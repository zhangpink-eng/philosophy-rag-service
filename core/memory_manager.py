import uuid
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session as DBSession
from db.postgres_client import Memory, SessionSummary, UserProfile


class MemoryManager:
    """Long-term memory management across sessions"""

    @staticmethod
    def generate_memory_id() -> str:
        """Generate unique memory ID"""
        return f"memory_{uuid.uuid4().hex[:16]}"

    def store_memory(
        self,
        db: DBSession,
        user_id: str,
        content: str,
        memory_type: str = "session",
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5
    ) -> Memory:
        """Store a new memory"""
        memory_id = self.generate_memory_id()
        memory = Memory(
            id=memory_id,
            user_id=user_id,
            memory_type=memory_type,
            session_id=session_id,
            content=content,
            tags=tags or [],
            importance=importance
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory

    def retrieve_memories(
        self,
        db: DBSession,
        user_id: str,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Memory]:
        """Retrieve memories for a user"""
        query = db.query(Memory).filter(Memory.user_id == user_id)

        if memory_type:
            query = query.filter(Memory.memory_type == memory_type)

        if tags:
            # Filter memories that have any of the tags
            for tag in tags:
                query = query.filter(Memory.tags.contains([tag]))

        return query.order_by(Memory.importance.desc(), Memory.last_accessed.desc()).limit(limit).all()

    def update_memory_access(self, db: DBSession, memory_id: str) -> None:
        """Update last accessed time"""
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if memory:
            memory.last_accessed = datetime.utcnow()
            db.commit()

    def get_user_longterm_memories(
        self,
        db: DBSession,
        user_id: str,
        limit: int = 20
    ) -> List[Memory]:
        """Get user's long-term memories"""
        return db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.memory_type == "longterm"
        ).order_by(Memory.last_accessed.desc()).limit(limit).all()

    def consolidate_session_memory(
        self,
        db: DBSession,
        user_id: str,
        session_id: str,
        session_summary: SessionSummary
    ) -> List[Memory]:
        """Consolidate important session info into long-term memory"""
        memories = []

        # Store main topic
        if session_summary.main_topic:
            topic_memory = self.store_memory(
                db=db,
                user_id=user_id,
                content=f"Discussed topic: {session_summary.main_topic}",
                memory_type="longterm",
                session_id=session_id,
                tags=[session_summary.main_topic],
                importance=0.7
            )
            memories.append(topic_memory)

        # Store key insights
        for insight in (session_summary.user_insights or []):
            insight_memory = self.store_memory(
                db=db,
                user_id=user_id,
                content=f"User insight: {insight}",
                memory_type="longterm",
                session_id=session_id,
                tags=["insight"],
                importance=0.6
            )
            memories.append(insight_memory)

        # Store contradictions found
        for contradiction in (session_summary.contradictions_found or []):
            contradiction_memory = self.store_memory(
                db=db,
                user_id=user_id,
                content=f"Contradiction explored: {contradiction}",
                memory_type="longterm",
                session_id=session_id,
                tags=["contradiction"],
                importance=0.5
            )
            memories.append(contradiction_memory)

        # Store unresolved questions for follow-up
        for question in (session_summary.unresolved_questions or []):
            question_memory = self.store_memory(
                db=db,
                user_id=user_id,
                content=f"Unresolved question to follow up: {question}",
                memory_type="longterm",
                session_id=session_id,
                tags=["unresolved", "follow-up"],
                importance=0.4
            )
            memories.append(question_memory)

        return memories

    def search_related_memories(
        self,
        db: DBSession,
        user_id: str,
        query: str,
        limit: int = 5
    ) -> List[Memory]:
        """Search memories by content keyword"""
        return db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.content.ilike(f"%{query}%")
        ).order_by(Memory.importance.desc()).limit(limit).all()

    def delete_old_memories(
        self,
        db: DBSession,
        user_id: str,
        before_date: datetime
    ) -> int:
        """Delete memories older than specified date"""
        result = db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.timestamp < before_date
        ).delete()
        db.commit()
        return result
