import uuid
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session as DBSession
from db.postgres_client import User, UserProfile, Session as SessionModel


class UserManager:
    """User management - registration, authentication, profile updates"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return UserManager.hash_password(password) == password_hash

    @staticmethod
    def generate_user_id() -> str:
        """Generate unique user ID"""
        return f"user_{uuid.uuid4().hex[:16]}"

    def create_user(
        self,
        db: DBSession,
        name: str,
        email: str,
        password: str,
        phone: Optional[str] = None
    ) -> User:
        """Create a new user"""
        user_id = self.generate_user_id()
        user = User(
            id=user_id,
            name=name,
            email=email,
            password_hash=self.hash_password(password),
            phone=phone
        )
        db.add(user)

        # Create initial user profile
        profile_id = f"profile_{uuid.uuid4().hex[:16]}"
        profile = UserProfile(
            id=profile_id,
            user_id=user_id,
            thinking_patterns=[],
            blind_spots=[],
            avoidance_patterns=[],
            core_themes=[],
            strengths=[],
            growth_timeline=[],
            depth_trend=[],
            session_summaries=[]
        )
        db.add(profile)

        db.commit()
        db.refresh(user)
        return user

    def authenticate_user(
        self,
        db: DBSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """Authenticate user by email and password"""
        user = db.query(User).filter(User.email == email).first()
        if user and self.verify_password(password, user.password_hash):
            # Update last active
            user.last_active = datetime.utcnow()
            db.commit()
            return user
        return None

    def get_user_by_id(self, db: DBSession, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, db: DBSession, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()

    def update_user_activity(self, db: DBSession, user_id: str) -> None:
        """Update user's last active timestamp"""
        user = self.get_user_by_id(db, user_id)
        if user:
            user.last_active = datetime.utcnow()
            db.commit()

    def increment_session_count(self, db: DBSession, user_id: str) -> None:
        """Increment user's total session count"""
        user = self.get_user_by_id(db, user_id)
        if user:
            user.total_sessions += 1
            if user.remaining_sessions > 0:
                user.remaining_sessions -= 1
            db.commit()

    def get_user_profile(self, db: DBSession, user_id: str) -> Optional[UserProfile]:
        """Get user's latest profile"""
        profiles = db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).order_by(UserProfile.timestamp.desc()).first()
        return profiles

    def update_user_profile(
        self,
        db: DBSession,
        user_id: str,
        updates: Dict
    ) -> Optional[UserProfile]:
        """Update user profile with new data"""
        profile = self.get_user_profile(db, user_id)
        if not profile:
            return None

        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        db.commit()
        db.refresh(profile)
        return profile
