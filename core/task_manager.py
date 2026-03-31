#!/usr/bin/env python3
"""
全局任务管理器

功能：
1. 任务队列管理
2. 检查点 (Checkpoint) 保存与恢复
3. Manifest 持久化
4. 增量处理支持
5. 断点续传

使用示例：
```python
from core.task_manager import TaskManager, Task, TaskStage

tm = TaskManager(project="rag-service")

# 创建任务
task = tm.create_task("indexing", {
    "data_dir": "data/raw",
    "total_files": 100
})

# 检查是否有未完成任务需要恢复
resume_task = tm.get_resumable_task()
if resume_task:
    print(f"恢复任务: {resume_task.id}")
    # 继续处理
else:
    print("没有需要恢复的任务")
```
"""
import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
import threading
import shutil


class TaskStatus(Enum):
    PENDING = "pending"          # 等待执行
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 取消


class StageStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StageCheckpoint:
    """阶段检查点"""
    stage_name: str
    status: str = StageStatus.PENDING.value
    processed_count: int = 0
    total_count: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "stage_name": self.stage_name,
            "status": self.status,
            "processed_count": self.processed_count,
            "total_count": self.total_count,
            "data": self.data,
            "error": self.error,
            "updated_at": self.updated_at or datetime.now().isoformat()
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "StageCheckpoint":
        return cls(
            stage_name=d["stage_name"],
            status=d.get("status", StageStatus.PENDING.value),
            processed_count=d.get("processed_count", 0),
            total_count=d.get("total_count", 0),
            data=d.get("data", {}),
            error=d.get("error"),
            updated_at=d.get("updated_at")
        )


@dataclass
class Task:
    """任务"""
    id: str
    name: str
    project: str
    status: str = TaskStatus.PENDING.value
    stages: List[StageCheckpoint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "project": self.project,
            "status": self.status,
            "stages": [s.to_dict() for s in self.stages],
            "metadata": self.metadata,
            "created_at": self.created_at or datetime.now().isoformat(),
            "updated_at": self.updated_at or datetime.now().isoformat(),
            "completed_at": self.completed_at,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Task":
        stages = [StageCheckpoint.from_dict(s) for s in d.get("stages", [])]
        return cls(
            id=d["id"],
            name=d["name"],
            project=d["project"],
            status=d.get("status", TaskStatus.PENDING.value),
            stages=stages,
            metadata=d.get("metadata", {}),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
            completed_at=d.get("completed_at"),
            error=d.get("error")
        )


class TaskManager:
    """
    全局任务管理器（单例）

    线程安全，支持多任务并发管理
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, project: str = "default", base_dir: Optional[Path] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, project: str = "default", base_dir: Optional[Path] = None):
        if self._initialized:
            return

        self.project = project
        self.base_dir = base_dir or Path.home() / ".task-manager"
        self.checkpoints_dir = self.base_dir / "checkpoints"
        self.logs_dir = self.base_dir / "logs"
        self.manifest_path = self.base_dir_dir = self.base_dir / "manifest.json"

        # 创建目录
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # 加载 manifest
        self._manifest: Dict = self._load_manifest()
        self._initialized = True

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @base_dir.setter
    def base_dir(self, value: Path):
        self._base_dir = value
        self.checkpoints_dir = value / "checkpoints"
        self.logs_dir = value / "logs"
        self.manifest_path = value / "manifest.json"

    def _load_manifest(self) -> Dict:
        """加载 manifest"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return self._create_empty_manifest()

    def _create_empty_manifest(self) -> Dict:
        """创建空 manifest"""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "projects": {}
        }

    def _save_manifest(self):
        """保存 manifest"""
        self._manifest["updated_at"] = datetime.now().isoformat()
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, ensure_ascii=False, indent=2)

    def _get_project_config(self) -> Dict:
        """获取项目配置"""
        if self.project not in self._manifest.get("projects", {}):
            self._manifest.setdefault("projects", {})[self.project] = {
                "tasks": {},
                "created_at": datetime.now().isoformat()
            }
        return self._manifest["projects"][self.project]

    def _generate_task_id(self, task_name: str) -> str:
        """生成任务 ID"""
        project_config = self._get_project_config()
        tasks = project_config.get("tasks", {})
        existing_ids = [k for k in tasks.keys() if k.startswith(f"{task_name}_")]
        if not existing_ids:
            return f"{task_name}_001"
        max_num = max(int(k.split("_")[-1]) for k in existing_ids)
        return f"{task_name}_{max_num + 1:03d}"

    def _get_checkpoint_dir(self, task_id: str) -> Path:
        """获取任务的检查点目录"""
        return self.checkpoints_dir / task_id

    # ==================== 任务管理 API ====================

    def create_task(
        self,
        task_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        stages: Optional[List[str]] = None
    ) -> Task:
        """
        创建新任务

        Args:
            task_name: 任务名称
            metadata: 任务元数据
            stages: 任务阶段列表

        Returns:
            Task 对象
        """
        task_id = self._generate_task_id(task_name)
        stage_checkpoints = [
            StageCheckpoint(stage_name=s) for s in (stages or ["stage_1"])
        ]

        task = Task(
            id=task_id,
            name=task_name,
            project=self.project,
            status=TaskStatus.PENDING.value,
            stages=stage_checkpoints,
            metadata=metadata or {},
            created_at=datetime.now().isoformat()
        )

        # 保存到 manifest
        project_config = self._get_project_config()
        project_config.setdefault("tasks", {})[task_id] = task.to_dict()

        # 创建检查点目录
        ckpt_dir = self._get_checkpoint_dir(task_id)
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        self._save_manifest()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        project_config = self._get_project_config()
        task_data = project_config.get("tasks", {}).get(task_id)
        if task_data:
            return Task.from_dict(task_data)
        return None

    def update_task(self, task: Task):
        """更新任务"""
        project_config = self._get_project_config()
        project_config["tasks"][task.id] = task.to_dict()
        self._save_manifest()

    def get_resumable_task(self) -> Optional[Task]:
        """获取可恢复的任务"""
        project_config = self._get_project_config()
        tasks = project_config.get("tasks", {})

        for task_id, task_data in tasks.items():
            status = task_data.get("status")
            if status in (TaskStatus.RUNNING.value, TaskStatus.FAILED.value):
                # 检查是否有有效的检查点
                ckpt_dir = self._get_checkpoint_dir(task_id)
                if ckpt_dir.exists() and any(ckpt_dir.iterdir()):
                    return Task.from_dict(task_data)

        return None

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """列出任务"""
        project_config = self._get_project_config()
        tasks = project_config.get("tasks", {})

        result = []
        for task_data in tasks.values():
            if status is None or task_data.get("status") == status:
                result.append(Task.from_dict(task_data))

        return sorted(result, key=lambda t: t.created_at or "")

    def delete_task(self, task_id: str):
        """删除任务"""
        project_config = self._get_project_config()
        if task_id in project_config.get("tasks", {}):
            del project_config["tasks"][task_id]

            # 删除检查点目录
            ckpt_dir = self._get_checkpoint_dir(task_id)
            if ckpt_dir.exists():
                shutil.rmtree(ckpt_dir)

            self._save_manifest()

    # ==================== 阶段检查点 API ====================

    def update_stage_checkpoint(
        self,
        task_id: str,
        stage_name: str,
        status: str,
        processed_count: int = 0,
        total_count: int = 0,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        更新阶段检查点

        Args:
            task_id: 任务 ID
            stage_name: 阶段名称
            status: 阶段状态
            processed_count: 已处理数量
            total_count: 总数量
            data: 阶段数据
            error: 错误信息
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # 查找或创建阶段
        stage = None
        for s in task.stages:
            if s.stage_name == stage_name:
                stage = s
                break

        if stage is None:
            stage = StageCheckpoint(stage_name=stage_name)
            task.stages.append(stage)

        stage.status = status
        stage.processed_count = processed_count
        stage.total_count = total_count
        if data:
            stage.data.update(data)
        if error:
            stage.error = error
        stage.updated_at = datetime.now().isoformat()

        # 更新任务状态
        if status == StageStatus.IN_PROGRESS.value and task.status != TaskStatus.RUNNING.value:
            task.status = TaskStatus.RUNNING.value
            task.updated_at = datetime.now().isoformat()
        elif status == StageStatus.COMPLETED.value:
            # 检查是否所有阶段都完成
            all_completed = all(
                s.status == StageStatus.COMPLETED.value for s in task.stages
            )
            if all_completed:
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.now().isoformat()
        elif status == StageStatus.FAILED.value:
            task.status = TaskStatus.FAILED.value
            task.error = error

        # 保存检查点文件
        ckpt_dir = self._get_checkpoint_dir(task_id)
        ckpt_file = ckpt_dir / f"{stage_name}.json"
        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump(stage.to_dict(), f, ensure_ascii=False, indent=2)

        self.update_task(task)

    def get_stage_checkpoint(self, task_id: str, stage_name: str) -> Optional[StageCheckpoint]:
        """获取阶段检查点"""
        task = self.get_task(task_id)
        if not task:
            return None

        for stage in task.stages:
            if stage.stage_name == stage_name:
                return stage

        # 尝试从检查点文件加载
        ckpt_file = self._get_checkpoint_dir(task_id) / f"{stage_name}.json"
        if ckpt_file.exists():
            with open(ckpt_file, "r", encoding="utf-8") as f:
                return StageCheckpoint.from_dict(json.load(f))

        return None

    def get_latest_checkpoint(self, task_id: str) -> Optional[StageCheckpoint]:
        """获取最新的检查点（用于恢复）"""
        task = self.get_task(task_id)
        if not task:
            return None

        # 返回第一个未完成或最近的阶段
        for stage in task.stages:
            if stage.status != StageStatus.COMPLETED.value:
                return stage

        # 所有阶段都完成了，返回最后一个
        return task.stages[-1] if task.stages else None

    # ==================== 任务执行辅助 ====================

    def save_checkpoint_data(
        self,
        task_id: str,
        stage_name: str,
        key: str,
        value: Any
    ):
        """
        保存检查点数据（用于恢复时的中间状态）

        Args:
            task_id: 任务 ID
            stage_name: 阶段名称
            key: 数据键
            value: 数据值
        """
        ckpt_dir = self._get_checkpoint_dir(task_id)
        data_file = ckpt_dir / f"{stage_name}_{key}.json"

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)

    def load_checkpoint_data(self, task_id: str, stage_name: str, key: str) -> Any:
        """加载检查点数据"""
        ckpt_dir = self._get_checkpoint_dir(task_id)
        data_file = ckpt_dir / f"{stage_name}_{key}.json"

        if data_file.exists():
            with open(data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def clear_task_checkpoints(self, task_id: str):
        """清除任务的检查点（用于重新开始）"""
        ckpt_dir = self._get_checkpoint_dir(task_id)
        if ckpt_dir.exists():
            shutil.rmtree(ckpt_dir)
            ckpt_dir.mkdir(parents=True, exist_ok=True)

        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.PENDING.value
            for stage in task.stages:
                stage.status = StageStatus.PENDING.value
                stage.processed_count = 0
                stage.data = {}
            self.update_task(task)

    # ==================== 文件变更检测 ====================

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """计算文件内容的 MD5 哈希"""
        if not file_path.exists():
            return ""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def check_file_changed(
        self,
        file_path: Path,
        task_id: str,
        key: str = "default"
    ) -> bool:
        """
        检查文件是否已变更

        Returns:
            True if file is new or changed, False if unchanged
        """
        current_hash = self.compute_file_hash(file_path)
        stored_hash = self.load_checkpoint_data(task_id, "file_hashes", key)

        if stored_hash is None:
            return True

        return current_hash != stored_hash

    def mark_file_processed(
        self,
        file_path: Path,
        task_id: str,
        key: str = "default"
    ):
        """标记文件已处理（保存 hash）"""
        current_hash = self.compute_file_hash(file_path)

        # 加载现有的 hash 映射
        hashes = self.load_checkpoint_data(task_id, "file_hashes", "mapping") or {}

        # 更新
        hashes[key] = current_hash

        # 保存
        self.save_checkpoint_data(task_id, "file_hashes", "mapping", hashes)


# ==================== 便捷函数 ====================

def get_task_manager(project: str = "rag-service", base_dir: Optional[Path] = None) -> TaskManager:
    """获取任务管理器实例"""
    return TaskManager(project=project, base_dir=base_dir)


def create_indexing_task(
    data_dir: Path,
    project: str = "rag-service"
) -> Task:
    """创建索引任务"""
    tm = get_task_manager(project=project)

    # 统计文件数量
    files = list(data_dir.rglob("*.txt")) if data_dir.exists() else []
    # 过滤隐藏文件
    files = [f for f in files if not f.name.startswith('.')]

    return tm.create_task(
        task_name="indexing",
        metadata={
            "data_dir": str(data_dir),
            "total_files": len(files)
        },
        stages=["load", "preprocess", "translate", "chunk", "embed", "index"]
    )


def create_batch_preprocess_task(
    data_dir: Path,
    project: str = "rag-service"
) -> Task:
    """创建批量预处理任务"""
    tm = get_task_manager(project=project)

    files = list(data_dir.rglob("*.txt")) if data_dir.exists() else []
    files = [f for f in files if not f.name.startswith('.')]

    return tm.create_task(
        task_name="batch_preprocess",
        metadata={
            "data_dir": str(data_dir),
            "total_files": len(files)
        },
        stages=["load", "clean", "detect_lang", "separate", "dedup", "translate", "chunk"]
    )
