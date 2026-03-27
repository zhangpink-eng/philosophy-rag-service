from typing import List, Dict, Optional, AsyncIterator
from core.embedder import Embedder
from core.reranker import Reranker
from core.llm_client import LLMClient
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

    def retrieve(
        self,
        query: str
    ) -> List[Dict[str, any]]:
        """
        Perform hybrid retrieval with reranking (dense + sparse with RRF fusion).

        Args:
            query: User's search query (in Chinese)

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

        # Rerank using Chinese texts
        if results:
            chinese_texts = [r["text_zh"] for r in results]
            reranked = self.reranker.rerank(query, chinese_texts, self.rerank_top_k)

            # Reorder results based on reranking
            reranked_results = []
            for doc_idx, score in reranked:
                result = results[doc_idx].copy()
                result["rerank_score"] = score
                reranked_results.append(result)

            return reranked_results

        return results[:self.rerank_top_k]

    def retrieve_with_comparison(
        self,
        query: str
    ) -> Dict[str, any]:
        """
        Perform hybrid retrieval and return results before and after reranking for comparison.

        Args:
            query: User's search query (in Chinese)

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

        before_rerank = results[:self.rerank_top_k]

        # Rerank using Chinese texts
        after_rerank = []
        if results:
            chinese_texts = [r["text_zh"] for r in results]
            reranked = self.reranker.rerank(query, chinese_texts, self.rerank_top_k)

            for doc_idx, score in reranked:
                result = results[doc_idx].copy()
                result["rerank_score"] = score
                after_rerank.append(result)

        return {
            "before_rerank": before_rerank,
            "after_rerank": after_rerank,
            "query": query
        }

    async def generate(
        self,
        query: str,
        use_stream: bool = False
    ) -> str:
        """
        Generate answer using retrieved context.

        Args:
            query: User's question
            use_stream: Whether to use streaming generation

        Returns:
            Generated answer
        """
        # Retrieve relevant documents
        docs = self.retrieve(query)

        if not docs:
            return "抱歉，我在参考资料中没有找到与您问题相关的内容。"

        # Build context for LLM
        contexts = [
            {
                "text_zh": doc["text_zh"],
                "text_en": doc["text_en"],
                "source": doc["source"]
            }
            for doc in docs
        ]

        # Build prompt
        system_prompt = self.llm.build_system_prompt()
        user_prompt = self.llm.build_qa_prompt(query, contexts)

        # Generate response
        if use_stream:
            response_parts = []
            async for chunk in self.llm.generate_stream(system_prompt, user_prompt):
                response_parts.append(chunk)
            return "".join(response_parts)
        else:
            return await self.llm.generate(system_prompt, user_prompt)

    async def generate_stream(
        self,
        query: str
    ) -> AsyncIterator[str]:
        """
        Generate streaming answer.

        Yields:
            Text chunks as they are generated
        """
        # Retrieve relevant documents
        docs = self.retrieve(query)

        if not docs:
            yield "抱歉，我在参考资料中没有找到与您问题相关的内容。"
            return

        # Build context for LLM
        contexts = [
            {
                "text_zh": doc["text_zh"],
                "text_en": doc["text_en"],
                "source": doc["source"]
            }
            for doc in docs
        ]

        # Build prompt
        system_prompt = self.llm.build_system_prompt()
        user_prompt = self.llm.build_qa_prompt(query, contexts)

        # Stream response
        async for chunk in self.llm.generate_stream(system_prompt, user_prompt):
            yield chunk

    def query(
        self,
        query: str,
        include_sources: bool = True
    ) -> Dict[str, any]:
        """
        Synchronous query interface.

        Args:
            query: User's question
            include_sources: Whether to include source documents

        Returns:
            Dict with answer and optionally source documents
        """
        import asyncio

        # Run async generate
        answer = asyncio.run(self.generate(query, use_stream=False))

        # Retrieve docs for sources
        docs = self.retrieve(query)

        result = {"answer": answer}

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
