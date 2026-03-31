#!/usr/bin/env python3
"""
检索模块 - 提供向量检索接口
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Union


class Retriever:
    """
    向量检索器

    使用方式:
    ```python
    from core.index.retriever import Retriever

    retriever = Retriever("/path/to/index")
    results = retriever.search("查询内容", language="zh", top_k=5)
    ```
    """

    def __init__(
        self,
        index_dir: Union[str, Path],
        embedder=None
    ):
        """
        Args:
            index_dir: 索引目录
            embedder: Embedder 实例（可选，默认内部创建）
        """
        self.index_dir = Path(index_dir)
        self._load_index()
        self.embedder = embedder

    def _load_index(self):
        """加载索引数据"""
        # 加载 chunks 元数据
        with open(self.index_dir / "index_data.json", 'r', encoding='utf-8') as f:
            self.index_data = json.load(f)

        # 加载 chunks
        self.chunks = self.index_data["chunks"]
        self.zh_chunk_ids = self.index_data.get("zh_chunk_ids", [])
        self.en_chunk_ids = self.index_data.get("en_chunk_ids", [])

        # 加载向量
        self.zh_vectors = None
        self.en_vectors = None

        zh_path = self.index_dir / "zh_vectors.npy"
        en_path = self.index_dir / "en_vectors.npy"

        if zh_path.exists():
            self.zh_vectors = np.load(zh_path)

        if en_path.exists():
            self.en_vectors = np.load(en_path)

        self.vector_dim = self.index_data.get("vector_dim", 1024)

        # 创建 chunk_id 到 chunk 的映射
        self.chunk_map = {c["chunk_id"]: c for c in self.chunks}

    def _load_embedder(self):
        """加载 embedder（延迟加载）"""
        if self.embedder is None:
            from core.index.embed import Embedder
            self.embedder = Embedder(
                model_name=str(self.index_dir.parent.parent / "models" / "bge-m3"),
                device="cpu"
            )
            self.embedder.load()

    def _cosine_sim(self, query_vec: np.ndarray, vectors: np.ndarray) -> np.ndarray:
        """计算余弦相似度"""
        query_norm = query_vec / np.linalg.norm(query_vec)
        vec_norm = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.dot(vec_norm, query_norm)

    def search(
        self,
        query: str,
        language: str = "zh",
        top_k: int = 5,
        return_text: bool = True
    ) -> List[Dict]:
        """
        检索

        Args:
            query: 查询文本
            language: 检索语言 "zh" 或 "en"
            top_k: 返回前 k 个结果
            return_text: 是否返回文本内容

        Returns:
            List[Dict]: 检索结果
            [{
                "chunk_id": str,
                "score": float,
                "text_zh": str,
                "text_en": str,
                "language": str
            }, ...]
        """
        self._load_embedder()

        # 选择向量和 chunk_ids
        vectors = self.zh_vectors if language == "zh" else self.en_vectors
        chunk_ids = self.zh_chunk_ids if language == "zh" else self.en_chunk_ids

        if vectors is None or len(vectors) == 0:
            return []

        # 生成 query 向量
        query_vec = self.embedder.embed([query])[0]

        # 计算相似度
        similarities = self._cosine_sim(query_vec, vectors)

        # 取 top_k
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # 构建结果
        results = []
        for idx in top_indices:
            chunk_id = chunk_ids[idx]
            chunk = self.chunk_map.get(chunk_id, {})

            result = {
                "chunk_id": chunk_id,
                "score": float(similarities[idx]),
                "language": chunk.get("language", language)
            }

            if return_text:
                result["text_zh"] = chunk.get("text_zh", "")
                result["text_en"] = chunk.get("text_en", "")

            results.append(result)

        return results

    def search_bilingual(
        self,
        query_zh: str,
        query_en: str,
        top_k: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        双语检索

        Args:
            query_zh: 中文查询
            query_en: 英文查询
            top_k: 返回前 k 个结果

        Returns:
            Dict: {"zh": [...], "en": [...]}
        """
        zh_results = self.search(query_zh, language="zh", top_k=top_k)
        en_results = self.search(query_en, language="en", top_k=top_k)

        return {
            "zh": zh_results,
            "en": en_results
        }

    def get_chunk(self, chunk_id: str) -> Optional[Dict]:
        """获取指定 chunk"""
        return self.chunk_map.get(chunk_id)

    def get_paired_chunk(self, chunk_id: str) -> Dict[str, Optional[Dict]]:
        """
        获取配对的 chunk

        Args:
            chunk_id: chunk ID

        Returns:
            Dict: {"current": chunk, "paired": paired_chunk}
        """
        current = self.chunk_map.get(chunk_id)
        if not current:
            return {"current": None, "paired": None}

        # 查找配对：如果 chunk_id 以 _zh_ 结尾，查找 _en_ 版本
        paired_id = None
        if "_zh_" in chunk_id:
            paired_id = chunk_id.replace("_zh_", "_en_")
        elif "_en_" in chunk_id:
            paired_id = chunk_id.replace("_en_", "_zh_")

        paired = self.chunk_map.get(paired_id) if paired_id else None

        return {
            "current": current,
            "paired": paired
        }

    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        return {
            "total_chunks": len(self.chunks),
            "zh_chunks": len(self.zh_chunk_ids),
            "en_chunks": len(self.en_chunk_ids),
            "vector_dim": self.vector_dim,
            "index_dir": str(self.index_dir)
        }


def main():
    """命令行测试"""
    import argparse

    parser = argparse.ArgumentParser(description='检索测试')
    parser.add_argument('index_dir', help='索引目录')
    parser.add_argument('query', help='查询文本')
    parser.add_argument('-l', '--language', choices=['zh', 'en'], default='zh',
                        help='查询语言')
    parser.add_argument('-k', '--top-k', type=int, default=5, help='返回数量')

    args = parser.parse_args()

    retriever = Retriever(args.index_dir)

    print(f"索引统计: {retriever.get_stats()}")
    print()

    results = retriever.search(args.query, language=args.language, top_k=args.top_k)

    print(f"查询: {args.query}")
    print(f"语言: {args.language}")
    print(f"结果:")
    print("-" * 60)

    for i, r in enumerate(results, 1):
        print(f"\n{i}. [{r['score']:.4f}] {r['chunk_id']}")
        text = r.get('text_zh') or r.get('text_en', '')
        print(f"   {text[:100]}...")


if __name__ == '__main__':
    main()
