from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional, List
from config import settings

# Create engine
DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    subscription_plan = Column(String(50), default="free")
    total_sessions = Column(Integer, default=0)
    remaining_sessions = Column(Integer, default=10)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """Session model"""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    topic = Column(Text, nullable=True)  # Main topic of the session
    scenario = Column(String(50), default="consultation")  # consultation/supervision/workshop
    status = Column(String(50), default="scheduled")  # scheduled/in_progress/completed/cancelled
    message_count = Column(Integer, default=0)  # Number of messages in session
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    dialogue_history = Column(JSON, default=list)  # [{role, content, timestamp}]
    summary_id = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")


class SessionSummary(Base):
    """Session summary model"""
    __tablename__ = "session_summaries"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=True)  # 无外键约束
    user_id = Column(String, nullable=True)  # 测试场景用 anonymous
    topic = Column(Text, nullable=True)
    scenario = Column(String(50))
    duration_minutes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Content summary
    main_topic = Column(Text, nullable=True)
    key_questions = Column(JSON, default=list)  # ["question1", "question2"]
    user_insights = Column(JSON, default=list)  # ["insight1", "insight2"]
    contradictions_found = Column(JSON, default=list)  # ["contradiction1"]
    avoidance_moments = Column(JSON, default=list)  # ["moment1"]

    # Follow-up
    unresolved_questions = Column(JSON, default=list)
    homework = Column(JSON, default=list)
    next_session_focus = Column(Text, nullable=True)

    # Quality evaluation
    depth_score = Column(Float, default=0.0)  # 0-10
    contradiction_score = Column(Float, default=0.0)  # 0-10
    insight_score = Column(Float, default=0.0)  # 0-10
    engagement_score = Column(Float, default=0.0)  # 0-10
    style_score = Column(Float, default=0.0)  # 0-10
    overall_score = Column(Float, default=0.0)  # 0-10

    # Dialogue history for reference
    dialogue_history = Column(JSON, default=list)


class UserProfile(Base):
    """User profile model - tracks user's thinking patterns over time"""
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)  # 无外键约束
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Thinking patterns (auto-updated)
    thinking_patterns = Column(JSON, default=list)  # ["pattern1", "pattern2"]
    blind_spots = Column(JSON, default=list)  # ["blind_spot1"]
    avoidance_patterns = Column(JSON, default=list)  # ["avoidance1"]
    core_themes = Column(JSON, default=list)  # ["theme1", "theme2"]
    strengths = Column(JSON, default=list)  # ["strength1"]

    # Growth trajectory
    growth_timeline = Column(JSON, default=list)  # [{"date", "insight", "topic"}]
    depth_trend = Column(JSON, default=list)  # [{"session_id", "depth_score", "date"}]

    # Session summaries index
    session_summaries = Column(JSON, default=list)  # [{"session_id", "date", "topic"}]


class Feedback(Base):
    """Feedback model"""
    __tablename__ = "feedbacks"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=True)  # 无外键约束
    user_id = Column(String, nullable=True)  # 测试场景用 anonymous
    timestamp = Column(DateTime, default=datetime.utcnow)
    rating = Column(Integer, default=0)  # 1-5
    helpful_aspects = Column(JSON, default=list)  # ["aspect1", "aspect2"]
    improvement_suggestions = Column(Text, nullable=True)


class Memory(Base):
    """Long-term memory model"""
    __tablename__ = "memories"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    memory_type = Column(String(50), default="session")  # session/longterm/user_profile
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Memory content
    content = Column(Text, nullable=False)
    memory_vector = Column(JSON, nullable=True)  # For similarity search
    tags = Column(JSON, default=list)  # ["freedom", "anxiety", "work"]

    # Metadata
    importance = Column(Float, default=0.5)  # 0-1
    last_accessed = Column(DateTime, default=datetime.utcnow)


class SafetyLog(Base):
    """Safety check log model"""
    __tablename__ = "safety_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=True)  # 无外键约束
    user_input = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=False)  # LOW/MEDIUM/HIGH/CRISIS
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Workshop(Base):
    """Workshop model"""
    __tablename__ = "workshops"

    id = Column(String, primary_key=True)
    topic = Column(Text, nullable=False)
    host_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="waiting")  # waiting/active/ended
    phase = Column(String(50), default="viewpoint")  # viewpoint/discussion/summary
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    host = relationship("User")
    participants = relationship("WorkshopParticipant", back_populates="workshop", cascade="all, delete-orphan")
    viewpoints = relationship("WorkshopViewpoint", back_populates="workshop", cascade="all, delete-orphan")


class WorkshopParticipant(Base):
    """Workshop participant model"""
    __tablename__ = "workshop_participants"

    id = Column(String, primary_key=True)
    workshop_id = Column(String, ForeignKey("workshops.id"), nullable=False)
    participant_id = Column(String, nullable=False)  # External ID (from frontend)
    name = Column(String(100), nullable=False)
    viewpoint = Column(Text, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    workshop = relationship("Workshop", back_populates="participants")


class WorkshopViewpoint(Base):
    """Workshop viewpoint model"""
    __tablename__ = "workshop_viewpoints"

    id = Column(String, primary_key=True)
    workshop_id = Column(String, ForeignKey("workshops.id"), nullable=False)
    participant_id = Column(String, ForeignKey("workshop_participants.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    workshop = relationship("Workshop", back_populates="viewpoints")


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_direct():
    """Get database session directly (for non-FastAPI use)"""
    return SessionLocal()


class DialogueSession(Base):
    """轻量对话 session（无用户绑定，用于 test_server）"""
    __tablename__ = "dialogue_sessions"

    session_id = Column(String, primary_key=True)
    turns = Column(JSON, default=list)  # [{speaker, message}]
    scenario = Column(String(50), default="consultation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
