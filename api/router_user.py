from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional
import hashlib

from sqlalchemy.orm import Session as DBSession
from db.postgres_client import get_db, User
from api.schemas import (
    UserRegisterRequest, UserLoginRequest, UserResponse,
    UserProfileResponse, AuthResponse
)
from core.user_manager import UserManager
from config import settings

router = APIRouter(prefix="/api/users", tags=["users"])

user_manager = UserManager()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/login", auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: DBSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token"""
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    return user_manager.get_user_by_id(db, user_id)


def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authentication"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user


@router.post("/register", response_model=AuthResponse)
async def register(request: UserRegisterRequest, db: DBSession = Depends(get_db)):
    """Register a new user"""
    # Check if email already exists
    existing = user_manager.get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = user_manager.create_user(
        db=db,
        name=request.name,
        email=request.email,
        password=request.password,
        phone=request.phone
    )

    # Create token
    access_token = create_access_token(data={"sub": user.id})

    return AuthResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            created_at=user.created_at,
            last_active=user.last_active,
            subscription_plan=user.subscription_plan,
            total_sessions=user.total_sessions,
            remaining_sessions=user.remaining_sessions
        )
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: UserLoginRequest, db: DBSession = Depends(get_db)):
    """Login user"""
    user = user_manager.authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(data={"sub": user.id})

    return AuthResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            created_at=user.created_at,
            last_active=user.last_active,
            subscription_plan=user.subscription_plan,
            total_sessions=user.total_sessions,
            remaining_sessions=user.remaining_sessions
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(require_auth)):
    """Get current user info"""
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone=current_user.phone,
        created_at=current_user.created_at,
        last_active=current_user.last_active,
        subscription_plan=current_user.subscription_plan,
        total_sessions=current_user.total_sessions,
        remaining_sessions=current_user.remaining_sessions
    )


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Get current user's profile"""
    profile = user_manager.get_user_profile(db, current_user.id)
    if not profile:
        return UserProfileResponse()

    return UserProfileResponse(
        thinking_patterns=profile.thinking_patterns or [],
        blind_spots=profile.blind_spots or [],
        avoidance_patterns=profile.avoidance_patterns or [],
        core_themes=profile.core_themes or [],
        strengths=profile.strengths or [],
        growth_timeline=profile.growth_timeline or [],
        depth_trend=profile.depth_trend or [],
        session_summaries=profile.session_summaries or []
    )


@router.put("/profile")
async def update_user_profile(
    updates: dict,
    current_user: User = Depends(require_auth),
    db: DBSession = Depends(get_db)
):
    """Update user profile"""
    profile = user_manager.update_user_profile(db, current_user.id, updates)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    return {"status": "success", "message": "Profile updated"}
