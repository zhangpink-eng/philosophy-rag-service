#!/usr/bin/env python3
"""
Dialogue Manager - Oscar哲学咨询对话管理器。
负责：
1. 对话状态跟踪
2. 咨询阶段管理
3. 技巧选择决策
4. 对话策略执行

Usage:
    dm = DialogueManager()
    state = dm.start_session(user_id)
    response = dm.process_message(state, user_message)
"""

import json
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from datetime import datetime
from pathlib import Path


class ConsultationPhase(Enum):
    """咨询阶段"""
    GREETING = "greeting"           # 开场寒暄
    PROBLEM_EXPLORATION = "problem_exploration"  # 问题探索
    FOCUSING = "focusing"           # 聚焦问题
    LOGICAL_EXPLORATION = "logical_exploration"  # 逻辑探索
    CONCEPT_CLARIFICATION = "concept_clarification"  # 概念澄清
    INTEGRATION = "integration"     # 整合反思
    CLOSING = "closing"            # 结束评估


class DialogueTechnique(Enum):
    """对话技巧"""
    SOCRATIC_QUESTION = "socratic_question"       # 苏格拉底追问
    LOGICAL_CHALLENGE = "logical_challenge"      # 逻辑挑战
    SIMPLIFICATION = "simplification"            # 简化问题
    BINARY_CHOICE = "binary_choice"             # 二选一
    STOP_AND_BREATHE = "stop_and_breathe"       # 叫停呼吸
    ACCEPT_CONFUSION = "accept_confusion"        # 接受困惑
    PARAPHRASE = "paraphrase"                   # 复述确认
    COUNTERFACTUAL = "counterfactual"            # 反事实
    EMPATHIC_REFLECTION = "empathic_reflection"  # 共情反映
    INTEGRATION = "integration"                  # 整合反思


@dataclass
class DialogueTurn:
    """对话回合"""
    turn_id: int
    speaker: str  # "oscar" or "user"
    message: str
    technique_used: Optional[str] = None
    emotional_state: Optional[str] = None
    timestamp: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class ConsultationState:
    """咨询状态"""
    session_id: str
    user_id: str
    phase: ConsultationPhase
    turns: List[DialogueTurn]
    current_topic: Optional[str] = None
    detected_emotions: List[str] = field(default_factory=list)
    key_insights: List[str] = field(default_factory=list)
    contradictions_found: List[str] = field(default_factory=list)
    questions_asked: int = 0
    user_agreements: int = 0
    user_resistance: int = 0
    last_technique: Optional[str] = None
    session_start: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class OscarResponse:
    """Oscar的响应"""
    message: str
    technique: DialogueTechnique
    next_phase_suggestion: ConsultationPhase
    emotional_note: Optional[str] = None
    suggestions_for_next: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class DialogueManager:
    """
    Oscar哲学咨询对话管理器。
    基于从语料中提取的咨询模式和技巧运作。
    """

    def __init__(self, persona_path: str = "data/persona/oscar_persona.json"):
        self.session_states: Dict[str, ConsultationState] = {}
        self.persona = self._load_persona(persona_path)
        self.turn_counter = 0

        # 阶段转换规则
        self.phase_transitions = {
            ConsultationPhase.GREETING: self._should_transition_from_greeting,
            ConsultationPhase.PROBLEM_EXPLORATION: self._should_transition_from_exploration,
            ConsultationPhase.FOCUSING: self._should_transition_from_focusing,
            ConsultationPhase.LOGICAL_EXPLORATION: self._should_transition_from_logical,
            ConsultationPhase.CONCEPT_CLARIFICATION: self._should_transition_from_clarification,
            ConsultationPhase.INTEGRATION: self._should_transition_from_integration,
        }

        # 技巧选择策略
        self.technique_selection = {
            "high_anxiety": [DialogueTechnique.STOP_AND_BREATHE, DialogueTechnique.ACCEPT_CONFUSION],
            "contradiction_detected": [DialogueTechnique.LOGICAL_CHALLENGE, DialogueTechnique.SIMPLIFICATION],
            "vague_response": [DialogueTechnique.SOCRATIC_QUESTION, DialogueTechnique.BINARY_CHOICE],
            "emotional_block": [DialogueTechnique.EMPATHIC_REFLECTION, DialogueTechnique.STOP_AND_BREATHE],
            "agreement": [DialogueTechnique.SOCRATIC_QUESTION, DialogueTechnique.LOGICAL_CHALLENGE],
            "resistance": [DialogueTechnique.ACCEPT_CONFUSION, DialogueTechnique.SIMPLIFICATION],
            "insight_moment": [DialogueTechnique.PARAPHRASE, DialogueTechnique.INTEGRATION],
        }

        # Oscar的核心话术模板
        self.oscar_templates = self._load_templates()

    def _load_persona(self, path: str) -> Dict:
        """加载人格画像"""
        try:
            persona_file = Path(path)
            if persona_file.exists():
                return json.loads(persona_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return self._get_default_persona()

    def _get_default_persona(self) -> Dict:
        """默认人格画像"""
        return {
            "name": "Oscar",
            "communication_style": {
                "response_length": "简短，10-30词",
                "tone": "直接、冷静、挑战性但不评判"
            },
            "core_techniques": {
                "苏格拉底追问": {"weight": 0.3},
                "逻辑挑战": {"weight": 0.25},
                "简化聚焦": {"weight": 0.2},
                "叫停技巧": {"weight": 0.15},
                "接受困惑": {"weight": 0.1}
            }
        }

    def _load_templates(self) -> Dict[str, List[str]]:
        """加载Oscar话术模板"""
        return {
            # 开场
            "greeting": [
                "Hello, what's the reason you wanted to speak with me?",
                "So, what brings you here today?",
                "What would you like to discuss?",
            ],
            # 苏格拉底追问
            "socratic_question": [
                "What do you mean by that?",
                "Can you define what that means for you?",
                "If that's true, then what follows?",
                "Why do you think that is?",
                "What evidence do you have for that?",
            ],
            # 逻辑挑战
            "logical_challenge": [
                "But you said earlier that...",
                "So you agree that X, but also claim Y?",
                "There's a contradiction here, don't you think?",
                "How do you reconcile these two statements?",
            ],
            # 简化问题
            "simplification": [
                "In one word, what is it?",
                "What's the main issue here?",
                "Can you simplify that?",
                "What is the core of this problem?",
                "Let's focus on the essential.",
            ],
            # 二选一
            "binary_choice": [
                "Is it A or B?",
                "Yes or no?",
                "Do you prefer X or Y?",
                "Is this about X or about Y?",
            ],
            # 叫停
            "stop_and_breathe": [
                "Stop. Breathe.",
                "Calm down.",
                "Don't speak too much.",
                "Take a breath.",
                "Slow down.",
            ],
            # 接受困惑
            "accept_confusion": [
                "You don't understand, and that's okay.",
                "I don't understand either, let's try again.",
                "Not knowing is part of the process.",
                "Confusion is normal.",
            ],
            # 复述
            "paraphrase": [
                "So what you're saying is...",
                "Let me make sure I understand...",
                "In other words, you feel that...",
            ],
            # 反事实
            "counterfactual": [
                "If you could change one thing, what would it be?",
                "Imagine if X were true, would Y still apply?",
                "Suppose you had unlimited resources, how would you approach this?",
            ],
            # 共情
            "empathic_reflection": [
                "I can see this is difficult for you.",
                "This seems to be an important issue.",
                "You're right to think carefully about this.",
            ],
            # 整合
            "integration": [
                "So what have we discovered?",
                "Let me summarize what we've discussed.",
                "What is the main takeaway for you?",
            ],
            # 结束
            "closing": [
                "Before you go, did you like our discussion?",
                "What was most useful for you today?",
                "Do you have any final thoughts?",
            ],
            # 确认理解
            "check_understanding": [
                "Do you understand what I'm saying?",
                "Is that clear?",
                "Does that make sense to you?",
            ],
        }

    def start_session(self, user_id: str, initial_topic: str = None) -> ConsultationState:
        """开始新的咨询会话"""
        session_id = str(uuid.uuid4())[:8]
        state = ConsultationState(
            session_id=session_id,
            user_id=user_id,
            phase=ConsultationPhase.GREETING,
            turns=[],
            current_topic=initial_topic,
            session_start=datetime.now().isoformat()
        )
        self.session_states[session_id] = state
        self.turn_counter = 0
        return state

    def get_session(self, session_id: str) -> Optional[ConsultationState]:
        """获取会话状态"""
        return self.session_states.get(session_id)

    def process_message(
        self,
        state: ConsultationState,
        user_message: str
    ) -> OscarResponse:
        """
        处理用户消息并返回Oscar的响应。

        Args:
            state: 当前咨询状态
            user_message: 用户输入

        Returns:
            OscarResponse: Oscar的响应
        """
        self.turn_counter += 1

        # 记录用户消息
        user_turn = DialogueTurn(
            turn_id=self.turn_counter,
            speaker="user",
            message=user_message,
            timestamp=datetime.now().isoformat()
        )
        state.turns.append(user_turn)

        # 分析用户消息
        emotion = self._detect_emotion(user_message)
        if emotion:
            state.detected_emotions.append(emotion)

        has_contradiction = self._detect_contradiction(user_message, state)
        if has_contradiction:
            state.contradictions_found.append(has_contradiction)

        # 检查用户响应特征
        is_resistance = self._detect_resistance(user_message)
        is_agreement = self._detect_agreement(user_message)
        is_vague = self._detect_vagueness(user_message)

        if is_resistance:
            state.user_resistance += 1
        if is_agreement:
            state.user_agreements += 1

        # 选择技巧
        technique = self._select_technique(
            state,
            emotion=emotion,
            has_contradiction=has_contradiction,
            is_resistance=is_resistance,
            is_agreement=is_agreement,
            is_vague=is_vague
        )

        # 生成响应
        oscar_message = self._generate_response(state, technique)
        state.last_technique = technique.value

        # 记录Oscar消息
        oscar_turn = DialogueTurn(
            turn_id=self.turn_counter,
            speaker="oscar",
            message=oscar_message,
            technique_used=technique.value,
            emotional_state=emotion,
            timestamp=datetime.now().isoformat()
        )
        state.turns.append(oscar_turn)

        state.questions_asked += 1

        # 确定下一阶段
        next_phase = self._determine_next_phase(state, technique)

        # 创建响应
        response = OscarResponse(
            message=oscar_message,
            technique=technique,
            next_phase_suggestion=next_phase,
            emotional_note=emotion if emotion in ["anxiety", "defensive"] else None,
            suggestions_for_next=self._get_suggestions(technique, state)
        )

        return response

    def _detect_emotion(self, message: str) -> Optional[str]:
        """检测情绪状态"""
        message_lower = message.lower()

        emotion_patterns = {
            "anxiety": ["anxious", "nervous", "worried", "stress", "紧张", "焦虑"],
            "defensive": ["but", "however", "defensive", "抗拒", "可是"],
            "frustration": ["frustrated", "stuck", "can't", "unable", "挫败"],
            "openness": ["yes", "I see", "understand", "明白了", "是的"],
            "confusion": ["confused", "don't understand", "困惑", "不明白"],
        }

        for emotion, patterns in emotion_patterns.items():
            if any(p in message_lower for p in patterns):
                return emotion
        return None

    def _detect_contradiction(self, message: str, state: ConsultationState) -> Optional[str]:
        """检测逻辑矛盾"""
        message_lower = message.lower()

        # 检查是否与之前说的矛盾
        previous_statements = [t.message.lower() for t in state.turns if t.speaker == "user"]

        contradiction_markers = ["but", "however", "although", "actually"]
        if any(marker in message_lower for marker in contradiction_markers):
            # 简单的矛盾检测：如果用户改变立场或说"其实不是"
            for prev in previous_statements[-3:]:
                if ("yes" in prev or "I agree" in prev) and ("no" in message_lower or "but" in message_lower):
                    return "用户似乎在改变立场"

        return None

    def _detect_resistance(self, message: str) -> bool:
        """检测抗拒"""
        message_lower = message.lower()
        resistance_patterns = ["but", "however", "I don't know", "maybe", "I guess", "可是", "但是", "不确定"]
        return any(p in message_lower for p in resistance_patterns)

    def _detect_agreement(self, message: str) -> bool:
        """检测认同"""
        message_lower = message.lower()
        agreement_patterns = ["yes", "yeah", "I see", "I understand", "exactly", "对的", "是的", "明白"]
        return any(p in message_lower for p in agreement_patterns)

    def _detect_vagueness(self, message: str) -> bool:
        """检测模糊回答"""
        message_lower = message.lower()
        vague_patterns = ["something", "maybe", "kind of", "sort of", "perhaps", "大概", "可能", "也许"]
        word_count = len(message.split())
        return any(p in message_lower for p in vague_patterns) or (word_count > 50 and "?" not in message)

    def _select_technique(
        self,
        state: ConsultationState,
        emotion: str = None,
        has_contradiction: str = None,
        is_resistance: bool = False,
        is_agreement: bool = False,
        is_vague: bool = False
    ) -> DialogueTechnique:
        """根据当前状态选择合适的技巧"""
        # 首先检查特殊情况

        # 高焦虑情绪
        if emotion == "anxiety":
            return DialogueTechnique.STOP_AND_BREATHE

        # 检测到矛盾
        if has_contradiction:
            return DialogueTechnique.LOGICAL_CHALLENGE

        # 模糊回答
        if is_vague:
            return DialogueTechnique.SIMPLIFICATION

        # 抗拒
        if is_resistance and state.user_resistance >= 2:
            return DialogueTechnique.ACCEPT_CONFUSION

        # 认同时刻 - 趁热追问
        if is_agreement and state.questions_asked > 2:
            return DialogueTechnique.SOCRATIC_QUESTION

        # 根据阶段选择
        if state.phase == ConsultationPhase.GREETING:
            return DialogueTechnique.SOCRATIC_QUESTION
        elif state.phase == ConsultationPhase.PROBLEM_EXPLORATION:
            return DialogueTechnique.SIMPLIFICATION
        elif state.phase == ConsultationPhase.LOGICAL_EXPLORATION:
            return DialogueTechnique.LOGICAL_CHALLENGE
        elif state.phase == ConsultationPhase.CONCEPT_CLARIFICATION:
            return DialogueTechnique.BINARY_CHOICE
        elif state.phase == ConsultationPhase.CLOSING:
            return DialogueTechnique.PARAPHRASE

        # 默认使用苏格拉底追问
        return DialogueTechnique.SOCRATIC_QUESTION

    def _generate_response(self, state: ConsultationState, technique: DialogueTechnique) -> str:
        """生成Oscar的响应"""
        templates = self.oscar_templates

        # 根据技巧选择模板
        template_key = technique.value.replace("_", "_")
        available_templates = templates.get(template_key, templates["socratic_question"])

        # 阶段特定的开场白
        if state.phase == ConsultationPhase.GREETING and len(state.turns) <= 2:
            available_templates = templates["greeting"]

        # 选择一个模板（可以添加随机性）
        template = available_templates[0]  # 简化：使用第一个

        # 如果需要，加入上下文特定的修改
        message = template

        # 针对某些技巧的特殊处理
        if technique == DialogueTechnique.LOGICAL_CHALLENGE and state.contradictions_found:
            message = f"{state.contradictions_found[-1]}。{message}"

        if technique == DialogueTechnique.SIMPLIFICATION:
            # 聚焦于当前话题
            if state.current_topic:
                message = f"What is the main issue regarding {state.current_topic}? {message}"

        if technique == DialogueTechnique.STOP_AND_BREATHE:
            # 检查是否真的需要叫停
            if state.detected_emotions and "anxiety" not in state.detected_emotions[-3:]:
                message = templates["socratic_question"][0]  # 换成追问

        return message

    def _determine_next_phase(self, state: ConsultationState, technique: DialogueTechnique) -> ConsultationPhase:
        """确定下一阶段"""
        turn_count = len([t for t in state.turns if t.speaker == "user"])

        # 阶段转换逻辑
        if turn_count <= 1:
            return ConsultationPhase.GREETING
        elif turn_count <= 3:
            return ConsultationPhase.PROBLEM_EXPLORATION
        elif turn_count <= 6:
            return ConsultationPhase.FOCUSING
        elif turn_count <= 10:
            return ConsultationPhase.LOGICAL_EXPLORATION
        elif turn_count <= 14:
            return ConsultationPhase.CONCEPT_CLARIFICATION
        elif turn_count <= 18:
            return ConsultationPhase.INTEGRATION
        else:
            return ConsultationPhase.CLOSING

    def _should_transition_from_greeting(self, state: ConsultationState) -> bool:
        """判断是否应从开场阶段转换"""
        return len([t for t in state.turns if t.speaker == "user"]) >= 1

    def _should_transition_from_exploration(self, state: ConsultationState) -> bool:
        """判断是否应从问题探索阶段转换"""
        return state.questions_asked >= 2

    def _should_transition_from_focusing(self, state: ConsultationState) -> bool:
        """判断是否应从聚焦阶段转换"""
        return state.current_topic is not None or state.questions_asked >= 4

    def _should_transition_from_logical(self, state: ConsultationState) -> bool:
        """判断是否应从逻辑探索阶段转换"""
        return len(state.contradictions_found) >= 2

    def _should_transition_from_clarification(self, state: ConsultationState) -> bool:
        """判断是否应从概念澄清阶段转换"""
        return state.user_agreements >= 2

    def _should_transition_from_integration(self, state: ConsultationState) -> bool:
        """判断是否应从整合阶段转换"""
        return len(state.key_insights) >= 1

    def _get_suggestions(self, technique: DialogueTechnique, state: ConsultationState) -> List[str]:
        """获取下一步建议"""
        suggestions = []

        if technique == DialogueTechnique.LOGICAL_CHALLENGE:
            suggestions.append("准备接受用户的辩解或认同")
        elif technique == DialogueTechnique.SOCRATIC_QUESTION:
            suggestions.append("等待用户澄清或解释")
        elif technique == DialogueTechnique.STOP_AND_BREATHE:
            suggestions.append("观察用户是否冷静下来")
        elif technique == DialogueTechnique.SIMPLIFICATION:
            suggestions.append("如果用户仍模糊，继续简化或二选一")

        return suggestions

    def end_session(self, session_id: str) -> Dict:
        """结束会话并返回摘要"""
        state = self.session_states.get(session_id)
        if not state:
            return {"error": "Session not found"}

        summary = {
            "session_id": session_id,
            "duration": len(state.turns),
            "phases_visited": [p.value for p in ConsultationPhase],
            "techniques_used": list(set(t.technique_used for t in state.turns if t.technique_used)),
            "emotions_detected": state.detected_emotions,
            "contradictions_found": state.contradictions_found,
            "questions_asked": state.questions_asked,
            "user_agreements": state.user_agreements,
            "user_resistance": state.user_resistance,
            "key_insights": state.key_insights,
        }

        # 清理状态
        del self.session_states[session_id]

        return summary

    def get_session_history(self, session_id: str) -> List[Dict]:
        """获取会话历史"""
        state = self.session_states.get(session_id)
        if not state:
            return []

        return [
            {
                "turn_id": t.turn_id,
                "speaker": t.speaker,
                "message": t.message,
                "technique": t.technique_used,
                "timestamp": t.timestamp
            }
            for t in state.turns
        ]

    def export_session_log(self, session_id: str, output_path: str = None) -> str:
        """导出会话日志"""
        state = self.session_states.get(session_id)
        if not state:
            return ""

        log = f"# Consultation Session {session_id}\n"
        log += f"User: {state.user_id}\n"
        log += f"Start: {state.session_start}\n"
        log += f"Phase: {state.phase.value}\n\n"
        log += "## Dialogue\n\n"

        for turn in state.turns:
            speaker = "Oscar" if turn.speaker == "oscar" else "User"
            log += f"**{speaker}** (Turn {turn.turn_id})"
            if turn.technique_used:
                log += f" - [{turn.technique_used}]"
            log += f"\n{turn.message}\n\n"

        if output_path:
            Path(output_path).write_text(log, encoding="utf-8")

        return log


def demo():
    """演示DialogueManager的使用"""
    print("=" * 60)
    print("Oscar Dialogue Manager Demo")
    print("=" * 60)

    dm = DialogueManager()

    # 开始会话
    state = dm.start_session(user_id="demo_user")
    print(f"\n[Session Started] {state.session_id}")

    # 模拟对话
    user_inputs = [
        "I want to talk about my work-life balance.",
        "It's been really stressful lately. I feel like I can't keep up.",
        "Yes, I think I need to make some changes.",
        "I guess... but it's complicated.",
    ]

    for user_msg in user_inputs:
        print(f"\n[User] {user_msg}")

        response = dm.process_message(state, user_msg)

        print(f"[Oscar] {response.message}")
        print(f"  Technique: {response.technique.value}")
        print(f"  Next Phase: {response.next_phase_suggestion.value}")

    # 结束会话
    summary = dm.end_session(state.session_id)
    print(f"\n[Session Ended]")
    print(f"Questions asked: {summary['questions_asked']}")
    print(f"Techniques used: {summary['techniques_used']}")


if __name__ == "__main__":
    demo()
