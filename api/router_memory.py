from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional

from db.postgres_client import get_db, User
from api.router_user import require_auth
from api.schemas import MemoryResponse
from core.memory_manager import MemoryManager

router = APIRouter(prefix="/api/memories", tags=["memories"])

memory_manager = MemoryManager()


@router.get("", response_model=List[MemoryResponse])
async def get_memories(
    memory_type: Optional[str] = None,
    tags: Optional[str] = None,  # comma-separated
    limit: int = 20,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Get user's memories"""
    tag_list = tags.split(",") if tags else None

    memories = memory_manager.retrieve_memories(
        db=db,
        user_id=current_user.id,
        memory_type=memory_type,
        tags=tag_list,
        limit=limit
    )

    return [
        MemoryResponse(
            id=m.id,
            user_id=m.user_id,
            memory_type=m.memory_type,
            content=m.content,
            tags=m.tags or [],
            importance=m.importance,
            timestamp=m.timestamp,
            last_accessed=m.last_accessed
        )
        for m in memories
    ]


@router.get("/search")
async def search_memories(
    q: str,
    limit: int = 10,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Search memories by content"""
    memories = memory_manager.search_related_memories(
        db=db,
        user_id=current_user.id,
        query=q,
        limit=limit
    )

    return [
        MemoryResponse(
            id=m.id,
            user_id=m.user_id,
            memory_type=m.memory_type,
            content=m.content,
            tags=m.tags or [],
            importance=m.importance,
            timestamp=m.timestamp,
            last_accessed=m.last_accessed
        )
        for m in memories
    ]


@router.get("/longterm", response_model=List[MemoryResponse])
async def get_longterm_memories(
    limit: int = 20,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Get user's long-term memories"""
    memories = memory_manager.get_user_longterm_memories(
        db=db,
        user_id=current_user.id,
        limit=limit
    )

    return [
        MemoryResponse(
            id=m.id,
            user_id=m.user_id,
            memory_type=m.memory_type,
            content=m.content,
            tags=m.tags or [],
            importance=m.importance,
            timestamp=m.timestamp,
            last_accessed=m.last_accessed
        )
        for m in memories
    ]
