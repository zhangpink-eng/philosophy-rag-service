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
    NamedSparseVector,
    AliasOperations,
    CreateAliasOperation,
    DeleteAliasOperation
)
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from config import settings
import time


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
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            using="dense",
            limit=top_k,
            with_payload=True
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
            for hit in results.points
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

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=SparseVector(indices=indices, values=values),
            using="sparse",
            limit=top_k,
            with_payload=True
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
            for hit in results.points
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

    def create_versioned_collection(
        self,
        dense_dim: int = None,
        version_suffix: str = None
    ) -> str:
        """
        Create a new versioned collection for zero-downtime rebuild.

        Args:
            dense_dim: Dense vector dimension
            version_suffix: Optional version suffix (defaults to timestamp)

        Returns:
            The new collection name
        """
        dense_dim = dense_dim or settings.DENSE_DIMENSION
        version_suffix = version_suffix or str(int(time.time()))

        new_collection_name = f"{self.collection_name}_v{version_suffix}"

        # Check if already exists and delete
        try:
            self.client.get_collection(new_collection_name)
            self.client.delete_collection(new_collection_name)
        except (UnexpectedResponse, Exception):
            pass

        # Create new collection
        self.client.create_collection(
            collection_name=new_collection_name,
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

        return new_collection_name

    def switch_collection_alias(
        self,
        new_collection_name: str,
        alias_name: str = None
    ) -> bool:
        """
        Atomically switch alias to point to a different collection.

        Args:
            new_collection_name: The collection to point the alias at
            alias_name: The alias name (defaults to collection_name)

        Returns:
            True if successful
        """
        alias_name = alias_name or self.collection_name

        try:
            # Delete existing alias if any
            try:
                self.client.delete_collection_alias(alias_name)
            except Exception:
                pass

            # Create new alias
            self.client.update_collection_aliases(
                actions=[
                    CreateAliasOperation(
                        alias_name=alias_name,
                        collection_name=new_collection_name
                    )
                ]
            )
            return True
        except Exception as e:
            print(f"Failed to switch alias: {e}")
            return False

    def list_collection_versions(self) -> List[str]:
        """List all collections that are versions of the main collection."""
        try:
            collections = self.client.get_collections().collections
            return [
                c.name for c in collections
                if c.name.startswith(f"{self.collection_name}_v")
            ]
        except Exception:
            return []

    def delete_collection_by_name(self, collection_name: str) -> bool:
        """Delete a specific collection by name."""
        try:
            self.client.delete_collection(collection_name)
            return True
        except Exception as e:
            print(f"Failed to delete collection {collection_name}: {e}")
            return False

    def cleanup_old_versions(self, keep_latest: int = 2) -> List[str]:
        """
        Delete old versioned collections, keeping the specified number of recent ones.

        Args:
            keep_latest: Number of recent versions to keep

        Returns:
            List of deleted collection names
        """
        versions = self.list_collection_versions()
        if len(versions) <= keep_latest:
            return []

        # Sort by version (timestamp), keep the newest ones
        versions_sorted = sorted(versions, reverse=True)
        to_delete = versions_sorted[keep_latest:]

        deleted = []
        for v in to_delete:
            if self.delete_collection_by_name(v):
                deleted.append(v)

        return deleted

    def set_active_collection(self, collection_name: str) -> None:
        """Set the active collection name for queries."""
        self.collection_name = collection_name

    def get_adjacent_chunks(
        self,
        source: str,
        chunk_index: int,
        window: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get adjacent chunks from the same file around the given chunk_index.
        Used to expand context for LLM consumption.

        Args:
            source: Source file name
            chunk_index: Center chunk index
            window: Number of adjacent chunks to fetch on each side

        Returns:
            List of adjacent chunks (sorted by chunk_index)
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        # Calculate range
        min_idx = max(0, chunk_index - window)
        max_idx = chunk_index + window

        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="source",
                            match=MatchValue(value=source)
                        ),
                        FieldCondition(
                            key="chunk_index",
                            range=Range(gte=min_idx, lte=max_idx)
                        )
                    ]
                ),
                with_payload=True,
                limit=window * 2 + 1
            )

            chunks = []
            for hit in results:
                chunks.append({
                    "id": hit.id,
                    "chunk_index": hit.payload.get("chunk_index", 0),
                    "text_en": hit.payload.get("text_en", ""),
                    "text_zh": hit.payload.get("text_zh", ""),
                    "source": hit.payload.get("source", "")
                })

            # Sort by chunk_index
            chunks.sort(key=lambda x: x["chunk_index"])
            return chunks

        except Exception as e:
            print(f"Error fetching adjacent chunks: {e}")
            return []

    def expand_chunks_with_context(
        self,
        chunks: List[Dict[str, Any]],
        window: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Expand a list of retrieved chunks by fetching adjacent chunks.
        Merges text from same file to provide richer context.

        Args:
            chunks: List of chunks from search
            window: Number of adjacent chunks per side to fetch

        Returns:
            Expanded chunks with merged text from adjacent chunks
        """
        if not chunks:
            return []

        # Group by source to avoid duplicate fetches
        source_groups: Dict[str, List[int]] = {}
        for chunk in chunks:
            source = chunk.get("source", "")
            idx = chunk.get("chunk_index", 0)
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(idx)

        # Fetch adjacent chunks for each source
        expanded = []
        for source, indices in source_groups.items():
            # Get all chunks in range
            min_idx = min(indices)
            max_idx = max(indices)

            all_chunks_in_range = self.get_adjacent_chunks(
                source, (min_idx + max_idx) // 2, window=max_idx - min_idx + window
            )

            # Merge text_zh and text_en
            merged_zh = []
            merged_en = []
            for c in all_chunks_in_range:
                zh = c.get("text_zh", "").strip()
                en = c.get("text_en", "").strip()
                if zh:
                    merged_zh.append(zh)
                if en:
                    merged_en.append(en)

            # Use the first chunk as representative for scores
            representative = chunks[next(i for i, x in enumerate(chunks) if x.get("source") == source)]

            expanded.append({
                "source": source,
                "text_zh": "\n\n".join(merged_zh),
                "text_en": "\n\n".join(merged_en),
                "chunk_indices": [c["chunk_index"] for c in all_chunks_in_range],
                "score": representative.get("rerank_score", representative.get("score", 0))
            })

        # Re-sort by score
        expanded.sort(key=lambda x: x["score"], reverse=True)
        return expanded
