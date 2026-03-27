from typing import List, Tuple
from FlagEmbedding import FlagReranker
from config import settings


class Reranker:
    """BGE-Reranker-v2-m3 for precise relevance ranking."""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or settings.RERANKER_MODEL_PATH
        self.model = FlagReranker(
            self.model_path,
            use_fp16=False
        )

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_k: Number of top results to return

        Returns:
            List of (document_index, score) tuples, sorted by relevance
        """
        if not documents:
            return []

        # Prepare query-document pairs
        pairs = [[query, doc] for doc in documents]

        # Get relevance scores
        scores = self.model.compute_score(pairs, normalize=True)

        # Create (index, score) tuples and sort by score descending
        results = list(enumerate(scores))
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def rerank_with_texts(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Rerank and return documents with their scores.

        Returns:
            List of (document_text, score) tuples
        """
        ranked_indices = self.rerank(query, documents, top_k)
        return [(documents[idx], score) for idx, score in ranked_indices]
