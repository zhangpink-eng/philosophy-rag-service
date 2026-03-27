from typing import Dict, List, Optional
from dataclasses import dataclass
from core.llm_client import LLMClient


@dataclass
class QualityScore:
    """Quality score for a session or turn"""
    depth_score: float = 0.0  # 0-10
    contradiction_score: float = 0.0  # 0-10
    insight_score: float = 0.0  # 0-10
    engagement_score: float = 0.0  # 0-10
    style_score: float = 0.0  # 0-10

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score"""
        return (
            self.depth_score * 0.30 +
            self.contradiction_score * 0.20 +
            self.insight_score * 0.25 +
            self.engagement_score * 0.15 +
            self.style_score * 0.10
        )

    def to_dict(self) -> Dict:
        return {
            "overall": round(self.overall_score, 2),
            "depth": round(self.depth_score, 2),
            "contradiction": round(self.contradiction_score, 2),
            "insight": round(self.insight_score, 2),
            "engagement": round(self.engagement_score, 2),
            "style": round(self.style_score, 2)
        }


@dataclass
class QualityReport:
    """Complete quality evaluation report"""
    session_id: str
    quality_score: QualityScore
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[str]
    key_moments: List[Dict]  # [{"turn": int, "type": str, "description": str}]
    summary: str


class QualityEvaluator:
    """
    Evaluate dialogue quality for philosophical consultation.

    Dimensions:
    - Depth (30%): 是否从表面走向深层问题
    - Contradiction (20%): 是否成功暴露思维矛盾
    - Insight (25%): 用户是否产生新认知
    - Engagement (15%): 用户是否积极参与
    - Style (10%): AI是否符合Oscar风格
    """

    def __init__(self):
        self.llm = LLMClient()

    async def evaluate_session(
        self,
        dialogue_history: List[Dict],
        scenario: str = "consultation"
    ) -> QualityReport:
        """
        Evaluate a complete session.

        Args:
            dialogue_history: List of dialogue turns [{"role": "user/oscar", "content": str}]
            scenario: consultation/supervision/workshop

        Returns:
            QualityReport with full evaluation
        """
        if not dialogue_history:
            return self._empty_report("")

        # Format dialogue for analysis
        dialogue_text = self._format_dialogue(dialogue_history)

        # Get LLM-based evaluation
        prompt = self._build_evaluation_prompt(dialogue_text, scenario)

        try:
            system_prompt = "You are a philosophical consultation quality evaluator."
            response = await self.llm.generate(system_prompt, prompt)

            # Parse response into structured report
            report = self._parse_evaluation_response(response, dialogue_history)
            return report
        except Exception as e:
            print(f"Error in quality evaluation: {e}")
            return self._fallback_report(dialogue_history)

    def evaluate_turn(
        self,
        context: List[Dict],
        ai_response: str
    ) -> Dict:
        """
        Evaluate a single turn (for real-time feedback in assistant mode).

        Args:
            context: Previous dialogue history
            ai_response: AI's response to evaluate

        Returns:
            Dict with scores and suggestions
        """
        # Check response length
        response_length = len(ai_response)

        # Check for question (Oscar typically asks questions)
        has_question = "？" in ai_response or "?" in ai_response

        # Check for confrontation (Oscar style)
        confrontation_words = ["但是", "然而", "矛盾", "不一致", "真的吗", "你确定"]
        has_confrontation = any(word in ai_response for word in confrontation_words)

        # Check for silence/short response (Oscar sometimes stays silent)
        is_short = response_length < 20

        suggestions = []
        if not has_question and not is_short:
            suggestions.append("考虑用问题引导，而非陈述")
        if not has_confrontation:
            suggestions.append("可以更直接地指出矛盾")
        if response_length > 200:
            suggestions.append("回复偏长，考虑更简洁")

        return {
            "length_ok": 20 < response_length < 150,
            "has_question": has_question,
            "has_confrontation": has_confrontation,
            "is_appropriate_length": 20 < response_length < 150,
            "suggestions": suggestions
        }

    async def generate_improvement_suggestions(
        self,
        quality_report: QualityReport
    ) -> List[str]:
        """
        Generate improvement suggestions based on quality report.

        Args:
            quality_report: Quality evaluation report

        Returns:
            List of specific improvement suggestions
        """
        suggestions = []

        # Based on scores
        if quality_report.quality_score.depth_score < 5:
            suggestions.append("尝试问更深层的问题，引导用户探索核心问题")
        if quality_report.quality_score.contradiction_score < 5:
            suggestions.append("更积极地指出用户陈述中的逻辑矛盾")
        if quality_report.quality_score.insight_score < 5:
            suggestions.append("创造更多空间让用户产生自己的洞察")
        if quality_report.quality_score.engagement_score < 5:
            suggestions.append("使用更开放式的问题鼓励用户参与")
        if quality_report.quality_score.style_score < 5:
            suggestions.append("保持Oscar的直接、挑战性风格")

        # Based on weaknesses
        for weakness in quality_report.weaknesses:
            if "回避" in weakness:
                suggestions.append("避免被用户的话题转移带走")
            if "表面" in weakness:
                suggestions.append("追问更深层的原因和假设")
            if "过长" in weakness:
                suggestions.append("保持回复简洁有力")

        return suggestions[:5]  # Return top 5

    def _format_dialogue(self, dialogue_history: List[Dict]) -> str:
        """Format dialogue history for prompt"""
        lines = []
        for i, turn in enumerate(dialogue_history):
            role = "Client" if turn.get("role") == "user" else "Oscar"
            content = turn.get("content", "")
            lines.append(f"[{i+1}] {role}: {content}")
        return "\n".join(lines)

    def _build_evaluation_prompt(self, dialogue_text: str, scenario: str) -> str:
        """Build evaluation prompt"""
        return f"""请评估以下哲学咨询对话的质量。

场景: {scenario}

对话内容:
{dialogue_text}

请从以下维度评分（0-10分）：
1. 深度(Depth): 对话是否从表面问题走向深层探索
2. 矛盾暴露(Contradiction): 是否成功暴露用户的逻辑矛盾
3. 洞察产生(Insight): 用户是否产生了新的认知
4. 参与度(Engagement): 用户是否积极思考而非被动应答
5. 风格一致(Style): AI是否符合苏格拉底式对话风格

请以JSON格式返回评估结果：
{{
    "depth_score": 0-10,
    "contradiction_score": 0-10,
    "insight_score": 0-10,
    "engagement_score": 0-10,
    "style_score": 0-10,
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["缺点1", "缺点2"],
    "key_moments": [
        {{"turn": 3, "type": "insight", "description": "用户产生了重要洞察"}},
        {{"turn": 5, "type": "contradiction", "description": "暴露了逻辑矛盾"}}
    ],
    "summary": "整体评价"
}}

只返回JSON，不要有其他文字。"""

    def _parse_evaluation_response(
        self,
        response: str,
        dialogue_history: List[Dict]
    ) -> QualityReport:
        """Parse LLM response into QualityReport"""
        import json
        import re

        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())

                score = QualityScore(
                    depth_score=float(data.get("depth_score", 0)),
                    contradiction_score=float(data.get("contradiction_score", 0)),
                    insight_score=float(data.get("insight_score", 0)),
                    engagement_score=float(data.get("engagement_score", 0)),
                    style_score=float(data.get("style_score", 0))
                )

                return QualityReport(
                    session_id="",
                    quality_score=score,
                    strengths=data.get("strengths", []),
                    weaknesses=data.get("weaknesses", []),
                    improvement_suggestions=[],
                    key_moments=data.get("key_moments", []),
                    summary=data.get("summary", "")
                )
        except Exception as e:
            print(f"Parse error: {e}")

        return self._fallback_report(dialogue_history)

    def _fallback_report(self, dialogue_history: List[Dict]) -> QualityReport:
        """Generate fallback report when LLM evaluation fails"""
        # Simple heuristics-based evaluation
        user_turns = [t for t in dialogue_history if t.get("role") == "user"]
        oscar_turns = [t for t in dialogue_history if t.get("role") != "user"]

        # Count questions (Oscar style)
        question_count = sum(1 for t in oscar_turns if "？" in t.get("content", "") or "?" in t.get("content", ""))

        # Estimate engagement based on response length
        avg_user_length = sum(len(t.get("content", "")) for t in user_turns) / max(len(user_turns), 1)

        engagement = min(10, avg_user_length / 10)  # Rough estimate
        style = min(10, question_count / max(len(oscar_turns), 1) * 20)  # More questions = better style

        score = QualityScore(
            depth_score=5.0,  # Neutral
            contradiction_score=5.0,
            insight_score=engagement,
            engagement_score=engagement,
            style_score=style
        )

        return QualityReport(
            session_id="",
            quality_score=score,
            strengths=["对话正常进行"] if dialogue_history else ["无对话数据"],
            weaknesses=[],
            improvement_suggestions=["考虑增加更深层的追问"] if question_count < 3 else [],
            key_moments=[],
            summary="基于启发式的初步评估"
        )

    def _empty_report(self, session_id: str) -> QualityReport:
        """Return empty report"""
        return QualityReport(
            session_id=session_id,
            quality_score=QualityScore(),
            strengths=[],
            weaknesses=["无对话数据"],
            improvement_suggestions=[],
            key_moments=[],
            summary="无对话数据"
        )
