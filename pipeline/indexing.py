import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set
from tqdm import tqdm

from core.chunker import TextChunker, Chunk
from core.translator import Translator
from core.embedder import Embedder
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

        self.chunker = TextChunker(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
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

    def index_single_file(
        self,
        file_path: Path,
        batch_size: int = 10
    ) -> int:
        """Index a single file."""
        print(f"Processing: {file_path.name}")

        # Delete old points for this file if they exist
        self._delete_source_points(file_path.name)

        # Chunk text
        chunks = self.chunker.chunk_file(str(file_path))
        print(f"  Split into {len(chunks)} chunks")

        # Extract English texts
        english_texts = [chunk.text for chunk in chunks]

        # Translate to Chinese (batch)
        try:
            chinese_texts = self.translator.translate_batch_sync(english_texts)
            print(f"  Translated {len(chinese_texts)} chunks")
        except Exception as e:
            print(f"  Translation failed: {e}, using empty strings")
            chinese_texts = [""] * len(english_texts)

        # Generate dense embedding from English (cross-lingual semantic matching)
        dense_embeddings = self.embedder.embed_dense(english_texts)
        print(f"  Generated dense embeddings (English)")

        # Generate sparse embedding from Chinese (keyword matching for Chinese queries)
        if any(chinese_texts):
            sparse_embeddings = self.embedder.embed_sparse(chinese_texts)
        else:
            sparse_embeddings = [{} for _ in english_texts]
        print(f"  Generated sparse embeddings (Chinese)")

        # Prepare points for Qdrant
        points = []
        for i, (chunk, text_en, text_zh) in enumerate(
            zip(chunks, english_texts, chinese_texts)
        ):
            point = {
                "id": hash(f"{file_path.name}_{i}") % (10**12),  # Numeric ID
                "text_en": text_en,
                "text_zh": text_zh,
                "source": file_path.name,
                "chunk_index": i,
                "dense_vector": dense_embeddings[i] if isinstance(dense_embeddings[0], list) else dense_embeddings,
                "sparse_vector": sparse_embeddings[i] if isinstance(sparse_embeddings, list) else sparse_embeddings
            }
            points.append(point)

        # Upsert to Qdrant
        self.qdrant.upsert_points(points)
        print(f"  Indexed {len(points)} points")

        return len(points)

    def index_all(
        self,
        recreate_collection: bool = False,
        incremental: bool = True
    ) -> Dict[str, int]:
        """
        Index all files in the data directory.

        Args:
            recreate_collection: If True, delete and recreate the entire collection
            incremental: If True, only index new/modified files
        """
        manifest = self._load_manifest() if incremental else {}

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
                continue

        # Save updated manifest
        self._save_manifest(manifest)

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

    def rebuild_index(self) -> Dict[str, int]:
        """Force rebuild of entire index."""
        return self.index_all(recreate_collection=True, incremental=False)
