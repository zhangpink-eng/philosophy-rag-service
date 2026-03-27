from typing import List, Dict, Optional, Tuple, Any
import qdrant_client
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SparseVector,
    SparseVectorParams,
    SparseIndexParams,
    NamedSparseVector
)
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from config import settings


class QdrantClientWrapper:
    """Qdrant client wrapper with hybrid search support."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None
    ):
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name or settings.QDRANT_COLLECTION

        self.client = QdrantClient(
            url=f"http://{self.host}:{self.port}"
        )

    def create_collection(
        self,
        dense_dim: int = None,
        force_recreate: bool = False
    ) -> bool:
        """Create collection with dense and sparse vector support."""
        dense_dim = dense_dim or settings.DENSE_DIMENSION

        # Check if collection exists
        try:
            self.client.get_collection(self.collection_name)
            exists = True
        except (UnexpectedResponse, Exception):
            exists = False

        if exists and not force_recreate:
            return False

        if exists and force_recreate:
            self.client.delete_collection(self.collection_name)

        # Create collection with both dense and sparse vectors
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=dense_dim,
                    distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(
                        on_disk=False
                    )
                )
            }
        )

        return True

    def upsert_points(
        self,
        points: List[Dict[str, Any]]
    ) -> bool:
        """Insert or update points into collection with dense and sparse vectors."""
        if not points:
            return False

        point_structs = []
        for point in points:
            vec = {"dense": point["dense_vector"]}

            # Add sparse vector if available
            if "sparse_vector" in point and point["sparse_vector"]:
                sparse = point["sparse_vector"]
                # Convert dict format to SparseVector format
                if isinstance(sparse, dict) and sparse:
                    indices = list(sparse.keys())
                    values = list(sparse.values())
                    vec["sparse"] = SparseVector(
                        indices=indices,
                        values=values
                    )

            point_structs.append(
                PointStruct(
                    id=point["id"],
                    vector=vec,
                    payload={
                        "text_en": point["text_en"],
                        "text_zh": point["text_zh"],
                        "source": point["source"],
                        "chunk_index": point["chunk_index"]
                    }
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=point_structs
        )

        return True

    def search_dense(
        self,
        vector: List[float],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """Search using dense vectors only."""
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=("dense", vector),
            limit=top_k
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text_en": hit.payload.get("text_en", ""),
                "text_zh": hit.payload.get("text_zh", ""),
                "source": hit.payload.get("source", ""),
                "chunk_index": hit.payload.get("chunk_index", 0)
            }
            for hit in results
        ]

    def search_sparse(
        self,
        sparse_vector: Dict[int, float],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """Search using sparse vectors only (BM25-like)."""
        if not sparse_vector:
            return []

        # Convert dict to SparseVector format
        indices = list(sparse_vector.keys())
        values = list(sparse_vector.values())

        # Use NamedSparseVector for sparse search
        query_vector = NamedSparseVector(
            name="sparse",
            vector=SparseVector(indices=indices, values=values)
        )

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text_en": hit.payload.get("text_en", ""),
                "text_zh": hit.payload.get("text_zh", ""),
                "source": hit.payload.get("source", ""),
                "chunk_index": hit.payload.get("chunk_index", 0)
            }
            for hit in results
        ]

    def search_hybrid(
        self,
        dense_vector: List[float],
        sparse_vector: Dict[int, float],
        top_k: int = 20,
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining dense and sparse vectors using RRF (Reciprocal Rank Fusion).

        Args:
            dense_vector: Dense embedding vector
            sparse_vector: Sparse vector dict {index: weight}
            top_k: Number of results to return
            alpha: Weight for dense vectors (1-alpha for sparse). Default 0.7.

        Returns:
            List of results with combined scores
        """
        # Get dense results
        dense_results = self.search_dense(dense_vector, top_k * 2)
        # Get sparse results
        sparse_results = self.search_sparse(sparse_vector, top_k * 2)

        if not dense_results and not sparse_results:
            return []

        # RRF fusion
        rrf_k = 60  # RRF constant
        doc_scores: Dict[int, Dict[str, Any]] = {}

        # Add dense scores
        for rank, result in enumerate(dense_results):
            doc_id = result["id"]
            rrf_score = alpha * (1 / (rrf_k + rank + 1))
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {"result": result, "combined_score": 0}
            doc_scores[doc_id]["combined_score"] += rrf_score

        # Add sparse scores
        for rank, result in enumerate(sparse_results):
            doc_id = result["id"]
            rrf_score = (1 - alpha) * (1 / (rrf_k + rank + 1))
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {"result": result, "combined_score": 0}
            doc_scores[doc_id]["combined_score"] += rrf_score

        # Sort by combined score
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1]["combined_score"],
            reverse=True
        )[:top_k]

        # Build final results
        final_results = []
        for doc_id, data in sorted_docs:
            result = data["result"].copy()
            result["score"] = data["combined_score"]
            result["dense_score"] = next(
                (r["score"] for r in dense_results if r["id"] == doc_id), 0
            )
            result["sparse_score"] = next(
                (r["score"] for r in sparse_results if r["id"] == doc_id), 0
            )
            final_results.append(result)

        return final_results

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status
            }
        except Exception as e:
            return {"error": str(e)}

    def delete_collection(self) -> bool:
        """Delete the collection."""
        try:
            self.client.delete_collection(self.collection_name)
            return True
        except Exception:
            return False
