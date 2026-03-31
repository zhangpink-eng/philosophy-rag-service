import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Optional, Set
from tqdm import tqdm

from core.chunker import SemanticChunker, FixedWindowChunker, Chunk
from core.translator import Translator
from core.embedder import Embedder
from core.index_progress import index_progress
from db.qdrant_client import QdrantClientWrapper
from config import settings


class IndexingPipeline:
    """Offline pipeline for indexing documents into Qdrant."""

    def __init__(
        self,
        data_dir: str = None,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.data_dir = Path(data_dir or settings.RAW_DATA_DIR)
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.manifest_path = self.data_dir / ".index_manifest.json"

        self.chunker = FixedWindowChunker(
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap
        )
        self.translator = Translator()
        self.embedder = Embedder()
        self.qdrant = QdrantClientWrapper()

    def _get_file_hash(self, file_path: Path) -> str:
        """Get hash of file content for incremental indexing."""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def _load_manifest(self) -> Dict[str, Dict]:
        """Load the indexing manifest."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_manifest(self, manifest: Dict) -> None:
        """Save the indexing manifest."""
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def _update_manifest_entry(self, file_path: Path, num_chunks: int) -> None:
        """Update a single entry in the manifest after file completion."""
        import hashlib
        manifest = self._load_manifest()
        file_hash = self._get_file_hash(file_path)
        manifest[file_path.name] = {
            "hash": file_hash,
            "chunks": num_chunks,
            "indexed_at": str(file_path.stat().st_mtime)
        }
        self._save_manifest(manifest)
        print(f"  Updated manifest: {file_path.name} ({num_chunks} chunks)")

    def _load_files(self) -> List[Path]:
        """Load all text files from data directory."""
        if not self.data_dir.exists():
            return []

        return list(self.data_dir.glob("**/*.txt"))

    def _get_existing_ids(self, source: str) -> Set[int]:
        """Get all point IDs for a given source file."""
        # This would require a Qdrant scroll query
        # For now, we'll rebuild IDs based on chunk count
        return set()

    def _delete_source_points(self, source: str) -> bool:
        """Delete all points for a given source file."""
        try:
            # Use delete by filter - delete all points where source == filename
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            self.qdrant.client.delete(
                collection_name=self.qdrant.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="source",
                            match=MatchValue(value=source)
                        )
                    ]
                )
            )
            return True
        except Exception as e:
            print(f"  Warning: Could not delete old points: {e}")
            return False

    def _is_chinese_text(self, text: str) -> bool:
        """Check if text is primarily Chinese (>50% Chinese characters, excluding punctuation)."""
        if not text:
            return False
        # Count Chinese characters (excluding common punctuation)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # Count non-punctuation characters for more accurate ratio
        non_punct = sum(1 for c in text if c.isalnum() or '\u4e00' <= c <= '\u9fff')
        if non_punct == 0:
            return False
        return chinese_chars / non_punct > 0.5

    def _is_chinese_file(self, texts: List[str]) -> bool:
        """Check if ALL texts in a file are primarily Chinese.

        Uses majority rule: if >50% of chunks have >50% Chinese characters,
        the file is considered Chinese and translation is skipped.
        """
        if not texts:
            return False
        chinese_chunk_count = sum(1 for text in texts if self._is_chinese_text(text))
        return chinese_chunk_count / len(texts) > 0.5

    def index_single_file(
        self,
        file_path: Path,
        batch_size: int = 10
    ) -> int:
        """Index a single file."""
        from core.preprocessor import analyze_document

        file_name = file_path.name
        print(f"Processing: {file_name}")

        # Report progress: starting this file
        index_progress.start_file(file_name)

        # Delete old points for this file if they exist
        self._delete_source_points(file_name)

        # Read raw file content
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Analyze document structure (bilingual detection)
        doc_analysis = analyze_document(raw_content)
        is_bilingual = doc_analysis['language'] == 'bilingual'

        if is_bilingual:
            print(f"  检测到双语格式: 中文{doc_analysis['stats']['zh_paragraphs']}段, 英文{doc_analysis['stats']['en_paragraphs']}段")
            # For bilingual files: chunk each language separately
            return self._index_bilingual_file(file_path, doc_analysis)
        else:
            # For monolingual files: use existing logic
            return self._index_monolingual_file(file_path)

    def _index_bilingual_file(
        self,
        file_path: Path,
        doc_analysis: dict
    ) -> int:
        """Index a bilingual file by chunking each language separately."""
        file_name = file_path.name

        # Get separated content
        zh_content = doc_analysis['text_zh']
        en_content = doc_analysis['text_en']

        # Chunk each language separately
        zh_chunks = self.chunker.chunk_text(zh_content, file_name)
        en_chunks = self.chunker.chunk_text(en_content, file_name)

        print(f"  中文: {len(zh_chunks)} chunks, 英文: {len(en_chunks)} chunks")

        # Create points with proper text_zh/text_en assignment
        points = []

        # Chinese chunks: text_zh = text, text_en = empty
        for i, chunk in enumerate(zh_chunks):
            zh_text = chunk.text
            en_text = ""

            point = {
                "id": hash(f"{file_name}_zh_{i}") % (10**12),
                "text_en": en_text,
                "text_zh": zh_text,
                "source": file_name,
                "chunk_index": i,
                "language": "zh"
            }
            points.append(point)

        # English chunks: text_zh = empty, text_en = text
        for i, chunk in enumerate(en_chunks):
            zh_text = ""
            en_text = chunk.text

            point = {
                "id": hash(f"{file_name}_en_{i}") % (10**12),
                "text_en": en_text,
                "text_zh": zh_text,
                "source": file_name,
                "chunk_index": len(zh_chunks) + i,
                "language": "en"
            }
            points.append(point)

        # Generate embeddings for each language
        zh_texts = [p["text_zh"] for p in points if p["text_zh"]]
        en_texts = [p["text_en"] for p in points if p["text_en"]]

        # Dense embeddings
        index_progress.update_stage(file_name, "Embedding向量中", 0, len(points))
        zh_dense = self.embedder.embed_dense(zh_texts) if zh_texts else []
        en_dense = self.embedder.embed_dense(en_texts) if en_texts else []
        print(f"  Generated dense embeddings")
        index_progress.update_stage(file_name, "Embedding向量中", len(points), len(points))

        # Sparse embeddings
        index_progress.update_stage(file_name, "Sparse向量中", 0, len(points))
        zh_sparse = self.embedder.embed_sparse(zh_texts) if zh_texts else []
        en_sparse = self.embedder.embed_sparse(en_texts) if en_texts else []
        print(f"  Generated sparse embeddings")
        index_progress.update_stage(file_name, "Sparse向量完成", len(points), len(points))

        # Assign embeddings to points
        zh_idx, en_idx = 0, 0
        for point in points:
            if point["text_zh"]:
                point["dense_vector"] = zh_dense[zh_idx] if isinstance(zh_dense[0], list) else zh_dense
                point["sparse_vector"] = zh_sparse[zh_idx] if isinstance(zh_sparse, list) and zh_sparse else {}
                zh_idx += 1
            else:
                point["dense_vector"] = en_dense[en_idx] if isinstance(en_dense[0], list) else en_dense
                point["sparse_vector"] = en_sparse[en_idx] if isinstance(en_sparse, list) and en_sparse else {}
                en_idx += 1

        # Upsert to Qdrant
        index_progress.update_stage(file_name, "索引入库中", 0, len(points))
        self.qdrant.upsert_points(points)
        print(f"  Indexed {len(points)} points")
        index_progress.update_stage(file_name, "索引完成", len(points), len(points))

        # Report progress
        index_progress.complete_file(file_name, len(points))
        self._update_manifest_entry(file_path, len(points))

        return len(points)

    def _index_monolingual_file(
        self,
        file_path: Path
    ) -> int:
        """Index a monolingual file (existing logic)."""
        file_name = file_path.name

        # Chunk text
        index_progress.update_stage(file_name, "分块中", 0, 0)
        chunks = self.chunker.chunk_file(str(file_path))
        print(f"  Split into {len(chunks)} chunks")
        index_progress.update_stage(file_name, "分块完成", len(chunks), len(chunks))

        # Extract English texts
        english_texts = [chunk.text for chunk in chunks]

        # Check if text is primarily Chinese - skip translation if so
        is_chinese = self._is_chinese_file(english_texts)

        # Translate to Chinese (batch) unless already Chinese
        if is_chinese:
            index_progress.update_stage(file_name, "跳过翻译(原文中文)", 0, len(chunks))
            chinese_texts = english_texts.copy()
            print(f"  Skipped translation - source text is Chinese")
        else:
            index_progress.update_stage(file_name, "翻译中", 0, len(chunks))
            try:
                chinese_texts = self.translator.translate_batch_sync(english_texts)
                print(f"  Translated {len(chinese_texts)} chunks")
            except Exception as e:
                print(f"  Translation failed: {e}, using empty strings")
                chinese_texts = [""] * len(english_texts)
            index_progress.update_stage(file_name, "翻译完成", len(chunks), len(chunks))

        # Generate dense embedding from English (cross-lingual semantic matching)
        index_progress.update_stage(file_name, "Embedding向量中", 0, len(chunks))
        dense_embeddings = self.embedder.embed_dense(english_texts)
        print(f"  Generated dense embeddings (English)")
        index_progress.update_stage(file_name, "Embedding向量中", len(chunks), len(chunks))

        # Generate sparse embedding from Chinese (keyword matching for Chinese queries)
        index_progress.update_stage(file_name, "Sparse向量中", 0, len(chunks))
        if any(chinese_texts):
            sparse_embeddings = self.embedder.embed_sparse(chinese_texts)
        else:
            sparse_embeddings = [{} for _ in english_texts]
        print(f"  Generated sparse embeddings (Chinese)")
        index_progress.update_stage(file_name, "Sparse向量完成", len(chunks), len(chunks))

        # Prepare points for Qdrant
        index_progress.update_stage(file_name, "索引入库中", 0, len(chunks))
        points = []
        for i, (chunk, text_en, text_zh) in enumerate(
            zip(chunks, english_texts, chinese_texts)
        ):
            point = {
                "id": hash(f"{file_path.name}_{i}") % (10**12),  # Numeric ID
                "text_en": text_en,
                "text_zh": text_zh,
                "source": file_name,
                "chunk_index": i,
                "language": "zh" if is_chinese else "en",
                "dense_vector": dense_embeddings[i] if isinstance(dense_embeddings[0], list) else dense_embeddings,
                "sparse_vector": sparse_embeddings[i] if isinstance(sparse_embeddings, list) else sparse_embeddings
            }
            points.append(point)

        # Upsert to Qdrant
        self.qdrant.upsert_points(points)
        print(f"  Indexed {len(points)} points")
        index_progress.update_stage(file_name, "索引完成", len(chunks), len(chunks))

        # Report progress: completed this file
        index_progress.complete_file(file_name, len(points))

        # Update manifest incrementally (save after each file to prevent data loss)
        self._update_manifest_entry(file_path, len(points))

        return len(points)

    def index_all(
        self,
        recreate_collection: bool = False,
        incremental: bool = True,
        target_collection: str = None
    ) -> Dict[str, int]:
        """
        Index all files in the data directory.

        Args:
            recreate_collection: If True, delete and recreate the entire collection
            incremental: If True, only index new/modified files
            target_collection: Optional specific collection to index into
        """
        manifest = self._load_manifest() if incremental else {}

        # Use specific collection if provided
        if target_collection:
            original_collection = self.qdrant.collection_name
            self.qdrant.set_active_collection(target_collection)
        else:
            original_collection = None

        # Create collection if needed
        if recreate_collection:
            self.qdrant.create_collection(force_recreate=True)
            manifest = {}  # Clear manifest on full rebuild
        else:
            self.qdrant.create_collection(force_recreate=False)

        # Load files
        files = self._load_files()
        print(f"Found {len(files)} files to index")

        if not files:
            print("No files found to index.")
            return {"files": 0, "chunks": 0, "skipped": 0, "new": 0}

        # Initialize progress tracker
        file_names = [f.name for f in files]
        index_progress.start(file_names)

        total_chunks = 0
        indexed_files = 0
        skipped_files = 0
        new_files = 0

        for file_path in tqdm(files, desc="Indexing files"):
            file_hash = self._get_file_hash(file_path)
            file_key = file_path.name

            # Check if file needs indexing
            if incremental and file_key in manifest:
                if manifest[file_key]["hash"] == file_hash:
                    print(f"Skipping (unchanged): {file_path.name}")
                    skipped_files += 1
                    total_chunks += manifest[file_key]["chunks"]
                    index_progress.complete_file(file_key, manifest[file_key]["chunks"])
                    continue

            # File is new or modified - index it
            try:
                num_chunks = self.index_single_file(file_path)
                manifest[file_key] = {
                    "hash": file_hash,
                    "chunks": num_chunks,
                    "indexed_at": str(Path(file_path).stat().st_mtime)
                }
                total_chunks += num_chunks
                indexed_files += 1
                new_files += 1
            except Exception as e:
                print(f"Error indexing {file_path.name}: {e}")
                index_progress.error_file(file_key, str(e))
                continue

        # Stop progress tracker
        index_progress.stop()

        # Save updated manifest
        self._save_manifest(manifest)

        # Restore original collection if we used a target
        if original_collection:
            self.qdrant.set_active_collection(original_collection)

        print(f"\nIndexing complete:")
        print(f"  Files indexed: {indexed_files}")
        print(f"  Files skipped: {skipped_files}")
        print(f"  Total chunks: {total_chunks}")

        return {
            "files": indexed_files,
            "chunks": total_chunks,
            "skipped": skipped_files,
            "new": new_files
        }

    def get_stats(self) -> Dict:
        """Get indexing statistics."""
        manifest = self._load_manifest()
        qdrant_info = self.qdrant.get_collection_info()

        return {
            "manifest_files": len(manifest),
            "manifest": manifest,
            "qdrant": qdrant_info
        }

    def rebuild_index_zero_downtime(self) -> Dict[str, int]:
        """
        Force rebuild of entire index using dual collection approach.

        This creates a new versioned collection, indexes all files into it,
        then atomically switches the alias to point to the new collection.
        Old collection is deleted after successful switch.
        """
        print("=" * 60)
        print("ZERO-DOWNTIME REBUILD")
        print("=" * 60)

        # Step 1: Create new versioned collection
        timestamp = str(int(time.time()))
        new_collection = self.qdrant.create_versioned_collection(version_suffix=timestamp)
        print(f"\n[1/4] Created new collection: {new_collection}")

        # Step 2: Index all files into the new collection
        print(f"\n[2/4] Indexing all files into {new_collection}...")
        result = self.index_all(
            recreate_collection=False,
            incremental=False,
            target_collection=new_collection
        )

        if result["files"] == 0 and result["chunks"] == 0:
            print("\nNo files to index, cleaning up...")
            self.qdrant.delete_collection_by_name(new_collection)
            return {"files": 0, "chunks": 0, "skipped": 0, "new": 0}

        print(f"\n[3/4] Indexed {result['files']} files, {result['chunks']} chunks")

        # Step 3: Atomically switch alias
        print(f"\n[3/4] Switching alias '{self.qdrant.collection_name}' -> {new_collection}")
        success = self.qdrant.switch_collection_alias(new_collection)

        if not success:
            print("WARNING: Alias switch failed! Manual intervention required.")
            print(f"New collection '{new_collection}' is ready to use.")
            return {
                "files": result["files"],
                "chunks": result["chunks"],
                "skipped": 0,
                "new": result["files"],
                "warning": "Alias switch failed, collection is ready but not active"
            }

        print(f"Alias switched successfully!")

        # Step 4: Cleanup old collections (keep latest 2)
        print(f"\n[4/4] Cleaning up old versions...")
        deleted = self.qdrant.cleanup_old_versions(keep_latest=2)
        if deleted:
            print(f"Deleted old collections: {', '.join(deleted)}")
        else:
            print("No old collections to clean up")

        print("\n" + "=" * 60)
        print("REBUILD COMPLETE")
        print("=" * 60)

        return {
            "files": result["files"],
            "chunks": result["chunks"],
            "skipped": 0,
            "new": result["files"]
        }

    def rebuild_index(self) -> Dict[str, int]:
        """Force rebuild of entire index using zero-downtime approach."""
        return self.rebuild_index_zero_downtime()
