from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============ User Schemas ============

class UserRegisterRequest(BaseModel):
    """User registration request."""
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None


class UserLoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response schema."""
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    created_at: datetime
    last_active: datetime
    subscription_plan: str
    total_sessions: int
    remaining_sessions: int


class UserProfileResponse(BaseModel):
    """User profile response schema."""
    thinking_patterns: List[str] = []
    blind_spots: List[str] = []
    avoidance_patterns: List[str] = []
    core_themes: List[str] = []
    strengths: List[str] = []
    growth_timeline: List[Dict] = []
    depth_trend: List[Dict] = []
    session_summaries: List[Dict] = []


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============ Session Schemas ============

class SessionCreateRequest(BaseModel):
    """Create session request."""
    scenario: str = Field("consultation", description="consultation/supervision/workshop")
    scheduled_at: Optional[datetime] = None


class SessionResponse(BaseModel):
    """Session response schema."""
    id: str
    user_id: str
    scenario: str
    status: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    dialogue_history: List[Dict] = []
    summary_id: Optional[str] = None


class DialogueTurnRequest(BaseModel):
    """Add dialogue turn request."""
    session_id: str
    role: str = Field(..., description="user or oscar")
    content: str


class SessionEndRequest(BaseModel):
    """End session request with optional summary data."""
    summary_data: Optional[Dict] = None


class SessionSummaryResponse(BaseModel):
    """Session summary response."""
    id: str
    session_id: Optional[str]
    user_id: str
    timestamp: datetime
    scenario: str
    duration_minutes: int
    main_topic: str
    key_questions: List[str] = []
    user_insights: List[str] = []
    contradictions_found: List[str] = []
    avoidance_moments: List[str] = []
    unresolved_questions: List[str] = []
    homework: List[str] = []
    next_session_focus: Optional[str] = None
    depth_score: float
    engagement_score: float


# ============ Memory Schemas ============

class MemoryResponse(BaseModel):
    """Memory response schema."""
    id: str
    user_id: str
    memory_type: str
    content: str
    tags: List[str] = []
    importance: float
    timestamp: datetime
    last_accessed: datetime


# ============ Query Schemas ============

class QueryRequest(BaseModel):
    """Request schema for query endpoint."""
    query: str = Field(..., description="User's question")
    include_sources: bool = Field(True, description="Include source documents in response")


class SourceDocument(BaseModel):
    """Source document schema."""
    text_zh: str
    text_en: str
    source: str
    score: float


class QueryResponse(BaseModel):
    """Response schema for query endpoint."""
    answer: str
    sources: List[SourceDocument] = []


class StreamQueryRequest(BaseModel):
    """Request schema for streaming query endpoint."""
    query: str = Field(..., description="User's question")


class IndexRequest(BaseModel):
    """Request schema for index endpoint."""
    recreate: bool = Field(False, description="Recreate collection before indexing (full rebuild)")
    incremental: bool = Field(True, description="Only index new/modified files")
    data_dir: Optional[str] = Field(None, description="Custom data directory path")
    files: Optional[List[str]] = Field(None, description="Specific files to index (default: all files)")


class IndexResponse(BaseModel):
    """Response schema for index endpoint."""
    status: str
    files: int
    chunks: int
    skipped: int = 0
    new: int = 0
    message: str


class PreprocessRequest(BaseModel):
    """Request schema for text preprocessing."""
    text: str = Field(..., description="Text content to preprocess")
    file_name: Optional[str] = Field(None, description="Optional file name for context")


class PreprocessResponse(BaseModel):
    """Response schema for preprocessing result."""
    language: str
    is_bilingual: bool
    text_zh: str
    text_en: str
    stats: Dict[str, Any]
    chunks_zh: int = 0
    chunks_en: int = 0
    final_chunks: int
    message: str = ""


class HealthResponse(BaseModel):
    """Response schema for health endpoint."""
    status: str
    collection: Dict[str, Any]
    models_loaded: bool


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
