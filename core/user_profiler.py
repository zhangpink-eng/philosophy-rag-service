from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from db.postgres_client import UserProfile, SessionSummary
import uuid


class UserProfiler:
    """Auto-update user profiles based on session summaries"""

    def update_profile_from_summary(
        self,
        db: DBSession,
        user_id: str,
        summary: SessionSummary
    ) -> UserProfile:
        """Update user profile based on session summary"""
        profile = self._get_latest_profile(db, user_id)
        if not profile:
            profile = self._create_initial_profile(db, user_id)

        # Update thinking patterns
        profile = self._update_thinking_patterns(profile, summary)

        # Update blind spots
        profile = self._update_blind_spots(profile, summary)

        # Update avoidance patterns
        profile = self._update_avoidance_patterns(profile, summary)

        # Update core themes
        profile = self._update_core_themes(profile, summary)

        # Update strengths
        profile = self._update_strengths(profile, summary)

        # Update growth timeline
        profile = self._update_growth_timeline(profile, summary, db)

        # Update depth trend
        profile = self._update_depth_trend(profile, summary, db)

        # Update session summaries index
        profile = self._update_session_index(profile, summary, db)

        profile.timestamp = datetime.utcnow()
        db.commit()
        db.refresh(profile)
        return profile

    def _get_latest_profile(self, db: DBSession, user_id: str) -> Optional[UserProfile]:
        """Get user's latest profile"""
        return db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).order_by(UserProfile.timestamp.desc()).first()

    def _create_initial_profile(self, db: DBSession, user_id: str) -> UserProfile:
        """Create initial profile for user"""
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
        db.refresh(profile)
        return profile

    def _update_thinking_patterns(
        self,
        profile: UserProfile,
        summary: SessionSummary
    ) -> UserProfile:
        """Extract and update thinking patterns"""
        patterns = list(profile.thinking_patterns or [])

        # Extract patterns from contradictions found
        for contradiction in (summary.contradictions_found or []):
            pattern = f"Tends to hold contradictory beliefs about: {contradiction[:50]}"
            if pattern not in patterns:
                patterns.append(pattern)

        # Keep only last 10 patterns
        profile.thinking_patterns = patterns[-10:]
        return profile

    def _update_blind_spots(
        self,
        profile: UserProfile,
        summary: SessionSummary
    ) -> UserProfile:
        """Extract and update blind spots"""
        blind_spots = list(profile.blind_spots or [])

        # Extract from avoidance moments
        for moment in (summary.avoidance_moments or []):
            spot = f"Avoids discussing: {moment[:50]}"
            if spot not in blind_spots:
                blind_spots.append(spot)

        # Keep only last 10
        profile.blind_spots = blind_spots[-10:]
        return profile

    def _update_avoidance_patterns(
        self,
        profile: UserProfile,
        summary: SessionSummary
    ) -> UserProfile:
        """Extract and update avoidance patterns"""
        patterns = list(profile.avoidance_patterns or [])

        for moment in (summary.avoidance_moments or []):
            if moment not in patterns:
                patterns.append(moment[:100])

        profile.avoidance_patterns = patterns[-10:]
        return profile

    def _update_core_themes(
        self,
        profile: UserProfile,
        summary: SessionSummary
    ) -> UserProfile:
        """Update core themes based on main topic"""
        themes = list(profile.core_themes or [])

        if summary.main_topic and summary.main_topic not in themes:
            themes.append(summary.main_topic)

        # Keep only last 15 themes
        profile.core_themes = themes[-15:]
        return profile

    def _update_strengths(
        self,
        profile: UserProfile,
        summary: SessionSummary
    ) -> UserProfile:
        """Update thinking strengths"""
        strengths = list(profile.strengths or [])

        # User insights indicate thinking strength
        for insight in (summary.user_insights or []):
            strength = f"Demonstrated insight: {insight[:50]}"
            if strength not in strengths:
                strengths.append(strength)

        # High engagement indicates active participation
        if summary.engagement_score and summary.engagement_score >= 7:
            if "Active participant in philosophical exploration" not in strengths:
                strengths.append("Active participant in philosophical exploration")

        profile.strengths = strengths[-10:]
        return profile

    def _update_growth_timeline(
        self,
        profile: UserProfile,
        summary: SessionSummary,
        db: DBSession
    ) -> UserProfile:
        """Add new entry to growth timeline"""
        timeline = list(profile.growth_timeline or [])

        entry = {
            "date": datetime.utcnow().isoformat(),
            "insight": summary.main_topic,
            "topic": summary.main_topic,
            "depth_score": summary.depth_score
        }

        timeline.append(entry)
        profile.growth_timeline = timeline[-20:]  # Keep last 20 entries
        return profile

    def _update_depth_trend(
        self,
        profile: UserProfile,
        summary: SessionSummary,
        db: DBSession
    ) -> UserProfile:
        """Add new depth score to trend"""
        trend = list(profile.depth_trend or [])

        entry = {
            "session_id": summary.session_id,
            "depth_score": summary.depth_score,
            "date": datetime.utcnow().isoformat()
        }

        trend.append(entry)
        profile.depth_trend = trend[-30:]  # Keep last 30 sessions
        return profile

    def _update_session_index(
        self,
        profile: UserProfile,
        summary: SessionSummary,
        db: DBSession
    ) -> UserProfile:
        """Add session to summaries index"""
        summaries = list(profile.session_summaries or [])

        entry = {
            "session_id": summary.session_id,
            "date": datetime.utcnow().isoformat(),
            "topic": summary.main_topic
        }

        summaries.append(entry)
        profile.session_summaries = summaries[-30:]  # Keep last 30
        return profile

    def get_profile_summary(self, profile: UserProfile) -> str:
        """Generate a text summary of user profile for prompt injection"""
        if not profile:
            return "No profile data available."

        parts = []

        if profile.core_themes:
            parts.append(f"Core themes: {', '.join(profile.core_themes[-3:])}")

        if profile.blind_spots:
            parts.append(f"Known blind spots: {', '.join(profile.blind_spots[-2:])}")

        if profile.avoidance_patterns:
            parts.append(f"Tends to avoid: {', '.join(profile.avoidance_patterns[-2:])}")

        if profile.growth_timeline:
            recent = profile.growth_timeline[-1]
            parts.append(f"Most recent topic: {recent.get('insight', 'Unknown')}")

        return "; ".join(parts) if parts else "Building profile..."
