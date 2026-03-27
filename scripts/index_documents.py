#!/usr/bin/env python3
"""
Index documents into Qdrant.

Usage:
    python scripts/index_documents.py                    # Index all files in data/raw
    python scripts/index_documents.py --recreate         # Recreate collection
    python scripts/index_documents.py --data-dir ./data   # Custom data directory
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.indexing import IndexingPipeline


def main():
    parser = argparse.ArgumentParser(description="Index documents into Qdrant")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Data directory containing text files"
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate collection before indexing"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size for text splitting"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=64,
        help="Chunk overlap for text splitting"
    )

    args = parser.parse_args()

    # Create pipeline
    pipeline = IndexingPipeline(
        data_dir=args.data_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )

    # Run indexing
    print("Starting document indexing...")
    print(f"Data directory: {pipeline.data_dir}")
    print(f"Chunk size: {args.chunk_size}, overlap: {args.chunk_overlap}")
    print("-" * 50)

    result = pipeline.index_all(recreate_collection=args.recreate)

    print("-" * 50)
    print("Indexing complete!")
    print(f"Files indexed: {result['files']}")
    print(f"Total chunks: {result['chunks']}")

    # Print stats
    stats = pipeline.get_stats()
    print(f"\nCollection info:")
    print(f"  Name: {stats.get('name', 'N/A')}")
    print(f"  Points: {stats.get('points_count', 'N/A')}")
    print(f"  Status: {stats.get('status', 'N/A')}")


if __name__ == "__main__":
    main()
