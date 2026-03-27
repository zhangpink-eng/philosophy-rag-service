import uuid
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session as DBSession
from db.postgres_client import Session as SessionModel, SessionSummary, User


class SessionManager:
    """Session management - create, update, end sessions"""

    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID"""
        return f"session_{uuid.uuid4().hex[:16]}"

    def create_session(
        self,
        db: DBSession,
        user_id: str,
        scenario: str = "consultation",
        scheduled_at: Optional[datetime] = None
    ) -> SessionModel:
        """Create a new session"""
        session_id = self.generate_session_id()
        session = SessionModel(
            id=session_id,
            user_id=user_id,
            scenario=scenario,
            status="scheduled",
            scheduled_at=scheduled_at,
            dialogue_history=[]
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def start_session(self, db: DBSession, session_id: str) -> Optional[SessionModel]:
        """Start a scheduled session"""
        session = self.get_session_by_id(db, session_id)
        if session and session.status == "scheduled":
            session.status = "in_progress"
            session.started_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
        return session

    def end_session(
        self,
        db: DBSession,
        session_id: str,
        summary_data: Optional[Dict] = None
    ) -> Optional[SessionModel]:
        """End a session and optionally create summary"""
        session = self.get_session_by_id(db, session_id)
        if not session:
            return None

        session.status = "completed"
        session.ended_at = datetime.utcnow()

        # Calculate duration
        if session.started_at:
            duration = int((session.ended_at - session.started_at).total_seconds() / 60)
            session.duration_minutes = duration

        # Create summary if provided
        if summary_data:
            summary_id = f"summary_{uuid.uuid4().hex[:16]}"
            summary = SessionSummary(
                id=summary_id,
                session_id=session_id,
                user_id=session.user_id,
                scenario=session.scenario,
                duration_minutes=duration,
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
            session.summary_id = summary_id

        db.commit()
        db.refresh(session)
        return session

    def add_dialogue_turn(
        self,
        db: DBSession,
        session_id: str,
        role: str,
        content: str
    ) -> Optional[SessionModel]:
        """Add a dialogue turn to session history"""
        session = self.get_session_by_id(db, session_id)
        if session:
            turn = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            if not session.dialogue_history:
                session.dialogue_history = []
            session.dialogue_history.append(turn)
            db.commit()
            db.refresh(session)
        return session

    def get_session_by_id(self, db: DBSession, session_id: str) -> Optional[SessionModel]:
        """Get session by ID"""
        return db.query(SessionModel).filter(SessionModel.id == session_id).first()

    def get_user_sessions(
        self,
        db: DBSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[SessionModel]:
        """Get user's session history"""
        return db.query(SessionModel).filter(
            SessionModel.user_id == user_id
        ).order_by(SessionModel.created_at.desc()).offset(offset).limit(limit).all()

    def get_session_summary(
        self,
        db: DBSession,
        session_id: str
    ) -> Optional[SessionSummary]:
        """Get session summary"""
        return db.query(SessionSummary).filter(
            SessionSummary.session_id == session_id
        ).first()

    def cancel_session(self, db: DBSession, session_id: str) -> Optional[SessionModel]:
        """Cancel a session"""
        session = self.get_session_by_id(db, session_id)
        if session and session.status in ["scheduled", "in_progress"]:
            session.status = "cancelled"
            db.commit()
            db.refresh(session)
        return session
