from typing import List, Dict, Optional
from core.embedder import Embedder
from core.reranker import Reranker
from core.llm_client import LLMClient
from core.prompt_builder import PromptBuilder, PromptConfig, ConsultationContext
from db.qdrant_client import QdrantClientWrapper
from config import settings


class RetrievalPipeline:
    """Online pipeline for retrieval and generation."""

    def __init__(
        self,
        retrieval_top_k: int = None,
        rerank_top_k: int = None
    ):
        self.retrieval_top_k = retrieval_top_k or settings.RETRIEVAL_TOP_K
        self.rerank_top_k = rerank_top_k or settings.RERANK_TOP_K

        self.embedder = Embedder()
        self.reranker = Reranker()
        self.llm = LLMClient()
        self.qdrant = QdrantClientWrapper()
        self.prompt_builder = PromptBuilder()

    def retrieve(
        self,
        query: str,
        expand_context: bool = True,
        context_window: int = 2
    ) -> List[Dict[str, any]]:
        """
        Perform hybrid retrieval with reranking and optional context expansion.

        Args:
            query: User's search query (in Chinese)
            expand_context: Whether to expand chunks with adjacent content
            context_window: Number of adjacent chunks to fetch on each side

        Returns:
            List of retrieved documents with relevance scores
        """
        # Generate dense and sparse embeddings
        embeddings = self.embedder.embed(query)

        # Hybrid search in Qdrant (dense + sparse with RRF)
        results = self.qdrant.search_hybrid(
            dense_vector=embeddings["dense"],
            sparse_vector=embeddings.get("sparse", {}),
            top_k=self.retrieval_top_k,
            alpha=0.7  # Weight for dense vs sparse
        )

        if not results:
            return []

        # Rerank using Chinese texts (with fallback: if text_zh is empty, use text_en)
        chinese_texts = []
        for r in results:
            zh = r.get("text_zh", "") or ""
            en = r.get("text_en", "") or ""
            chinese_texts.append(zh if zh else en)

        reranked = self.reranker.rerank(query, chinese_texts, self.rerank_top_k)

        # Reorder results based on reranking
        reranked_results = []
        for doc_idx, score in reranked:
            result = results[doc_idx].copy()
            result["rerank_score"] = score
            reranked_results.append(result)

        # Expand with adjacent chunks for richer context
        if expand_context:
            reranked_results = self.qdrant.expand_chunks_with_context(
                reranked_results, window=context_window
            )

        return reranked_results

    def retrieve_with_comparison(
        self,
        query: str,
        expand_context: bool = True,
        context_window: int = 2,
        before_rerank_limit: int = 10,
        after_rerank_limit: int = 5
    ) -> Dict[str, any]:
        """
        Perform hybrid retrieval and return results before and after reranking.

        Args:
            query: User's search query
            expand_context: Whether to expand chunks with adjacent content
            context_window: Number of adjacent chunks to fetch on each side
            before_rerank_limit: Number of results to return before reranking
            after_rerank_limit: Number of results to return after reranking

        Returns:
            Dict with 'before_rerank' and 'after_rerank' results
        """
        # Generate dense and sparse embeddings
        embeddings = self.embedder.embed(query)

        # Hybrid search in Qdrant (dense + sparse with RRF)
        results = self.qdrant.search_hybrid(
            dense_vector=embeddings["dense"],
            sparse_vector=embeddings.get("sparse", {}),
            top_k=self.retrieval_top_k,
            alpha=0.7
        )

        if not results:
            return {"before_rerank": [], "after_rerank": [], "query": query}

        # Expand before reranking
        if expand_context:
            results = self.qdrant.expand_chunks_with_context(
                results, window=context_window
            )

        before_rerank = results[:before_rerank_limit]

        # Now rerank on the expanded results
        chinese_texts = []
        for r in results:
            zh = r.get("text_zh", "") or ""
            en = r.get("text_en", "") or ""
            chinese_texts.append(zh if zh else en)

        reranked = self.reranker.rerank(query, chinese_texts, self.retrieval_top_k)

        # Build reranked results with scores
        after_rerank_results = []
        for doc_idx, score in reranked:
            if doc_idx < len(results):
                result = results[doc_idx].copy()
                result["rerank_score"] = score
                after_rerank_results.append(result)

        after_rerank = after_rerank_results[:after_rerank_limit]

        return {
            "before_rerank": before_rerank,
            "after_rerank": after_rerank,
            "query": query
        }

    def query(
        self,
        query: str,
        include_sources: bool = True,
        scenario: str = "consultation",
        consultation_phase: str = "problem_exploration"
    ) -> Dict[str, any]:
        """
        Synchronous query interface combining retrieval + LLM generation.

        Args:
            query: User's question
            include_sources: Whether to include source documents
            scenario: consultation | supervision | workshop
            consultation_phase: greeting | problem_exploration | focusing | ...

        Returns:
            Dict with answer and optionally source documents
        """
        import asyncio

        # Retrieve docs
        docs = self.retrieve(query, expand_context=False)

        # Build context for LLM
        context = ConsultationContext(
            user_id="anonymous",
            session_id="single_query",
            current_topic=None,
            consultation_phase=consultation_phase,
            user_emotional_state=None,
            techniques_used=[],
            key_insights=[],
            previous_turns=[],
            scenario=scenario
        )

        # Build prompts using PromptBuilder
        system_prompt, user_prompt = self.prompt_builder.build_consultation_prompt(
            query=query,
            context=context,
            retrieved_docs=docs,
            config=PromptConfig(
                persona_enabled=True,
                skills_enabled=True,
                fewshot_enabled=False,
                tone="direct",
                response_length="short",
                language="bilingual",
                scenario=scenario
            )
        )

        # Run async generate
        answer = asyncio.run(
            self.llm.generate(
                system_prompt=system_prompt,
                user_message=user_prompt
            )
        )

        result = {
            "answer": answer,
            "scenario": scenario,
            "phase": consultation_phase,
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt)
        }

        if include_sources:
            result["sources"] = [
                {
                    "text_zh": doc["text_zh"],
                    "text_en": doc["text_en"],
                    "source": doc["source"],
                    "score": doc.get("rerank_score", doc.get("score", 0))
                }
                for doc in docs
            ]

        return result
