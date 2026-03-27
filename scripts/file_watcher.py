#!/usr/bin/env python3
"""
File watcher for automatic incremental indexing, persona extraction, and few-shot generation.
Monitors data directory for new/modified .txt files and triggers:
1. RAG vector indexing
2. Oscar persona profile update
3. Few-shot examples extraction

Usage: python scripts/file_watcher.py
"""

import os
import sys
import time
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.indexing import IndexingPipeline
from scripts.extract_persona import OscarPersonaExtractor
from scripts.extract_fewshot import FewShotExtractor
from config import settings


class IndexingEventHandler(FileSystemEventHandler):
    """Handler that triggers incremental indexing and persona/fewshot extraction on file changes."""

    def __init__(self, pipeline: IndexingPipeline, persona_extractor: OscarPersonaExtractor, fewshot_extractor: FewShotExtractor, debounce_seconds: int = 5):
        self.pipeline = pipeline
        self.persona_extractor = persona_extractor
        self.fewshot_extractor = fewshot_extractor
        self.debounce_seconds = debounce_seconds
        self.pending_files: dict = {}  # path -> last modified time
        self.lock = threading.Lock()
        self.indexing_thread = None

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith('.txt'):
            return
        self._schedule_indexing(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith('.txt'):
            return
        print(f"[{datetime.now().strftime('%H:%M:%S')}] New file detected: {event.src_path}")
        self._schedule_indexing(event.src_path)

    def _schedule_indexing(self, file_path: str):
        """Debounce file changes and schedule indexing."""
        with self.lock:
            self.pending_files[file_path] = time.time()

        # Schedule indexing after debounce period
        threading.Thread(target=self._delayed_index, args=(file_path,), daemon=True).start()

    def _delayed_index(self, file_path: str):
        """Wait for debounce period then check if still pending."""
        time.sleep(self.debounce_seconds)

        with self.lock:
            last_modified = self.pending_files.get(file_path)
            if last_modified is None:
                return
            # Check if file has been modified since
            try:
                current_mtime = os.path.getmtime(file_path)
                if current_mtime > last_modified:
                    return  # File modified again
            except OSError:
                return  # File no longer exists

            del self.pending_files[file_path]

        # Perform incremental indexing
        self._run_indexing(file_path)

    def _run_indexing(self, file_path: str = None):
        """Run incremental indexing and persona extraction."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting incremental indexing...")

        try:
            # Index specific file or all
            if file_path:
                result = self.pipeline.index_single_file(Path(file_path))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Indexed {Path(file_path).name}: {result} chunks")
            else:
                result = self.pipeline.index_all(recreate_collection=False, incremental=True)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Indexed: {result['new']} new, {result['skipped']} skipped, {result['chunks']} total chunks")

            # Update persona profile after indexing
            self._update_persona()
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Indexing error: {e}")

    def _update_persona(self):
        """Update Oscar persona profile and few-shot examples after new data."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating Oscar persona profile...")
        try:
            self.persona_extractor.load_transcripts()
            self.persona_extractor.analyze_question_types()
            self.persona_extractor.analyze_techniques()
            self.persona_extractor.analyze_interventions()
            self.persona_extractor.analyze_dialectical_moves()
            self.persona_extractor.extract_response_patterns()
            profile = self.persona_extractor.save_results()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Persona updated: {profile['statistics']['philosopher_lines_analyzed']} lines analyzed")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Persona update error: {e}")

        # Also update few-shot examples
        self._update_fewshot()

    def _update_fewshot(self):
        """Update few-shot examples after new data."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating few-shot examples...")
        try:
            turns = self.fewshot_extractor.load_transcripts()
            snippets = self.fewshot_extractor.extract_snippets(turns)
            examples = self.fewshot_extractor.build_consultation_examples(turns, snippets)
            prompts = self.fewshot_extractor.generate_fewshot_prompts(examples)
            self.fewshot_extractor.save_results(snippets, examples, prompts)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Few-shot updated: {len(examples)} examples, {len(prompts)} prompts")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Few-shot update error: {e}")


def start_watching(data_dir: str = None, debounce: int = 5):
    """Start file watcher for the data directory."""
    data_dir = Path(data_dir or settings.RAW_DATA_DIR)

    if not data_dir.exists():
        print(f"Data directory does not exist: {data_dir}")
        return

    pipeline = IndexingPipeline()
    persona_extractor = OscarPersonaExtractor()
    fewshot_extractor = FewShotExtractor()
    event_handler = IndexingEventHandler(pipeline, persona_extractor, fewshot_extractor, debounce_seconds=debounce)

    observer = Observer()
    observer.schedule(event_handler, str(data_dir), recursive=True)
    observer.start()

    print(f"=" * 60)
    print(f"File Watcher Started")
    print(f"=" * 60)
    print(f"Monitoring: {data_dir}")
    print(f"Debounce: {debounce} seconds")
    print(f"Auto-actions: [1] RAG indexing [2] Oscar persona [3] Few-shot examples")
    print(f"Press Ctrl+C to stop")
    print(f"=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopping watcher...")
        observer.stop()
    observer.join()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Watcher stopped")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="File watcher for incremental indexing")
    parser.add_argument("--data-dir", default=None, help="Data directory to watch")
    parser.add_argument("--debounce", type=int, default=5, help="Debounce seconds before indexing")
    args = parser.parse_args()

    start_watching(args.data_dir, args.debounce)
