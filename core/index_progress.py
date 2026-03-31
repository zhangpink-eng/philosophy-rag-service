"""
Indexing progress tracker with file-based sharing.
"""
import threading
import time
import json
import os
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


class IndexProgressTracker:
    """Thread-safe progress tracker with file persistence."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._state_file = Path("/tmp/index_progress.json")
        self._files: Dict[str, Dict] = {}
        self._current_file: Optional[str] = None
        self._total_files: int = 0
        self._completed_files: int = 0
        self._is_running: bool = False
        self._started_at: Optional[float] = None
        self._mu = threading.Lock()

        # Load existing state if any
        self._load_from_file()

    def _load_from_file(self):
        """Load state from file."""
        try:
            if self._state_file.exists():
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                    self._files = data.get('files', {})
                    self._total_files = data.get('total_files', 0)
                    self._completed_files = data.get('completed_files', 0)
                    self._is_running = data.get('is_running', False)
                    self._started_at = data.get('started_at')
        except Exception:
            pass

    def _save_to_file(self):
        """Save state to file."""
        try:
            with open(self._state_file, 'w') as f:
                json.dump({
                    'files': self._files,
                    'total_files': self._total_files,
                    'completed_files': self._completed_files,
                    'current_file': self._current_file,
                    'is_running': self._is_running,
                    'started_at': self._started_at
                }, f)
        except Exception:
            pass

    def start(self, file_names: List[str]):
        """Start tracking progress for a list of files."""
        with self._mu:
            self._files = {name: {"status": "pending", "stage": "", "stage_progress": 0, "total_chunks": 0, "chunks": 0, "error": ""} for name in file_names}
            self._current_file = None
            self._total_files = len(file_names)
            self._completed_files = 0
            self._is_running = True
            self._started_at = time.time()
            self._save_to_file()

    def start_file(self, file_name: str):
        """Mark a file as started processing."""
        with self._mu:
            self._current_file = file_name
            if file_name in self._files:
                self._files[file_name]["status"] = "processing"
                self._files[file_name]["stage"] = "分块中"
                self._files[file_name]["stage_progress"] = 0
            self._save_to_file()

    def update_stage(self, file_name: str, stage: str, progress: int = 0, total: int = 0):
        """Update the current processing stage for a file."""
        with self._mu:
            if file_name in self._files:
                self._files[file_name]["stage"] = stage
                self._files[file_name]["stage_progress"] = progress
                if total > 0:
                    self._files[file_name]["total_chunks"] = total
            self._save_to_file()

    def complete_file(self, file_name: str, chunks: int = 0):
        """Mark a file as completed."""
        with self._mu:
            if file_name in self._files:
                self._files[file_name]["status"] = "completed"
                self._files[file_name]["chunks"] = chunks
            self._completed_files += 1
            if self._current_file == file_name:
                self._current_file = None
            self._save_to_file()

    def error_file(self, file_name: str, error: str):
        """Mark a file as errored."""
        with self._mu:
            if file_name in self._files:
                self._files[file_name]["status"] = "error"
                self._files[file_name]["error"] = error
            if self._current_file == file_name:
                self._current_file = None
            self._save_to_file()

    def stop(self):
        """Stop tracking."""
        with self._mu:
            self._is_running = False
            self._save_to_file()

    def get_state(self) -> Dict:
        """Get current progress state."""
        with self._mu:
            # Always reload from file to get latest state
            self._load_from_file()

            elapsed = time.time() - self._started_at if self._started_at else 0

            return {
                "is_running": self._is_running,
                "total_files": self._total_files,
                "completed_files": self._completed_files,
                "current_file": self._current_file,
                "elapsed_seconds": elapsed,
                "files": self._files.copy()
            }

    def get_progress_percent(self) -> float:
        """Get overall progress percentage."""
        with self._mu:
            self._load_from_file()
            if self._total_files == 0:
                return 0
            return (self._completed_files / self._total_files) * 100


# Global singleton instance
index_progress = IndexProgressTracker()
