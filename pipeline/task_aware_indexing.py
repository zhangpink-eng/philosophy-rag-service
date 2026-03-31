#!/usr/bin/env python3
"""
支持任务管理的索引管道

功能：
1. 集成任务管理器 (TaskManager)
2. 断点续传
3. 增量索引
4. 分阶段检查点保存

使用示例：
```python
from pipeline.task_aware_indexing import TaskAwareIndexingPipeline

pipeline = TaskAwareIndexingPipeline(
    data_dir="data/raw",
    task_id="indexing_001"
)

# 启动任务（自动恢复或创建新任务）
pipeline.start()

# 或恢复之前的任务
pipeline.resume()
```
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from tqdm import tqdm

from core.chunker import FixedWindowChunker
from core.translator import Translator
from core.embedder import Embedder
from core.preprocessor import analyze_document
from core.task_manager import (
    TaskManager,
    TaskStatus,
    StageStatus,
    get_task_manager
)
from db.qdrant_client import QdrantClientWrapper
from config import settings


class TaskAwareIndexingPipeline:
    """
    支持任务管理的索引管道

    特性：
    - 断点续传：中断后可从检查点恢复
    - 增量索引：跳过未变更的文件
    - 阶段检查点：每个阶段完成后保存进度
    """

    def __init__(
        self,
        data_dir: str = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        task_id: Optional[str] = None,
        project: str = "rag-service"
    ):
        self.data_dir = Path(data_dir or settings.RAW_DATA_DIR)
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.task_id = task_id

        # 初始化组件
        self.chunker = FixedWindowChunker(
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap
        )
        self.translator = Translator()
        self.embedder = Embedder()
        self.qdrant = QdrantClientWrapper()

        # 初始化任务管理器
        self.tm = get_task_manager(project=project)

        # 检查点保存间隔
        self.checkpoint_interval = 10  # 每处理10个文件保存一次

        # 任务状态
        self.current_task = None
        self.processed_files = []
        self.failed_files = []

    # ==================== 任务管理 ====================

    def start(self) -> Dict:
        """
        启动索引任务

        Returns:
            任务结果统计
        """
        # 检查是否有可恢复的任务
        resumable = self.tm.get_resumable_task()
        if resumable:
            print(f"发现可恢复的任务: {resumable.id}")
            return self.resume()

        # 创建新任务
        files = self._get_indexable_files()
        self.current_task = self.tm.create_task(
            task_name="indexing",
            metadata={
                "data_dir": str(self.data_dir),
                "total_files": len(files),
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap
            },
            stages=["load", "preprocess", "translate", "chunk", "embed", "index"]
        )
        self.task_id = self.current_task.id

        print(f"创建新任务: {self.task_id}")
        print(f"待处理文件: {len(files)}")

        return self._run_indexing(files)

    def resume(self) -> Dict:
        """恢复之前的任务"""
        task = self.tm.get_resumable_task()
        if not task:
            print("没有可恢复的任务")
            return self.start()

        self.current_task = task
        self.task_id = task.id

        # 获取最新的检查点
        checkpoint = self.tm.get_latest_checkpoint(task.id)
        if checkpoint:
            print(f"从阶段 '{checkpoint.stage_name}' 恢复")
            print(f"已处理: {checkpoint.processed_count}/{checkpoint.total_count}")

        # 重新加载文件列表
        files = self._get_indexable_files()

        # 获取已处理的文件列表
        processed_files = self.tm.load_checkpoint_data(
            task.id, "processed_files", "list"
        ) or []
        self.processed_files = processed_files

        # 过滤未处理的文件
        remaining_files = [f for f in files if str(f) not in processed_files]

        print(f"待处理文件: {len(remaining_files)}/{len(files)}")

        if not remaining_files:
            print("所有文件已处理完成")
            return self._get_task_summary()

        return self._run_indexing(remaining_files, is_resume=True)

    def _get_task_summary(self) -> Dict:
        """获取任务摘要"""
        processed = self.tm.load_checkpoint_data(
            self.task_id, "processed_files", "list"
        ) or []
        return {
            "task_id": self.task_id,
            "status": "completed",
            "total_files": len(processed),
            "processed_files": len(processed),
            "failed_files": len(self.failed_files)
        }

    # ==================== 文件处理 ====================

    def _get_indexable_files(self) -> List[Path]:
        """获取可索引的文件列表"""
        if not self.data_dir.exists():
            return []

        files = []
        for ext in ["*.txt", "*.md"]:
            files.extend(self.data_dir.glob(f"**/{ext}"))

        # 过滤隐藏文件和系统文件
        files = [f for f in files if not f.name.startswith('.')]

        # 按修改时间排序
        files.sort(key=lambda f: f.stat().st_mtime)

        return files

    def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件内容哈希"""
        import hashlib
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def _is_file_changed(self, file_path: Path) -> bool:
        """检查文件是否已变更"""
        stored_hash = self.tm.load_checkpoint_data(
            self.task_id, "file_hashes", file_path.name
        )
        if stored_hash is None:
            return True
        return self._compute_file_hash(file_path) != stored_hash

    def _mark_file_processed(self, file_path: Path):
        """标记文件已处理"""
        # 保存文件 hash
        file_hash = self._compute_file_hash(file_path)
        self.tm.save_checkpoint_data(
            self.task_id, "file_hashes", file_path.name, file_hash
        )

        # 更新已处理文件列表
        self.processed_files.append(str(file_path))
        self.tm.save_checkpoint_data(
            self.task_id, "processed_files", "list", self.processed_files
        )

    # ==================== 核心索引逻辑 ====================

    def _run_indexing(
        self,
        files: List[Path],
        is_resume: bool = False
    ) -> Dict:
        """
        执行索引流程

        Args:
            files: 文件列表
            is_resume: 是否是恢复模式
        """
        total_files = len(files)
        self.failed_files = []

        # 更新任务状态
        self.tm.update_stage_checkpoint(
            self.task_id,
            "load",
            StageStatus.COMPLETED.value,
            processed_count=0,
            total_count=total_files
        )

        # 阶段1: 预处理
        self.tm.update_stage_checkpoint(
            self.task_id,
            "preprocess",
            StageStatus.IN_PROGRESS.value,
            processed_count=0,
            total_count=total_files
        )

        print(f"\n{'='*60}")
        print(f"开始索引: {total_files} 个文件")
        print(f"{'='*60}\n")

        # 进度条
        with tqdm(total=total_files, desc="索引进度") as pbar:
            for i, file_path in enumerate(files):
                try:
                    # 检查文件是否变更
                    if is_resume and not self._is_file_changed(file_path):
                        print(f"跳过(未变更): {file_path.name}")
                        pbar.update(1)
                        continue

                    # 处理单个文件
                    num_chunks = self._index_single_file(file_path)

                    # 标记已处理
                    self._mark_file_processed(file_path)

                    # 更新检查点
                    if (i + 1) % self.checkpoint_interval == 0:
                        self.tm.update_stage_checkpoint(
                            self.task_id,
                            "preprocess",
                            StageStatus.IN_PROGRESS.value,
                            processed_count=i + 1,
                            total_count=total_files
                        )

                    pbar.update(1)

                except Exception as e:
                    print(f"\n处理失败: {file_path.name} - {e}")
                    self.failed_files.append({
                        "file": str(file_path),
                        "error": str(e)
                    })
                    pbar.update(1)
                    continue

        # 标记任务完成
        self.tm.update_stage_checkpoint(
            self.task_id,
            "preprocess",
            StageStatus.COMPLETED.value,
            processed_count=total_files,
            total_count=total_files
        )

        # 更新任务状态
        if self.current_task:
            self.current_task.status = TaskStatus.COMPLETED.value
            self.tm.update_task(self.current_task)

        return {
            "task_id": self.task_id,
            "total_files": total_files,
            "processed_files": len(self.processed_files),
            "failed_files": len(self.failed_files),
            "failed_details": self.failed_files
        }

    def _index_single_file(self, file_path: Path) -> int:
        """索引单个文件"""
        file_name = file_path.name
        print(f"\n处理: {file_name}")

        # 读取文件
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # 分析文档结构
        doc_analysis = analyze_document(raw_content)
        is_bilingual = doc_analysis['language'] in ('bilingual', 'zh_en_mixed')

        if is_bilingual:
            return self._index_bilingual_file(file_path, doc_analysis)
        else:
            return self._index_monolingual_file(file_path, raw_content)

    def _index_bilingual_file(
        self,
        file_path: Path,
        doc_analysis: Dict
    ) -> int:
        """索引双语文件"""
        file_name = file_path.name
        zh_content = doc_analysis.get('text_zh', '') or ''
        en_content = doc_analysis.get('text_en', '') or ''

        # 分块
        zh_chunks = self.chunker.chunk_text(zh_content) if zh_content else []
        en_chunks = self.chunker.chunk_text(en_content) if en_content else []

        print(f"  中文: {len(zh_chunks)} chunks, 英文: {len(en_chunks)} chunks")

        # 构建 points
        points = []

        for i, chunk in enumerate(zh_chunks):
            points.append({
                "id": hash(f"{file_name}_zh_{i}") % (10**12),
                "text_en": "",
                "text_zh": chunk["text"],
                "source": file_name,
                "chunk_index": i,
                "language": "zh"
            })

        for i, chunk in enumerate(en_chunks):
            points.append({
                "id": hash(f"{file_name}_en_{i}") % (10**12),
                "text_en": chunk["text"],
                "text_zh": "",
                "source": file_name,
                "chunk_index": len(zh_chunks) + i,
                "language": "en"
            })

        # 向量化和索引
        return self._embed_and_index(points, file_path)

    def _index_monolingual_file(
        self,
        file_path: Path,
        content: str
    ) -> int:
        """索引单语文件"""
        file_name = file_path.name

        # 分块
        chunks = self.chunker.chunk_text(content)
        print(f"  分块: {len(chunks)} chunks")

        # 构建 points
        points = []
        for i, chunk in enumerate(chunks):
            points.append({
                "id": hash(f"{file_name}_{i}") % (10**12),
                "text_en": chunk["text"],
                "text_zh": "",
                "source": file_name,
                "chunk_index": i,
                "language": "en"  # 目前只处理英文原文
            })

        # 翻译成中文
        if points:
            texts_to_translate = [p["text_en"] for p in points]
            translated = self.translator.translate_batch(texts_to_translate, target_lang="zh")

            for point, zh_text in zip(points, translated):
                point["text_zh"] = zh_text or ""

        # 向量化和索引
        return self._embed_and_index(points, file_path)

    def _embed_and_index(
        self,
        points: List[Dict],
        file_path: Path
    ) -> int:
        """向量化并索引"""
        if not points:
            return 0

        # 分离中英文文本
        zh_texts = [p["text_zh"] for p in points if p["text_zh"]]
        en_texts = [p["text_en"] for p in points if p["text_en"]]

        # Dense 向量
        zh_dense = self.embedder.embed_dense(zh_texts) if zh_texts else []
        en_dense = self.embedder.embed_dense(en_texts) if en_texts else []

        # Sparse 向量
        zh_sparse = self.embedder.embed_sparse(zh_texts) if zh_texts else []
        en_sparse = self.embedder.embed_sparse(en_texts) if en_texts else []

        # 分配向量
        zh_idx = en_idx = 0
        for point in points:
            if point["text_zh"]:
                point["dense_vector"] = zh_dense[zh_idx] if zh_idx < len(zh_dense) else []
                point["sparse_vector"] = zh_sparse[zh_idx] if zh_idx < len(zh_sparse) else {}
                zh_idx += 1
            else:
                point["dense_vector"] = en_dense[en_idx] if en_idx < len(en_dense) else []
                point["sparse_vector"] = en_sparse[en_idx] if en_idx < len(en_sparse) else {}
                en_idx += 1

        # 索引到 Qdrant
        self.qdrant.upsert_points(points)
        print(f"  索引完成: {len(points)} points")

        return len(points)

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict:
        """获取当前状态"""
        if not self.task_id:
            return {"status": "no_task"}

        task = self.tm.get_task(self.task_id)
        if not task:
            return {"status": "task_not_found"}

        checkpoint = self.tm.get_latest_checkpoint(self.task_id)

        return {
            "task_id": self.task_id,
            "status": task.status,
            "current_stage": checkpoint.stage_name if checkpoint else None,
            "processed_count": checkpoint.processed_count if checkpoint else 0,
            "total_count": checkpoint.total_count if checkpoint else 0,
            "failed_files": self.failed_files
        }

    def cancel(self):
        """取消当前任务"""
        if self.current_task:
            self.current_task.status = TaskStatus.CANCELLED.value
            self.tm.update_task(self.current_task)
            print(f"任务已取消: {self.task_id}")

    def reset(self):
        """重置任务（清除所有检查点）"""
        if self.task_id:
            self.tm.clear_task_checkpoints(self.task_id)
            print(f"任务已重置: {self.task_id}")


# ==================== CLI ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='任务感知的索引管道')
    parser.add_argument('--data-dir', '-d', help='数据目录')
    parser.add_argument('--task-id', '-t', help='任务 ID')
    parser.add_argument('--resume', '-r', action='store_true', help='恢复之前的任务')
    parser.add_argument('--reset', action='store_true', help='重置任务')
    parser.add_argument('--status', action='store_true', help='查看状态')

    args = parser.parse_args()

    pipeline = TaskAwareIndexingPipeline(
        data_dir=args.data_dir,
        task_id=args.task_id
    )

    if args.status:
        print(json.dumps(pipeline.get_status(), indent=2))
    elif args.reset:
        pipeline.reset()
    elif args.resume:
        result = pipeline.resume()
        print(json.dumps(result, indent=2))
    else:
        result = pipeline.start()
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
