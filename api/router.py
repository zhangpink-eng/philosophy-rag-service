from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import AsyncIterator, Optional
import asyncio
import os

from api.schemas import (
    QueryRequest,
    QueryResponse,
    StreamQueryRequest,
    IndexRequest,
    IndexResponse,
    PreprocessRequest,
    PreprocessResponse,
    HealthResponse,
    ErrorResponse
)
from pipeline.indexing import IndexingPipeline
from pipeline.retrieval import RetrievalPipeline

router = APIRouter()

# Global pipeline instances (lazy initialization)
_retrieval_pipeline = None
_indexing_pipeline = None


def get_retrieval_pipeline() -> RetrievalPipeline:
    """Get or create retrieval pipeline singleton."""
    global _retrieval_pipeline
    if _retrieval_pipeline is None:
        _retrieval_pipeline = RetrievalPipeline()
    return _retrieval_pipeline


def get_indexing_pipeline() -> IndexingPipeline:
    """Get or create indexing pipeline singleton."""
    global _indexing_pipeline
    if _indexing_pipeline is None:
        _indexing_pipeline = IndexingPipeline()
    return _indexing_pipeline


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Query the RAG system and get an answer with sources.

    Args:
        request: Query request with question

    Returns:
        Answer with source documents
    """
    try:
        pipeline = get_retrieval_pipeline()
        # Get sources via sync retrieve
        docs = pipeline.retrieve(request.query)
        # Generate answer via async
        answer = await pipeline.generate(request.query, use_stream=False)

        sources = [
            {"text_zh": d["text_zh"], "text_en": d["text_en"], "source": d["source"], "score": d.get("rerank_score", d.get("score", 0))}
            for d in docs
        ]

        return QueryResponse(
            answer=answer,
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/query/stream")
async def query_stream(request: StreamQueryRequest):
    """
    Query the RAG system with streaming response.

    Args:
        request: Query request with question

    Returns:
        Streaming text response
    """
    async def generate_stream() -> AsyncIterator[str]:
        try:
            pipeline = get_retrieval_pipeline()

            # Send headers for SSE
            yield "data: "

            async for chunk in pipeline.generate_stream(request.query):
                # Format as SSE
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0)  # Yield control

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/api/preprocess", response_model=PreprocessResponse)
async def preprocess_text(request: PreprocessRequest) -> PreprocessResponse:
    """
    Preprocess text content.

    Args:
        request: Preprocess request with text

    Returns:
        Preprocessing result with language detection and text separation
    """
    from core.preprocessor import Preprocessor, analyze_document

    try:
        # 分析文档结构
        doc_analysis = analyze_document(request.text)
        language = doc_analysis['language']
        is_bilingual = language in ('bilingual', 'zh_en_mixed')

        if is_bilingual:
            # bilingual 格式：分离处理，不翻译
            preprocessor = Preprocessor()
            preprocessor.chunker.max_chunk_size = 512
            preprocessor.chunker.overlap = 64

            # 分离后的中英文内容
            text_zh = doc_analysis.get('text_zh', '') or ''
            text_en = doc_analysis.get('text_en', '') or ''

            # 分别分块
            zh_paras = [p.strip() for p in text_zh.split('\n\n') if p.strip()]
            en_paras = [p.strip() for p in text_en.split('\n\n') if p.strip()]

            zh_chunks = preprocessor.chunker.chunk_paragraphs(zh_paras, preserve_pairs=True)
            en_chunks = preprocessor.chunker.chunk_paragraphs(en_paras, preserve_pairs=True)

            final_chunks = len(zh_chunks) + len(en_chunks)

            return PreprocessResponse(
                language=language,
                is_bilingual=True,
                text_zh=text_zh[:500] + ('...' if len(text_zh) > 500 else ''),
                text_en=text_en[:500] + ('...' if len(text_en) > 500 else ''),
                stats=doc_analysis['stats'],
                chunks_zh=len(zh_chunks),
                chunks_en=len(en_chunks),
                final_chunks=final_chunks,
                message=f"Bilingual format detected: {len(zh_paras)} zh paragraphs, {len(en_paras)} en paragraphs"
            )
        else:
            # 单语言文件：使用完整 Preprocessor 处理（可能需要翻译）
            preprocessor = Preprocessor()
            file_name = request.file_name or "temp.txt"

            # 临时写入文件
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(request.text)
                temp_path = Path(f.name)

            try:
                result = preprocessor.process_file(temp_path)
                metadata = result['metadata']

                return PreprocessResponse(
                    language=language,
                    is_bilingual=False,
                    text_zh=request.text[:500] + ('...' if len(request.text) > 500 else '') if language in ('zh', 'mixed') else '',
                    text_en=request.text[:500] + ('...' if len(request.text) > 500 else '') if language in ('en', 'mixed') else '',
                    stats={
                        "zh_paragraphs": metadata.zh_paragraphs,
                        "en_paragraphs": metadata.en_paragraphs,
                        "zh_chars": sum(len(p) for p in (request.text[:500] for _ in range(1))) if metadata.zh_paragraphs > 0 else 0,
                        "en_chars": sum(len(p) for p in (request.text[:500] for _ in range(1))) if metadata.en_paragraphs > 0 else 0,
                        "is_bilingual": False,
                        "total_paragraphs": metadata.zh_paragraphs + metadata.en_paragraphs
                    },
                    chunks_zh=metadata.zh_chunks,
                    chunks_en=metadata.en_chunks,
                    final_chunks=metadata.final_chunks,
                    message=f"Language: {language}, translated if needed"
                )
            finally:
                temp_path.unlink(missing_ok=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/index", response_model=IndexResponse)
async def index_documents(
    request: IndexRequest,
    background_tasks: BackgroundTasks
) -> IndexResponse:
    """
    Trigger document indexing.

    Args:
        request: Index configuration

    Returns:
        Indexing status
    """
    try:
        pipeline = get_indexing_pipeline()

        # Run indexing in background if it might take long
        if request.data_dir:
            pipeline.data_dir = request.data_dir

        if request.recreate:
            # Full rebuild uses zero-downtime approach
            result = pipeline.rebuild_index_zero_downtime()
            msg = f"Zero-downtime rebuild: indexed {result['files']} files, {result['chunks']} chunks"
        else:
            # Incremental indexing
            result = pipeline.index_all(
                recreate_collection=False,
                incremental=request.incremental
            )
            msg = f"Indexed {result['new']} new/modified files, skipped {result['skipped']} unchanged files"

        return IndexResponse(
            status="success",
            files=result["files"],
            chunks=result["chunks"],
            skipped=result.get("skipped", 0),
            new=result.get("new", 0),
            message=msg
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Service health status
    """
    try:
        pipeline = get_indexing_pipeline()
        stats = pipeline.get_stats()

        models_loaded = True
        try:
            # Try to use embedder to check if models are loaded
            _ = pipeline.embedder.embed("test")
        except Exception:
            models_loaded = False

        return HealthResponse(
            status="healthy" if not stats.get("error") else "degraded",
            collection=stats,
            models_loaded=models_loaded
        )

    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            collection={"error": str(e)},
            models_loaded=False
        )


@router.get("/api/stats")
async def get_stats():
    """Get collection statistics."""
    try:
        pipeline = get_indexing_pipeline()
        stats = pipeline.get_stats()

        # Get file list from data directory
        data_dir = pipeline.data_dir
        files = []
        if data_dir.exists():
            for f in data_dir.glob("**/*.txt"):
                files.append({
                    "name": f.name,
                    "path": str(f.relative_to(data_dir)),
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime
                })

        # Return simplified stats
        return {
            "manifest_files": stats.get("manifest_files", 0),
            "qdrant_points": stats.get("qdrant", {}).get("points_count", 0),
            "status": stats.get("qdrant", {}).get("status", "unknown"),
            "points_count": stats.get("qdrant", {}).get("points_count", 0),
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/files")
async def list_files():
    """List all available files in data directory."""
    try:
        pipeline = get_indexing_pipeline()
        data_dir = pipeline.data_dir
        files = []

        if data_dir.exists():
            for f in sorted(data_dir.glob("**/*.txt")):
                files.append({
                    "name": f.name,
                    "path": str(f.relative_to(data_dir)),
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime
                })

        return {
            "count": len(files),
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/index/progress")
async def get_index_progress():
    """Get current indexing progress."""
    try:
        from core.index_progress import index_progress
        state = index_progress.get_state()

        # Get pipeline stats
        pipeline = get_indexing_pipeline()
        stats = pipeline.get_stats()
        manifest = stats.get("manifest", {})

        # Calculate total indexed points from manifest + current completed files
        manifest_count = len(manifest)
        total_indexed_points = sum(v.get("chunks", 0) for v in manifest.values())

        # Add chunks from files that are completed in current run but not yet in manifest
        current_files = state.get("files", {})
        for filename, info in current_files.items():
            if info.get("status") == "completed" and info.get("chunks", 0) > 0:
                # Check if this file is already in manifest
                if filename not in manifest:
                    total_indexed_points += info.get("chunks", 0)

        return {
            "is_running": state["is_running"],
            "total_files": state["total_files"],
            "completed_files": state["completed_files"],
            "current_file": state["current_file"],
            "elapsed_seconds": state["elapsed_seconds"],
            "progress_percent": index_progress.get_progress_percent(),
            "points_count": total_indexed_points,
            "manifest_count": manifest_count,
            "files": state["files"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/retrieve/compare")
async def retrieve_compare(request: QueryRequest):
    """
    Compare retrieval results before and after reranking.

    Returns retrieval results showing the difference reranking makes.
    """
    try:
        pipeline = get_retrieval_pipeline()
        comparison = pipeline.retrieve_with_comparison(request.query)

        def apply_fallback(d):
            """If text_zh is empty, use text_en as fallback"""
            zh = d.get("text_zh") or ""
            en = d.get("text_en") or ""
            return {
                "text_zh": zh if zh else en,
                "text_en": en,
                "source": d.get("source", ""),
            }

        before_rerank = [
            {
                **apply_fallback(d),
                "rank": i + 1,
                "score": d.get("score", 0),
                "dense_score": d.get("dense_score", 0),
                "sparse_score": d.get("sparse_score", 0)
            }
            for i, d in enumerate(comparison["before_rerank"])
        ]

        after_rerank = [
            {
                **apply_fallback(d),
                "rank": i + 1,
                "rerank_score": d.get("rerank_score", 0),
                "original_rank": comparison["before_rerank"].index(d) + 1 if d in comparison["before_rerank"] else -1
            }
            for i, d in enumerate(comparison["after_rerank"])
        ]

        return {
            "query": comparison["query"],
            "before_rerank": before_rerank,
            "after_rerank": after_rerank
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
