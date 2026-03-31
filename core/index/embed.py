#!/usr/bin/env python3
"""
BGE-m3 Embedder 封装
"""
from typing import List, Dict, Optional, Union
import numpy as np


class Embedder:
    """
    BGE-m3 Embedder

    使用 BGE-m3 模型生成文本向量
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "cpu",
        batch_size: int = 32,
        max_length: int = 512
    ):
        """
        Args:
            model_name: BGE-m3 模型名称
            device: 设备 "cpu" 或 "cuda"
            batch_size: 批处理大小
            max_length: 最大序列长度
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length
        self.model = None
        self.tokenizer = None

    def load(self):
        """加载模型"""
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            raise ImportError(
                "请安装 FlagEmbedding: pip install FlagEmbedding"
            )

        self.model = BGEM3FlagModel(
            self.model_name,
            device=self.device,
            use_fp16=(self.device == "cuda")
        )
        print(f"已加载模型: {self.model_name}")

    def embed(
        self,
        texts: Union[str, List[str]],
        batch_size: Optional[int] = None
    ) -> np.ndarray:
        """
        生成文本向量

        Args:
            texts: 单个文本或文本列表
            batch_size: 批处理大小

        Returns:
            numpy.ndarray: 文本向量
        """
        if self.model is None:
            self.load()

        if isinstance(texts, str):
            texts = [texts]

        batch_size = batch_size or self.batch_size

        # 分批处理
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results = self.model.encode(batch)
            all_embeddings.append(results["dense_vecs"])

        return np.vstack(all_embeddings)

    def embed_chunks(
        self,
        chunks: List[Dict],
        text_field: str = "text"
    ) -> np.ndarray:
        """
        为 chunks 生成向量

        Args:
            chunks: chunks 列表
            text_field: 文本字段名

        Returns:
            numpy.ndarray: 向量数组
        """
        texts = [chunk[text_field] for chunk in chunks]
        return self.embed(texts)


class BGEReranker:
    """
    BGE Reranker - 可选，用于重排
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu"
    ):
        self.model_name = model_name
        self.device = device
        self.model = None

    def load(self):
        """加载模型"""
        try:
            from FlagEmbedding import FlagReranker
        except ImportError:
            raise ImportError(
                "请安装 FlagEmbedding: pip install FlagEmbedding"
            )

        self.model = FlagReranker(
            self.model_name,
            device=self.device,
            use_fp16=(self.device == "cuda")
        )
        print(f"已加载 Reranker: {self.model_name}")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10
    ) -> List[Dict]:
        """
        重排文档

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 k 个

        Returns:
            List[Dict]: 重排后的结果 [{"index": int, "score": float}, ...]
        """
        if self.model is None:
            self.load()

        scores = self.model.compute_score([query] * len(documents), documents)
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return [{"index": idx, "score": score} for idx, score in ranked]


if __name__ == '__main__':
    # 测试
    embedder = Embedder(model_name="BAAI/bge-m3", device="cpu")
    embedder.load()

    texts = ["这是一个测试句子", "这是另一个测试句子"]
    embeddings = embedder.embed(texts)

    print(f"生成了 {len(embeddings)} 个向量")
    print(f"向量维度: {embeddings[0].shape}")
