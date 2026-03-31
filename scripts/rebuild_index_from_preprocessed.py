#!/usr/bin/env python3
"""
从预处理好的 chunk 数据重建索引

用法：
    python scripts/rebuild_index_from_preprocessed.py

数据来源：/Users/pink/Desktop/哲学咨询/奥斯卡/文本预处理
数据格式：每个 JSON 文件含 chunks[], 每条 chunk 有 text_zh, text_en

索引策略（与原 pipeline 一致）：
    - Dense embedding: 使用英文 text_en（跨语言语义匹配）
    - Sparse embedding: 使用中文 text_zh（中文关键词命中）
"""
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Set
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.embedder import Embedder
from db.qdrant_client import QdrantClientWrapper
from config import settings


class PreprocessedIndexBuilder:
    """从预处理 JSON 加载 chunk 并重建 Qdrant 索引"""

    def __init__(
        self,
        preprocessed_dir: str = None,
        batch_size: int = 20
    ):
        self.preprocessed_dir = Path(preprocessed_dir or
            "/Users/pink/Desktop/哲学咨询/奥斯卡/文本预处理")
        self.batch_size = batch_size
        self.embedder = Embedder()
        self.qdrant = QdrantClientWrapper()

    def _load_preprocessed_files(self) -> List[Path]:
        """加载所有预处理 JSON 文件"""
        if not self.preprocessed_dir.exists():
            raise FileNotFoundError(f"目录不存在: {self.preprocessed_dir}")
        return list(self.preprocessed_dir.glob("*.json"))

    def _load_chunks_from_file(self, file_path: Path) -> List[Dict]:
        """从单个 JSON 文件加载 chunks"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("chunks", [])

    def _guess_language(self, chunk: Dict) -> str:
        """根据 text_zh 是否为空判断语言"""
        if chunk.get("text_zh", "").strip():
            return "zh"
        elif chunk.get("text_en", "").strip():
            return "en"
        return "mix"

    def _prepare_points(
        self,
        chunks: List[Dict],
        file_name: str,
        file_index: int
    ) -> List[Dict]:
        """
        将 chunks 转换为 Qdrant points

        策略：
        - Dense: 用英文 text_en（跨语言语义能力强）
        - Sparse: 用中文 text_zh（关键词命中）
        """
        points = []
        for i, chunk in enumerate(chunks):
            text_zh = chunk.get("text_zh", "").strip()
            text_en = chunk.get("text_en", "").strip()
            chunk_id = chunk.get("chunk_id", f"{file_name}_{i}")

            # 决定用哪个文本做 embedding
            # dense: 优先英文（跨语言能力强），没有英文才用中文
            # sparse: 优先中文，没有中文才用英文
            dense_text = text_en if text_en else text_zh
            sparse_text = text_zh if text_zh else text_en

            if not dense_text:
                continue  # 跳过空 chunk

            # 生成唯一 ID
            point_id = abs(hash(f"{file_name}_{chunk_id}_{i}")) % (10**12)

            point = {
                "id": point_id,
                "text_en": text_en,
                "text_zh": text_zh,
                "source": file_name,
                "chunk_id": chunk_id,
                "chunk_index": i,
                "file_index": file_index,
                "language": self._guess_language(chunk),
                "dense_text": dense_text,
                "sparse_text": sparse_text,
            }
            points.append(point)

        return points

    def _embed_batch(self, points: List[Dict]) -> List[Dict]:
        """批量生成 embeddings"""
        # 分离出需要 embedding 的文本
        dense_texts = [p["dense_text"] for p in points]
        sparse_texts = [p["sparse_text"] for p in points]

        # 生成 dense embedding (英文)
        dense_embeddings = self.embedder.embed_dense(dense_texts)

        # 生成 sparse embedding (中文)
        sparse_embeddings = self.embedder.embed_sparse(sparse_texts)

        # 写回 points
        for i, point in enumerate(points):
            point["dense_vector"] = dense_embeddings[i] if isinstance(dense_embeddings[0], list) else dense_embeddings
            point["sparse_vector"] = sparse_embeddings[i] if isinstance(sparse_embeddings, list) else sparse_embeddings

        return points

    def index_all(
        self,
        recreate_collection: bool = False,
        target_collection: str = None
    ) -> Dict:
        """
        重建全部索引

        Args:
            recreate_collection: 是否重建 collection
            target_collection: 可指定到特定 collection
        Returns:
            统计信息
        """
        print("=" * 60)
        print("从预处理数据重建索引")
        print(f"数据目录: {self.preprocessed_dir}")
        print("=" * 60)

        # 保存原始 collection 名称
        original_collection = self.qdrant.collection_name

        # 使用指定 collection
        if target_collection:
            self.qdrant.set_active_collection(target_collection)

        # 重建 collection
        if recreate_collection:
            self.qdrant.create_collection(force_recreate=True)
        else:
            self.qdrant.create_collection(force_recreate=False)

        # 加载文件列表
        files = self._load_preprocessed_files()
        print(f"\n找到 {len(files)} 个预处理文件")

        total_chunks = 0
        total_points = 0
        errors = 0

        for file_idx, file_path in enumerate(tqdm(files, desc="处理文件")):
            try:
                # 加载 chunks
                chunks = self._load_chunks_from_file(file_path)
                if not chunks:
                    print(f"\n警告: {file_path.name} 无 chunks，跳过")
                    continue

                # 准备 points（还没 embedding）
                points = self._prepare_points(chunks, file_path.stem, file_idx)

                # 批量 embedding
                for batch_start in range(0, len(points), self.batch_size):
                    batch = points[batch_start:batch_start + self.batch_size]
                    try:
                        batch = self._embed_batch(batch)
                        # 写入 Qdrant
                        self.qdrant.upsert_points(batch)
                    except Exception as e:
                        print(f"\n批次写入错误 ({file_path.name}): {e}")
                        errors += 1
                        continue

                total_chunks += len(chunks)
                total_points += len(points)

            except Exception as e:
                print(f"\n文件处理错误 ({file_path.name}): {e}")
                errors += 1
                continue

        # 恢复原始 collection
        if target_collection:
            self.qdrant.set_active_collection(original_collection)

        # 打印统计
        print("\n" + "=" * 60)
        print("索引重建完成")
        print(f"  处理文件: {len(files)}")
        print(f"  总 chunks: {total_chunks}")
        print(f"  成功索引: {total_points}")
        print(f"  错误数: {errors}")
        print("=" * 60)

        # Collection 信息
        info = self.qdrant.get_collection_info()
        print(f"\nCollection 信息: {info}")

        return {
            "files": len(files),
            "chunks": total_chunks,
            "indexed": total_points,
            "errors": errors,
            "collection_info": info
        }

    def rebuild_zero_downtime(self) -> Dict:
        """
        零停机重建：创建新 collection，索引完成后切换 alias
        """
        print("=" * 60)
        print("零停机重建索引")
        print("=" * 60)

        # 创建新 versioned collection
        timestamp = str(int(time.time()))
        new_collection = f"{settings.QDRANT_COLLECTION}_v{timestamp}"
        print(f"\n[1/4] 创建新 collection: {new_collection}")

        # 索引到新 collection
        print(f"\n[2/4] 开始索引到 {new_collection}...")
        result = self.index_all(
            recreate_collection=True,
            target_collection=new_collection
        )

        if result["indexed"] == 0:
            print("\n没有数据，清理并退出")
            self.qdrant.delete_collection_by_name(new_collection)
            return result

        # 切换 alias
        print(f"\n[3/4] 切换 alias -> {new_collection}")
        success = self.qdrant.switch_collection_alias(new_collection)

        if not success:
            print("⚠️  Alias 切换失败，collection 已就绪但未激活")
            return {**result, "warning": "alias_switch_failed"}

        print("Alias 切换成功!")

        # 清理旧版本
        print(f"\n[4/4] 清理旧版本 (保留最新 2 个)...")
        deleted = self.qdrant.cleanup_old_versions(keep_latest=2)
        if deleted:
            print(f"已删除: {', '.join(deleted)}")
        else:
            print("无旧版本需清理")

        print("\n" + "=" * 60)
        print("零停机重建完成!")
        print("=" * 60)

        return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="从预处理 JSON 重建索引")
    parser.add_argument(
        "--data-dir",
        default="/Users/pink/Desktop/哲学咨询/奥斯卡/文本预处理",
        help="预处理文件目录"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="批量 embedding 大小"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="重建 collection（删除旧数据）"
    )
    parser.add_argument(
        "--zero-downtime",
        action="store_true",
        help="零停机重建（创建新 collection 后切换）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计不写入"
    )

    args = parser.parse_args()

    builder = PreprocessedIndexBuilder(
        preprocessed_dir=args.data_dir,
        batch_size=args.batch_size
    )

    if args.dry_run:
        # 只统计
        files = builder._load_preprocessed_files()
        total_chunks = 0
        for f in files:
            chunks = builder._load_chunks_from_file(f)
            total_chunks += len(chunks)
        print(f"\n[DRY RUN] 找到 {len(files)} 个文件, 共 {total_chunks} chunks")
        return

    if args.zero_downtime:
        builder.rebuild_zero_downtime()
    elif args.rebuild:
        builder.index_all(recreate_collection=True)
    else:
        builder.index_all(recreate_collection=False)


if __name__ == "__main__":
    main()
