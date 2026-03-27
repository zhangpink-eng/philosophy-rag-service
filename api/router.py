from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import AsyncIterator
import asyncio

from api.schemas import (
    QueryRequest,
    QueryResponse,
    StreamQueryRequest,
    IndexRequest,
    IndexResponse,
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

        result = pipeline.index_all(
            recreate_collection=request.recreate,
            incremental=request.incremental
        )

        if request.recreate:
            msg = f"Full rebuild: indexed {result['files']} files, {result['chunks']} chunks"
        else:
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
        # Return simplified stats
        return {
            "manifest_files": stats.get("manifest_files", 0),
            "qdrant_points": stats.get("qdrant", {}).get("points_count", 0),
            "status": stats.get("qdrant", {}).get("status", "unknown")
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

        before_rerank = [
            {
                "text_zh": d["text_zh"],
                "text_en": d["text_en"],
                "source": d["source"],
                "rank": i + 1,
                "score": d.get("score", 0),
                "dense_score": d.get("dense_score", 0),
                "sparse_score": d.get("sparse_score", 0)
            }
            for i, d in enumerate(comparison["before_rerank"])
        ]

        after_rerank = [
            {
                "text_zh": d["text_zh"],
                "text_en": d["text_en"],
                "source": d["source"],
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
