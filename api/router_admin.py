"""
Admin API Router
管理后台 API - 数据统计、质量报告、会话分析
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from db.postgres_client import get_db_direct
from core.quality_evaluator import QualityEvaluator

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============ Admin Schemas ============

class SessionStats(BaseModel):
    """会话统计数据"""
    total_sessions: int
    active_sessions: int
    avg_duration_minutes: float
    total_messages: int
    avg_messages_per_session: float


class UserStats(BaseModel):
    """用户统计数据"""
    total_users: int
    new_users_today: int
    new_users_this_week: int
    new_users_this_month: int
    active_users: int


class QualityStats(BaseModel):
    """质量统计数据"""
    avg_depth_score: float
    avg_contradiction_score: float
    avg_insight_score: float
    avg_engagement_score: float
    avg_style_score: float
    avg_overall_score: float
    total_evaluated_sessions: int


class SafetyStats(BaseModel):
    """安全统计数据"""
    total_checks: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    crisis_detected_count: int


class WorkshopStats(BaseModel):
    """工作坊统计数据"""
    total_workshops: int
    active_workshops: int
    total_participants: int
    avg_participants_per_workshop: float


class DashboardData(BaseModel):
    """仪表盘数据"""
    session_stats: SessionStats
    user_stats: UserStats
    quality_stats: QualityStats
    safety_stats: SafetyStats
    workshop_stats: WorkshopStats


class SessionDetail(BaseModel):
    """会话详情"""
    session_id: str
    user_id: Optional[int]
    created_at: datetime
    ended_at: Optional[datetime]
    message_count: int
    quality_score: Optional[float]
    topics: List[str]


class QualityReport(BaseModel):
    """质量报告"""
    session_id: str
    user_id: Optional[int]
    created_at: datetime
    depth_score: float
    contradiction_score: float
    insight_score: float
    engagement_score: float
    style_score: float
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]


# ============ Admin Endpoints ============

@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard_data():
    """
    获取管理后台仪表盘数据

    Returns:
        包含所有统计数据的仪表盘数据
    """
    db = get_db_direct()

    try:
        # Session stats
        session_result = db.execute("""
            SELECT
                COUNT(*) as total_sessions,
                SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) as active_sessions,
                AVG(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - created_at)) / 60) as avg_duration_minutes,
                SUM(message_count) as total_messages,
                AVG(message_count) as avg_messages_per_session
            FROM sessions
        """).fetchone()

        session_stats = SessionStats(
            total_sessions=session_result['total_sessions'] or 0,
            active_sessions=session_result['active_sessions'] or 0,
            avg_duration_minutes=round(session_result['avg_duration_minutes'] or 0, 2),
            total_messages=session_result['total_messages'] or 0,
            avg_messages_per_session=round(session_result['avg_messages_per_session'] or 0, 2)
        )

        # User stats
        user_result = db.execute("""
            SELECT
                COUNT(*) as total_users,
                SUM(CASE WHEN created_at >= CURRENT_DATE THEN 1 ELSE 0 END) as new_today,
                SUM(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 ELSE 0 END) as new_week,
                SUM(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 ELSE 0 END) as new_month,
                SUM(CASE WHEN last_active >= CURRENT_DATE - INTERVAL '7 days' THEN 1 ELSE 0 END) as active_users
            FROM users
        """).fetchone()

        user_stats = UserStats(
            total_users=user_result['total_users'] or 0,
            new_users_today=user_result['new_today'] or 0,
            new_users_this_week=user_result['new_week'] or 0,
            new_users_this_month=user_result['new_month'] or 0,
            active_users=user_result['active_users'] or 0
        )

        # Quality stats
        quality_result = db.execute("""
            SELECT
                AVG(depth_score) as avg_depth,
                AVG(contradiction_score) as avg_contradiction,
                AVG(insight_score) as avg_insight,
                AVG(engagement_score) as avg_engagement,
                AVG(style_score) as avg_style,
                AVG(overall_score) as avg_overall,
                COUNT(*) as total_evaluated
            FROM session_summaries
            WHERE overall_score IS NOT NULL
        """).fetchone()

        quality_stats = QualityStats(
            avg_depth_score=round(quality_result['avg_depth'] or 0, 2),
            avg_contradiction_score=round(quality_result['avg_contradiction'] or 0, 2),
            avg_insight_score=round(quality_result['avg_insight'] or 0, 2),
            avg_engagement_score=round(quality_result['avg_engagement'] or 0, 2),
            avg_style_score=round(quality_result['avg_style'] or 0, 2),
            avg_overall_score=round(quality_result['avg_overall'] or 0, 2),
            total_evaluated_sessions=quality_result['total_evaluated'] or 0
        )

        # Safety stats
        safety_result = db.execute("""
            SELECT
                COUNT(*) as total_checks,
                SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) as high_risk,
                SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) as medium_risk,
                SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END) as low_risk,
                SUM(CASE WHEN risk_level = 'CRISIS' THEN 1 ELSE 0 END) as crisis
            FROM safety_logs
        """).fetchone()

        safety_stats = SafetyStats(
            total_checks=safety_result['total_checks'] or 0,
            high_risk_count=safety_result['high_risk'] or 0,
            medium_risk_count=safety_result['medium_risk'] or 0,
            low_risk_count=safety_result['low_risk'] or 0,
            crisis_detected_count=safety_result['crisis'] or 0
        )

        # Workshop stats
        workshop_result = db.execute("""
            SELECT
                COUNT(*) as total_workshops,
                SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) as active_workshops,
                COUNT(DISTINCT participant_id) as total_participants,
                AVG(participant_count) as avg_participants
            FROM (
                SELECT w.id, w.ended_at, p.id as participant_id,
                       COUNT(*) OVER (PARTITION BY w.id) as participant_count
                FROM workshops w
                LEFT JOIN workshop_participants p ON w.id = p.workshop_id
            ) sub
        """).fetchone()

        workshop_stats = WorkshopStats(
            total_workshops=workshop_result['total_workshops'] or 0,
            active_workshops=workshop_result['active_workshops'] or 0,
            total_participants=workshop_result['total_participants'] or 0,
            avg_participants_per_workshop=round(workshop_result['avg_participants'] or 0, 2)
        )

        return DashboardData(
            session_stats=session_stats,
            user_stats=user_stats,
            quality_stats=quality_stats,
            safety_stats=safety_stats,
            workshop_stats=workshop_stats
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[SessionDetail])
async def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    获取会话列表

    Args:
        limit: 返回数量限制
        offset: 偏移量
        user_id: 筛选特定用户
        start_date: 开始日期
        end_date: 结束日期
    """
    db = get_db_direct()

    query = """
        SELECT s.id as session_id, s.user_id, s.created_at, s.ended_at,
               s.message_count, ss.overall_score as quality_score
        FROM sessions s
        LEFT JOIN session_summaries ss ON s.id = ss.session_id
        WHERE 1=1
    """
    params = []

    if user_id:
        query += " AND s.user_id = %s"
        params.append(user_id)

    if start_date:
        query += " AND s.created_at >= %s"
        params.append(start_date)

    if end_date:
        query += " AND s.created_at <= %s"
        params.append(end_date)

    query += " ORDER BY s.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    results = db.execute(query, params).fetchall()

    sessions = []
    for row in results:
        # Extract topics from session summary if available
        topics = []
        if row['session_id']:
            topic_result = db.execute(
                "SELECT topic FROM sessions WHERE id = %s",
                (row['session_id'],)
            ).fetchone()
            if topic_result and topic_result['topic']:
                topics = [topic_result['topic']]

        sessions.append(SessionDetail(
            session_id=str(row['session_id']),
            user_id=row['user_id'],
            created_at=row['created_at'],
            ended_at=row['ended_at'],
            message_count=row['message_count'] or 0,
            quality_score=row['quality_score'],
            topics=topics
        ))

    return sessions


@router.get("/sessions/{session_id}/quality-report", response_model=QualityReport)
async def get_session_quality_report(session_id: str):
    """
    获取特定会话的质量报告

    Args:
        session_id: 会话 ID
    """
    db = get_db_direct()

    # Get session info
    session = db.execute(
        "SELECT * FROM sessions WHERE id = %s",
        (session_id,)
    ).fetchone()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get quality evaluation
    summary = db.execute(
        "SELECT * FROM session_summaries WHERE session_id = %s",
        (session_id,)
    ).fetchone()

    if not summary:
        raise HTTPException(status_code=404, detail="Quality evaluation not available")

    evaluator = QualityEvaluator()
    report = evaluator.generate_report(
        session_id=session_id,
        dialogue_history=json.loads(summary.get('dialogue_history', '[]')),
        quality_scores={
            'depth': summary['depth_score'] or 0,
            'contradiction': summary['contradiction_score'] or 0,
            'insight': summary['insight_score'] or 0,
            'engagement': summary['engagement_score'] or 0,
            'style': summary['style_score'] or 0,
            'overall': summary['overall_score'] or 0
        }
    )

    return QualityReport(
        session_id=session_id,
        user_id=session['user_id'],
        created_at=session['created_at'],
        **report
    )


@router.get("/quality-trends")
async def get_quality_trends(
    days: int = Query(30, ge=1, le=365)
):
    """
    获取质量趋势数据

    Args:
        days: 统计天数
    """
    db = get_db_direct()

    result = db.execute(f"""
        SELECT
            DATE(created_at) as date,
            AVG(depth_score) as avg_depth,
            AVG(contradiction_score) as avg_contradiction,
            AVG(insight_score) as avg_insight,
            AVG(engagement_score) as avg_engagement,
            AVG(style_score) as avg_style,
            AVG(overall_score) as avg_overall,
            COUNT(*) as session_count
        FROM session_summaries
        WHERE created_at >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    """).fetchall()

    trends = []
    for row in result:
        trends.append({
            'date': row['date'].isoformat() if row['date'] else None,
            'avg_depth': round(row['avg_depth'] or 0, 2),
            'avg_contradiction': round(row['avg_contradiction'] or 0, 2),
            'avg_insight': round(row['avg_insight'] or 0, 2),
            'avg_engagement': round(row['avg_engagement'] or 0, 2),
            'avg_style': round(row['avg_style'] or 0, 2),
            'avg_overall': round(row['avg_overall'] or 0, 2),
            'session_count': row['session_count']
        })

    return {'trends': trends, 'days': days}


@router.get("/safety-logs")
async def get_safety_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    risk_level: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    获取安全日志

    Args:
        limit: 返回数量限制
        offset: 偏移量
        risk_level: 筛选风险等级
        start_date: 开始日期
        end_date: 结束日期
    """
    db = get_db_direct()

    query = """
        SELECT * FROM safety_logs
        WHERE 1=1
    """
    params = []

    if risk_level:
        query += " AND risk_level = %s"
        params.append(risk_level)

    if start_date:
        query += " AND created_at >= %s"
        params.append(start_date)

    if end_date:
        query += " AND created_at <= %s"
        params.append(end_date)

    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    results = db.execute(query, params).fetchall()

    logs = []
    for row in results:
        logs.append({
            'id': row['id'],
            'session_id': row['session_id'],
            'user_input': row['user_input'],
            'risk_level': row['risk_level'],
            'message': row['message'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None
        })

    return {'logs': logs, 'total': len(logs)}


@router.get("/user-activity")
async def get_user_activity(
    days: int = Query(7, ge=1, le=90)
):
    """
    获取用户活跃度数据

    Args:
        days: 统计天数
    """
    db = get_db_direct()

    result = db.execute(f"""
        SELECT
            DATE(created_at) as date,
            COUNT(DISTINCT user_id) as active_users,
            COUNT(*) as new_users,
            SUM(message_count) as total_messages
        FROM sessions
        WHERE created_at >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    """).fetchall()

    activity = []
    for row in result:
        activity.append({
            'date': row['date'].isoformat() if row['date'] else None,
            'active_users': row['active_users'] or 0,
            'new_users': row['new_users'] or 0,
            'total_messages': row['total_messages'] or 0
        })

    return {'activity': activity, 'days': days}


@router.get("/topic-analysis")
async def get_topic_analysis(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100)
):
    """
    获取话题分析数据

    Args:
        days: 统计天数
        limit: 返回数量限制
    """
    db = get_db_direct()

    # Get most common topics from session summaries
    result = db.execute(f"""
        SELECT
            topic,
            COUNT(*) as session_count,
            AVG(overall_score) as avg_quality,
            AVG(depth_score) as avg_depth
        FROM session_summaries
        WHERE topic IS NOT NULL AND topic != ''
        AND created_at >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY topic
        ORDER BY session_count DESC
        LIMIT %s
    """, (limit,)).fetchall()

    topics = []
    for row in result:
        topics.append({
            'topic': row['topic'],
            'session_count': row['session_count'],
            'avg_quality': round(row['avg_quality'] or 0, 2),
            'avg_depth': round(row['avg_depth'] or 0, 2)
        })

    return {'topics': topics, 'days': days}
