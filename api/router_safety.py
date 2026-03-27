from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from core.safeguard import SafeGuard, RiskLevel, SafetyCheckResult
from core.quality_evaluator import QualityEvaluator, QualityReport

router = APIRouter(prefix="/api", tags=["safety"])

safeguard = SafeGuard()
quality_evaluator = QualityEvaluator()


# ============ Safety Schemas ============

class SafetyCheckRequest(BaseModel):
    text: str


class SafetyCheckResponse(BaseModel):
    is_safe: bool
    risk_level: str
    trigger_type: Optional[str] = None
    message: Optional[str] = None
    suggestion: Optional[str] = None


class SessionRiskRequest(BaseModel):
    dialogue_history: List[Dict]


class SessionRiskResponse(BaseModel):
    risk_level: str
    risk_indicators: List[str]
    is_safe: bool


# ============ Quality Schemas ============

class TurnEvaluationRequest(BaseModel):
    context: List[Dict]
    ai_response: str


class TurnEvaluationResponse(BaseModel):
    length_ok: bool
    has_question: bool
    has_confrontation: bool
    is_appropriate_length: bool
    suggestions: List[str]


# ============ Safety Endpoints ============

@router.post("/safety/check", response_model=SafetyCheckResponse)
async def check_input_safety(request: SafetyCheckRequest):
    """
    Check user input for safety concerns.

    Performs real-time content filtering for:
    - Crisis keywords (self-harm, suicide)
    - Extreme emotions
    - Boundary topics (requires professional help)
    """
    result = safeguard.check_user_input(request.text)

    return SafetyCheckResponse(
        is_safe=result.is_safe,
        risk_level=result.risk_level.value,
        trigger_type=result.trigger_type,
        message=result.message,
        suggestion=result.suggestion
    )


@router.post("/safety/response-check", response_model=SafetyCheckResponse)
async def check_response_safety(response_text: str):
    """
    Check AI response for safety concerns.

    Ensures AI doesn't provide inappropriate advice
    (medical, legal, etc.)
    """
    result = safeguard.check_ai_response(response_text)

    return SafetyCheckResponse(
        is_safe=result.is_safe,
        risk_level=result.risk_level.value,
        trigger_type=result.trigger_type,
        message=result.message,
        suggestion=result.suggestion
    )


@router.post("/safety/session-risk", response_model=SessionRiskResponse)
async def assess_session_risk(request: SessionRiskRequest):
    """
    Assess overall session risk based on dialogue history.

    Returns risk level and indicators for monitoring.
    """
    risk_level, indicators = safeguard.assess_session_risk(request.dialogue_history)

    return SessionRiskResponse(
        risk_level=risk_level.value,
        risk_indicators=indicators,
        is_safe=risk_level != RiskLevel.CRISIS
    )


@router.get("/safety/hotlines")
async def get_crisis_hotlines():
    """Get crisis hotline numbers"""
    return {
        "hotlines": [
            {"name": h.name, "phone": h.phone}
            for h in SafeGuard.HOTLINES
        ]
    }


# ============ Quality Endpoints ============

@router.post("/quality/turn")
async def evaluate_turn(request: TurnEvaluationRequest):
    """
    Evaluate a single dialogue turn.

    For real-time feedback in assistant mode.
    """
    result = quality_evaluator.evaluate_turn(
        context=request.context,
        ai_response=request.ai_response
    )

    return TurnEvaluationResponse(**result)


@router.post("/quality/session")
async def evaluate_session(
    session_id: str,
    dialogue_history: List[Dict],
    scenario: str = "consultation"
):
    """
    Evaluate complete session quality.

    Returns detailed report with scores across dimensions.
    """
    report = await quality_evaluator.evaluate_session(
        dialogue_history=dialogue_history,
        scenario=scenario
    )

    suggestions = await quality_evaluator.generate_improvement_suggestions(report)

    return {
        "session_id": session_id,
        "scores": report.quality_score.to_dict(),
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "improvement_suggestions": suggestions,
        "key_moments": report.key_moments,
        "summary": report.summary
    }
