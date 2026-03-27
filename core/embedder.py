from typing import Dict, List, Union, Tuple
from FlagEmbedding import BGEM3FlagModel
from config import settings


class Embedder:
    """BGE-M3 Embedding model wrapper for dense and sparse embeddings."""

    def __init__(
        self,
        model_path: str = None,
        dense_dimension: int = 1024
    ):
        self.model_path = model_path or settings.BGE_M3_MODEL_PATH
        self.dense_dimension = dense_dimension
        self.model = BGEM3FlagModel(
            self.model_path,
            use_fp16=False,
            normalize_embeddings=True
        )

    def embed(self, texts: Union[str, List[str]]) -> Union[Dict, List[Dict]]:
        """
        Generate both dense and sparse embeddings.

        Returns:
            Dict with 'dense' (List[float]) and 'sparse' (Dict[int, float])
        """
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        # BGE-M3 generates both dense and sparse
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False
        )

        results = []
        for i in range(len(texts)):
            result = {
                "dense": output["dense_vecs"][i].tolist(),
                "sparse": output["lexical_weights"][i] if "lexical_weights" in output else {}
            }
            # Convert sparse format if needed
            if isinstance(result["sparse"], list):
                sparse_dict = {}
                for item in result["sparse"]:
                    if isinstance(item, dict) and "indices" in item and "values" in item:
                        for idx, val in zip(item["indices"], item["values"]):
                            sparse_dict[int(idx)] = float(val)
                result["sparse"] = sparse_dict
            results.append(result)

        return results[0] if is_single else results

    def embed_dense(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Generate dense embeddings only."""
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False
        )

        result = output["dense_vecs"].tolist()
        return result[0] if is_single else result

    def embed_sparse(self, texts: Union[str, List[str]]) -> Union[Dict, List[Dict]]:
        """Generate sparse (BM25-like) embeddings."""
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        output = self.model.encode(
            texts,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False
        )

        results = []
        for i in range(len(texts)):
            sparse_weights = output["lexical_weights"][i]
            sparse_dict = {}
            if isinstance(sparse_weights, list):
                for item in sparse_weights:
                    if isinstance(item, dict) and "indices" in item and "values" in item:
                        for idx, val in zip(item["indices"], item["values"]):
                            sparse_dict[int(idx)] = float(val)
            elif isinstance(sparse_weights, dict):
                sparse_dict = {int(k): float(v) for k, v in sparse_weights.items()}
            results.append(sparse_dict)

        return results[0] if is_single else results

    def similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts."""
        embeddings = self.embed([text1, text2])
        dense1 = embeddings[0]["dense"]
        dense2 = embeddings[1]["dense"]

        # Cosine similarity
        dot = sum(a * b for a, b in zip(dense1, dense2))
        norm1 = sum(a * a for a in dense1) ** 0.5
        norm2 = sum(a * a for a in dense2) ** 0.5

        return dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0
