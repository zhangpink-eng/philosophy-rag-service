from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session as DBSession
from typing import List

from db.postgres_client import get_db, User
from api.router_user import require_auth
from api.schemas import (
    SessionCreateRequest, SessionResponse, DialogueTurnRequest,
    SessionEndRequest, SessionSummaryResponse, MemoryResponse
)
from core.session_manager import SessionManager
from core.session_summarizer import SessionSummarizer
from core.user_profiler import UserProfiler
from core.memory_manager import MemoryManager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

session_manager = SessionManager()
session_summarizer = SessionSummarizer()
user_profiler = UserProfiler()
memory_manager = MemoryManager()


@router.post("/start", response_model=SessionResponse)
async def start_session(
    request: SessionCreateRequest,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Create and start a new session"""
    session = session_manager.create_session(
        db=db,
        user_id=current_user.id,
        scenario=request.scenario,
        scheduled_at=request.scheduled_at
    )

    # Auto-start the session
    session = session_manager.start_session(db, session.id)

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        scenario=session.scenario,
        status=session.status,
        scheduled_at=session.scheduled_at,
        started_at=session.started_at,
        ended_at=session.ended_at,
        dialogue_history=session.dialogue_history or [],
        summary_id=session.summary_id
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Get session by ID"""
    session = session_manager.get_session_by_id(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        scenario=session.scenario,
        status=session.status,
        scheduled_at=session.scheduled_at,
        started_at=session.started_at,
        ended_at=session.ended_at,
        dialogue_history=session.dialogue_history or [],
        summary_id=session.summary_id
    )


@router.post("/message")
async def add_message(
    request: DialogueTurnRequest,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Add a dialogue turn to session"""
    session = session_manager.get_session_by_id(db, request.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not active")

    updated_session = session_manager.add_dialogue_turn(
        db=db,
        session_id=request.session_id,
        role=request.role,
        content=request.content
    )

    return {"status": "success", "message": "Message added"}


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: str,
    request: SessionEndRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """End a session"""
    session = session_manager.get_session_by_id(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already ended")

    # Generate summary if not provided
    summary_data = request.summary_data
    if not summary_data and session.dialogue_history:
        # Use LLM to generate summary
        try:
            summary_data = await session_summarizer.generate_summary(
                dialogue_history=session.dialogue_history,
                scenario=session.scenario
            )
        except Exception as e:
            print(f"Error generating summary: {e}")
            summary_data = {}

    # End session with summary
    ended_session = session_manager.end_session(db, session_id, summary_data)

    # Update user profiler in background
    if ended_session and summary_data:
        background_tasks.add_task(
            update_user_profile_task,
            db_url=str(db.bind.url),
            user_id=current_user.id,
            session_id=session_id,
            summary_data=summary_data
        )

    return SessionResponse(
        id=ended_session.id,
        user_id=ended_session.user_id,
        scenario=ended_session.scenario,
        status=ended_session.status,
        scheduled_at=ended_session.scheduled_at,
        started_at=ended_session.started_at,
        ended_at=ended_session.ended_at,
        dialogue_history=ended_session.dialogue_history or [],
        summary_id=ended_session.summary_id
    )


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
async def get_session_summary(
    session_id: str,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Get session summary"""
    session = session_manager.get_session_by_id(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    summary = session_manager.get_session_summary(db, session_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    return SessionSummaryResponse(
        id=summary.id,
        session_id=summary.session_id,
        user_id=summary.user_id,
        timestamp=summary.timestamp,
        scenario=summary.scenario,
        duration_minutes=summary.duration_minutes,
        main_topic=summary.main_topic or "",
        key_questions=summary.key_questions or [],
        user_insights=summary.user_insights or [],
        contradictions_found=summary.contradictions_found or [],
        avoidance_moments=summary.avoidance_moments or [],
        unresolved_questions=summary.unresolved_questions or [],
        homework=summary.homework or [],
        next_session_focus=summary.next_session_focus,
        depth_score=summary.depth_score,
        engagement_score=summary.engagement_score
    )


@router.get("/history", response_model=List[SessionResponse])
async def get_session_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Get user's session history"""
    sessions = session_manager.get_user_sessions(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )

    return [
        SessionResponse(
            id=s.id,
            user_id=s.user_id,
            scenario=s.scenario,
            status=s.status,
            scheduled_at=s.scheduled_at,
            started_at=s.started_at,
            ended_at=s.ended_at,
            dialogue_history=s.dialogue_history or [],
            summary_id=s.summary_id
        )
        for s in sessions
    ]


@router.post("/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Cancel a session"""
    session = session_manager.get_session_by_id(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    cancelled = session_manager.cancel_session(db, session_id)

    return {"status": "success", "message": "Session cancelled"}


def update_user_profile_task(db_url: str, user_id: str, session_id: str, summary_data: dict):
    """Background task to update user profile"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.postgres_client import Session as SessionModel, SessionSummary

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Get session and summary
        session = session_manager.get_session_by_id(db, session_id)
        if not session:
            return

        summary = session_manager.get_session_summary(db, session_id)
        if not summary:
            # Create summary from data
            summary_id = f"summary_{session_id.split('_')[1]}"
            summary = SessionSummary(
                id=summary_id,
                session_id=session_id,
                user_id=user_id,
                main_topic=summary_data.get("main_topic"),
                key_questions=summary_data.get("key_questions", []),
                user_insights=summary_data.get("user_insights", []),
                contradictions_found=summary_data.get("contradictions_found", []),
                avoidance_moments=summary_data.get("avoidance_moments", []),
                unresolved_questions=summary_data.get("unresolved_questions", []),
                homework=summary_data.get("homework", []),
                next_session_focus=summary_data.get("next_session_focus"),
                depth_score=summary_data.get("depth_score", 0.0),
                engagement_score=summary_data.get("engagement_score", 0.0)
            )
            db.add(summary)
            db.commit()
            db.refresh(summary)

        # Update profile
        user_profiler.update_profile_from_summary(db, user_id, summary)

        # Consolidate memories
        memory_manager.consolidate_session_memory(db, user_id, session_id, summary)

    finally:
        db.close()
