from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from core.llm_client import LLMClient
from core.safeguard import SafeGuard
from core.quality_evaluator import QualityEvaluator

router = APIRouter(prefix="/api/assist", tags=["assistant"])


# ============ Assistant Schemas ============

class ClientMessage(BaseModel):
    """Client's message to analyze"""
    content: str
    context: Optional[List[Dict]] = None


class SuggestRequest(BaseModel):
    """Request for suggested follow-up questions"""
    client_message: str
    session_topic: Optional[str] = None
    consultation_phase: str = "exploration"


class ReferenceRequest(BaseModel):
    """Request for relevant consultation cases"""
    query: str
    limit: int = 5


class AnalyzeRequest(BaseModel):
    """Request for analysis of client statement"""
    client_message: str
    session_context: Optional[List[Dict]] = None


class ReviewRequest(BaseModel):
    """Request for session review"""
    dialogue_history: List[Dict]
    focus_area: Optional[str] = None


# ============ Initialize Components ============
llm = LLMClient()
safeguard = SafeGuard()
quality_evaluator = QualityEvaluator()


# ============ Assistant Endpoints ============

@router.post("/suggest")
async def get_suggestions(request: SuggestRequest):
    """
    Get suggested follow-up questions based on client's message.

    Returns:
    - Suggested questions to deepen exploration
    - Recommended techniques
    - Topics to avoid
    """
    try:
        prompt = f"""作为一个哲学咨询助手，根据来访者的问题，给出苏格拉底式追问的建议。

来访者问题：{request.client_message}
当前话题：{request.session_topic or '未指定'}
当前阶段：{request.consultation_phase}

请给出3个追问建议，每个追问应该：
1. 简洁有力（10-30字）
2. 直接切入要害
3. 帮助来访者深化自我认知

以JSON格式返回：
{{
    "suggestions": [
        {{"question": "追问1", "technique": "使用的技巧", "purpose": "目的"}},
        ...
    ],
    "recommended_approach": "建议的总体方向",
    "topics_to_explore": ["可探索的方向1", "方向2"]
}}
"""
        system_prompt = "你是一个专业的哲学咨询助手，为人类咨询师提供建议。"
        response = await llm.generate(system_prompt, prompt)

        # Parse JSON response
        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            return data

        return {"suggestions": [], "recommended_approach": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reference")
async def get_references(request: ReferenceRequest):
    """
    Get relevant consultation cases from knowledge base.

    This would typically search the vector database for similar cases.
    For now, returns a placeholder.
    """
    try:
        # In production, this would search Qdrant for similar cases
        # For now, return a structured response

        return {
            "query": request.query,
            "cases": [],
            "message": "案例检索功能需要完整的RAG pipeline支持"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_client_message(request: AnalyzeRequest):
    """
    Analyze client's message for:
    - Emotional state
    - Potential blind spots
    - Logical inconsistencies
    - Hidden assumptions
    """
    try:
        prompt = f"""分析以下来访者的陈述，从哲学咨询的角度给出反馈。

来访者的话：{request.client_message}

请分析：
1. 情绪状态（是否有焦虑、防御、回避等）
2. 可能的思维盲点
3. 潜在的逻辑矛盾或不一致
4. 隐含的假设或前提
5. 可以深入追问的方向

以JSON格式返回：
{{
    "emotional_state": "观察到的情绪",
    "blind_spots": ["盲点1", "盲点2"],
    "contradictions": ["矛盾1"],
    "hidden_assumptions": ["隐含假设1"],
    "deeper_questions": ["可深入的问题1", "问题2"],
    "overall_analysis": "总体分析"
}}
"""
        system_prompt = "你是一个专业的哲学咨询分析师。"
        response = await llm.generate(system_prompt, prompt)

        # Parse JSON response
        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            return data

        return {"analysis": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review")
async def review_session(request: ReviewRequest):
    """
    Review completed session and provide:
    - Key moments
    - Missed opportunities
    - Suggestions for improvement
    - Client progress assessment
    """
    try:
        # Format dialogue
        dialogue_text = "\n".join([
            f"{'来访者' if t.get('role') == 'user' else '咨询师'}：{t.get('content', '')}"
            for t in request.dialogue_history[-20:]  # Last 20 turns
        ])

        prompt = f"""作为哲学咨询督导，请复盘以下咨询会话。

对话记录：
{dialogue_text}

关注重点：{request.focus_area or '整体表现'}

请从以下角度给出反馈：
1. 关键节点分析（3-5个重要时刻）
2. 错过的追问机会
3. 可以改进的地方
4. 来访者的进步表现
5. 下次咨询的建议

以JSON格式返回：
{{
    "key_moments": [
        {{"turn": 3, "type": "突破/回避/矛盾等", "description": "描述"}}
    ],
    "missed_opportunities": ["错过的机会1", "机会2"],
    "improvements": ["改进建议1", "建议2"],
    "client_progress": "来访者进步描述",
    "next_session_focus": "下次建议重点"
}}
"""
        system_prompt = "你是一个经验丰富的哲学咨询督导。"
        response = await llm.generate(system_prompt, prompt)

        # Parse JSON response
        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            return data

        return {"review": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safety-check")
async def check_message_safety(request: ClientMessage):
    """
    Check if client message requires safety intervention.

    Returns safety assessment and recommended response.
    """
    result = safeguard.check_user_input(request.client_message)

    response_guide = ""
    if not result.is_safe:
        if result.trigger_type == "crisis_keyword":
            response_guide = "建议立即进行危机干预，提供专业帮助资源"
        elif result.trigger_type == "extreme_emotion":
            response_guide = "建议先认可情绪，不急于解决问题"
        elif result.trigger_type == "boundary_topic":
            response_guide = "温和引导回哲学讨论，或建议寻求专业帮助"

    return {
        "is_safe": result.is_safe,
        "risk_level": result.risk_level.value,
        "trigger_type": result.trigger_type,
        "response_guide": response_guide,
        "message": result.message
    }
