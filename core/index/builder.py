#!/usr/bin/env python3
"""
索引构建器 - 将预处理结果转换为向量索引
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, asdict

from core.chunker import SemanticChunker
from .embed import Embedder, BGEReranker


@dataclass
class IndexChunk:
    """索引 Chunk 结构"""
    chunk_id: str
    text_zh: str
    text_en: str
    language: str  # "zh", "en"


class IndexBuilder:
    """
    索引构建器

    流程：
    1. 加载预处理结果 (chunks.json)
    2. 使用 BGE-m3 生成向量
    3. 存储向量索引
    """

    def __init__(
        self,
        embed_model: str = None,
        device: str = "cpu",
        batch_size: int = 32,
        max_chunk_size: int = 512,
        chunk_overlap: int = 64
    ):
        """
        Args:
            embed_model: BGE-m3 模型路径或名称，默认使用本地模型
            device: 设备 "cpu" 或 "cuda"
            batch_size: 批处理大小
            max_chunk_size: 最大 chunk 大小
            chunk_overlap: chunk 重叠大小
        """
        # 默认使用本地模型
        if embed_model is None:
            from pathlib import Path
            default_model = Path(__file__).parent.parent.parent / "models" / "bge-m3"
            if default_model.exists():
                embed_model = str(default_model)
            else:
                embed_model = "BAAI/bge-m3"

        self.embed_model = embed_model
        self.device = device
        self.batch_size = batch_size
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

        self.embedder = Embedder(
            model_name=embed_model,
            device=device,
            batch_size=batch_size,
            max_length=max_chunk_size
        )
        self.reranker = BGEReranker(device=device)
        self.chunker = SemanticChunker(
            max_chunk_size=max_chunk_size,
            overlap=chunk_overlap
        )

    def load_chunks(self, chunks_path: Union[str, Path]) -> List[IndexChunk]:
        """
        加载预处理结果

        Args:
            chunks_path: chunks.json 文件路径

        Returns:
            List[IndexChunk]: chunk 列表
        """
        with open(chunks_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        chunks = []
        for item in data.get("chunks", []):
            chunk = IndexChunk(
                chunk_id=item["chunk_id"],
                text_zh=item.get("text_zh", ""),
                text_en=item.get("text_en", ""),
                language=item.get("language", "zh")
            )
            chunks.append(chunk)

        return chunks

    def build_index(
        self,
        chunks_path: Union[str, Path],
        output_dir: Union[str, Path],
        use_reranker: bool = False
    ) -> Dict:
        """
        构建索引

        Args:
            chunks_path: 预处理结果路径
            output_dir: 输出目录
            use_reranker: 是否加载 reranker

        Returns:
            Dict: 索引构建统计信息
        """
        chunks_path = Path(chunks_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 加载 chunks
        print("加载预处理结果...")
        chunks = self.load_chunks(chunks_path)
        print(f"加载了 {len(chunks)} 个 chunks")

        # 2. 分离中英文
        zh_chunks = [c for c in chunks if c.text_zh]
        en_chunks = [c for c in chunks if c.text_en]
        print(f"中文 chunks: {len(zh_chunks)}")
        print(f"英文 chunks: {len(en_chunks)}")

        # 3. 加载 embedder
        print("加载 BGE-m3 模型...")
        self.embedder.load()

        # 4. 生成中文向量
        zh_vectors = None
        if zh_chunks:
            print("生成中文向量...")
            zh_texts = [c.text_zh for c in zh_chunks]
            zh_vectors = self.embedder.embed(zh_texts)
            print(f"中文向量: {zh_vectors.shape}")

        # 5. 生成英文向量
        en_vectors = None
        if en_chunks:
            print("生成英文向量...")
            en_texts = [c.text_en for c in en_chunks]
            en_vectors = self.embedder.embed(en_texts)
            print(f"英文向量: {en_vectors.shape}")

        # 6. 加载 reranker (可选)
        if use_reranker:
            print("加载 BGE Reranker...")
            self.reranker.load()

        # 7. 保存索引
        print("保存索引...")
        index_data = {
            "chunks": [asdict(c) for c in chunks],
            "zh_chunk_ids": [c.chunk_id for c in zh_chunks],
            "en_chunk_ids": [c.chunk_id for c in en_chunks],
            "vector_dim": zh_vectors.shape[1] if zh_vectors is not None else 0,
            "config": {
                "embed_model": self.embed_model,
                "max_chunk_size": self.max_chunk_size,
                "chunk_overlap": self.chunk_overlap
            }
        }

        # 保存 chunks 和元数据
        with open(output_dir / "index_data.json", 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        # 保存向量 (使用 numpy)
        if zh_vectors is not None:
            np.save(output_dir / "zh_vectors.npy", zh_vectors)
        if en_vectors is not None:
            np.save(output_dir / "en_vectors.npy", en_vectors)

        print(f"索引保存到: {output_dir}")

        return {
            "total_chunks": len(chunks),
            "zh_chunks": len(zh_chunks),
            "en_chunks": len(en_chunks),
            "zh_vector_shape": zh_vectors.shape if zh_vectors is not None else None,
            "en_vector_shape": en_vectors.shape if en_vectors is not None else None,
            "output_dir": str(output_dir)
        }


class VectorStore:
    """
    向量存储（简单实现，可替换为 Milvus/Pinecone 等）
    """

    def __init__(
        self,
        zh_vectors: np.ndarray,
        en_vectors: np.ndarray,
        zh_chunk_ids: List[str],
        en_chunk_ids: List[str]
    ):
        self.zh_vectors = zh_vectors
        self.en_vectors = en_vectors
        self.zh_chunk_ids = zh_chunk_ids
        self.en_chunk_ids = en_chunk_ids

    @classmethod
    def load(cls, index_dir: Union[str, Path]) -> "VectorStore":
        """加载索引"""
        index_dir = Path(index_dir)

        zh_vectors = np.load(index_dir / "zh_vectors.npy") if (
            index_dir / "zh_vectors.npy"
        ).exists() else None
        en_vectors = np.load(index_dir / "en_vectors.npy") if (
            index_dir / "en_vectors.npy"
        ).exists() else None

        with open(index_dir / "index_data.json", 'r', encoding='utf-8') as f:
            data = json.load(f)

        return cls(
            zh_vectors=zh_vectors,
            en_vectors=en_vectors,
            zh_chunk_ids=data["zh_chunk_ids"],
            en_chunk_ids=data["en_chunk_ids"]
        )

    def search(
        self,
        query_vector: np.ndarray,
        language: str = "zh",
        top_k: int = 10
    ) -> List[Dict]:
        """
        向量检索

        Args:
            query_vector: 查询向量
            language: 检索语言 "zh" 或 "en"
            top_k: 返回前 k 个

        Returns:
            List[Dict]: [{"chunk_id": str, "score": float}, ...]
        """
        vectors = self.zh_vectors if language == "zh" else self.en_vectors
        chunk_ids = self.zh_chunk_ids if language == "zh" else self.en_chunk_ids

        if vectors is None:
            return []

        # 计算余弦相似度
        query_norm = query_vector / np.linalg.norm(query_vector)
        vec_norm = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        similarities = np.dot(vec_norm, query_norm)

        # 取 top_k
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [
            {"chunk_id": chunk_ids[idx], "score": float(similarities[idx])}
            for idx in top_indices
        ]


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='构建向量索引')
    parser.add_argument('chunks_path', help='预处理结果路径 (chunks.json)')
    parser.add_argument('-o', '--output', required=True, help='输出目录')
    parser.add_argument('--embed-model', default='BAAI/bge-m3', help='Embedding 模型')
    parser.add_argument('--device', default='cpu', help='设备 (cpu/cuda)')
    parser.add_argument('--batch-size', type=int, default=32, help='批处理大小')
    parser.add_argument('--use-reranker', action='store_true', help='使用 Reranker')

    args = parser.parse_args()

    builder = IndexBuilder(
        embed_model=args.embed_model,
        device=args.device,
        batch_size=args.batch_size
    )

    result = builder.build_index(
        chunks_path=args.chunks_path,
        output_dir=args.output,
        use_reranker=args.use_reranker
    )

    print("\n索引构建完成!")
    print(f"总 chunks: {result['total_chunks']}")
    print(f"中文 chunks: {result['zh_chunks']}")
    print(f"英文 chunks: {result['en_chunks']}")


if __name__ == '__main__':
    main()
