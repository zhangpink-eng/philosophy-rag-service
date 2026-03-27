from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class RiskLevel(Enum):
    """Risk level for safety assessment"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRISIS = "crisis"


@dataclass
class SafetyCheckResult:
    """Result of safety check"""
    is_safe: bool
    risk_level: RiskLevel
    trigger_type: Optional[str] = None  # crisis_keyword, emotion_extreme, boundary议题, etc.
    message: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class CrisisHotline:
    """Crisis hotline information"""
    name: str
    phone: str


class SafeGuard:
    """
    Safety boundary and ethical control for philosophical consultation.

    Three-layer protection:
    1. Real-time content filtering (every turn)
    2. Boundary recognition (continuous monitoring)
    3. Ethical audit (post-analysis)
    """

    # Crisis keywords (Chinese)
    CRISIS_KEYWORDS = [
        # Self-harm
        r"想死",
        r"不想活了",
        r"活着没意思",
        r"死了算了",
        r"自杀",
        r"自残",
        r"割腕",
        r"跳楼",
        r"吃安眠药",
        r"结束生命",
        r"轻生",

        # Suicide attempts
        r"想自杀",
        r"要自杀",
        r"计划自杀",
        r"遗嘱",
        r"告别",

        # Extreme despair
        r"绝望",
        r"彻底崩溃",
        r"无法承受",
        r"生无可恋",
        r"人生没有意义",
    ]

    # High-risk emotional patterns
    EXTREME_EMOTION_PATTERNS = [
        r"(极其|非常|特别)痛苦",
        r"(完全|彻底)绝望",
        r"(实在|真的)活不下去了",
        r"没有(任何|一点)希望",
        r"太(痛苦|绝望|累了)了",
    ]

    # Boundary topics (需要专业帮助的领域)
    BOUNDARY_TOPICS = {
        "心理疾病": ["抑郁症", "躁郁症", "精神分裂", "焦虑症", "强迫症", " PTSD", "创伤"],
        "药物治疗": ["吃药", "药物", "剂量", "处方", "精神科"],
        "医疗诊断": ["诊断", "医院", "住院", "治疗方案"],
        "法律问题": ["起诉", "律师", "法律", "警察", "犯罪"],
        "危机情况": ["危机", "热线", "急救", "自杀念头"],
    }

    # Crisis hotlines
    HOTLINES = [
        CrisisHotline("全国心理援助热线", "400-161-9995"),
        CrisisHotline("北京心理危机研究与干预中心", "010-82951332"),
        CrisisHotline("生命热线", "400-821-1215"),
        CrisisHotline("希望24热线", "400-161-9995"),
    ]

    def __init__(self):
        self.crisis_patterns = [re.compile(p, re.IGNORECASE) for p in self.CRISIS_KEYWORDS]
        self.emotion_patterns = [re.compile(p, re.IGNORECASE) for p in self.EXTREME_EMOTION_PATTERNS]

    def check_user_input(self, text: str) -> SafetyCheckResult:
        """
        Check user input for safety concerns.

        Args:
            text: User's input text

        Returns:
            SafetyCheckResult with assessment
        """
        if not text or not text.strip():
            return SafetyCheckResult(is_safe=True, risk_level=RiskLevel.LOW)

        text = text.strip()

        # Check for crisis keywords
        crisis_match = self._check_crisis_keywords(text)
        if crisis_match:
            return crisis_match

        # Check for extreme emotions
        emotion_check = self._check_extreme_emotions(text)
        if emotion_check:
            return emotion_check

        # Check for boundary topics
        boundary_check = self._check_boundary_topics(text)
        if boundary_check:
            return boundary_check

        return SafetyCheckResult(is_safe=True, risk_level=RiskLevel.LOW)

    def _check_crisis_keywords(self, text: str) -> Optional[SafetyCheckResult]:
        """Check for crisis keywords"""
        for pattern in self.crisis_patterns:
            if pattern.search(text):
                return SafetyCheckResult(
                    is_safe=False,
                    risk_level=RiskLevel.CRISIS,
                    trigger_type="crisis_keyword",
                    message=self._get_crisis_response(),
                    suggestion="immediate_intervention"
                )
        return None

    def _check_extreme_emotions(self, text: str) -> Optional[SafetyCheckResult]:
        """Check for extreme emotional expressions"""
        matches = []
        for pattern in self.emotion_patterns:
            if pattern.search(text):
                matches.append(pattern.pattern)

        if len(matches) >= 2:  # Multiple extreme emotion patterns
            return SafetyCheckResult(
                is_safe=False,
                risk_level=RiskLevel.HIGH,
                trigger_type="extreme_emotion",
                message="我注意到你现在可能正在经历很大的痛苦。",
                suggestion="gentle_acknowledgment"
            )

        if matches:
            return SafetyCheckResult(
                is_safe=True,
                risk_level=RiskLevel.MEDIUM,
                trigger_type="elevated_emotion",
                message=None,
                suggestion="monitor"
            )

        return None

    def _check_boundary_topics(self, text: str) -> Optional[SafetyCheckResult]:
        """Check for topics that require professional help"""
        detected_topics = []

        for topic, keywords in self.BOUNDARY_TOPICS.items():
            for keyword in keywords:
                if keyword in text:
                    detected_topics.append(topic)
                    break

        if detected_topics:
            # Check if it's philosophical discussion vs seeking professional help
            if self._is_philosophical_context(text, detected_topics):
                return SafetyCheckResult(
                    is_safe=True,
                    risk_level=RiskLevel.LOW,
                    message=None,
                    suggestion="continue_with_caution"
                )
            else:
                return SafetyCheckResult(
                    is_safe=False,
                    risk_level=RiskLevel.MEDIUM,
                    trigger_type="boundary_topic",
                    message=self._get_boundary_redirect_message(detected_topics),
                    suggestion="redirect_to_professional"
                )

        return None

    def _is_philosophical_context(self, text: str, topics: List[str]) -> bool:
        """判断是否是哲学性讨论而非寻求专业帮助"""
        philosophical_indicators = [
            "什么是", "为什么", "如何理解",
            "哲学", "思考", "讨论",
            "有人说", "我认为", "我觉得"
        ]

        has_philosophical_language = any(ind in text for ind in philosophical_indicators)

        # 如果包含哲学性语言，认为是哲学讨论
        return has_philosophical_language

    def _get_crisis_response(self) -> str:
        """Get crisis response message"""
        hotline_text = "\n".join([f"- {h.name}：{h.phone}" for h in self.HOTLINES])

        return f"""我注意到你现在可能正在经历很大的困难。

作为哲学对话的引导者，我的能力是有限的。如果你正在经历心理上的痛苦，我建议你联系专业的心理援助：

{hotline_text}

我们可以暂停休息，也可以继续哲学对话。你想怎么做？"""

    def _get_boundary_redirect_message(self, topics: List[str]) -> str:
        """Get boundary redirect message"""
        topics_text = "、".join(topics[:2])  # 最多显示2个话题

        return f"""这个问题涉及到{topics_text}领域，这些领域需要专业人士的帮助。

哲学可以帮助你思考问题的本质和你的立场，但对于具体的医疗、法律或心理健康问题，建议你咨询相关专业人士。

我们可以继续讨论相关的哲学问题，你想探索哪个方向？"""

    def check_ai_response(self, response: str) -> SafetyCheckResult:
        """
        Check AI response for safety concerns.

        Args:
            response: AI's generated response

        Returns:
            SafetyCheckResult with assessment
        """
        if not response or not response.strip():
            return SafetyCheckResult(is_safe=True, risk_level=RiskLevel.LOW)

        # Check for potentially harmful advice
        harmful_patterns = [
            (r"你应该.*药", "不提供药物建议"),
            (r"去.*医院.*治疗", "不提供医疗建议"),
            (r"我建议你.*医生", "不推荐具体医生"),
        ]

        for pattern, concern in harmful_patterns:
            if re.search(pattern, response):
                return SafetyCheckResult(
                    is_safe=False,
                    risk_level=RiskLevel.MEDIUM,
                    trigger_type="inappropriate_advice",
                    message=f"注意：{concern}。请调整回复。",
                    suggestion="rephrase"
                )

        return SafetyCheckResult(is_safe=True, risk_level=RiskLevel.LOW)

    def assess_session_risk(self, dialogue_history: List[Dict]) -> Tuple[RiskLevel, List[str]]:
        """
        Assess overall session risk based on dialogue history.

        Args:
            dialogue_history: List of dialogue turns

        Returns:
            (RiskLevel, list of risk indicators)
        """
        risk_indicators = []
        crisis_count = 0
        high_risk_count = 0

        for turn in dialogue_history:
            content = turn.get("content", "")
            check = self.check_user_input(content)

            if check.risk_level == RiskLevel.CRISIS:
                crisis_count += 1
                risk_indicators.append(f"危机信号: {content[:50]}...")
            elif check.risk_level == RiskLevel.HIGH:
                high_risk_count += 1
                risk_indicators.append(f"高风险信号: {content[:50]}...")

        # Determine overall risk
        if crisis_count > 0:
            return RiskLevel.CRISIS, risk_indicators
        elif high_risk_count >= 3:
            return RiskLevel.HIGH, risk_indicators
        elif high_risk_count > 0:
            return RiskLevel.MEDIUM, risk_indicators
        else:
            return RiskLevel.LOW, []

    def generate_safety_prompt_injection(self, check_result: SafetyCheckResult) -> str:
        """
        Generate prompt injection for safety guidance.

        Args:
            check_result: Result from safety check

        Returns:
            String to inject into prompt
        """
        if check_result.is_safe:
            return ""

        if check_result.trigger_type == "crisis_keyword":
            return """

【安全注意】
用户可能处于危机状态。请：
1. 表达关心和理解
2. 不评判、不质疑
3. 提供专业帮助资源
4. 询问是否需要暂停
5. 保持对话开放，让用户决定下一步
"""

        elif check_result.trigger_type == "extreme_emotion":
            return """

【情绪注意】
用户表达了强烈的负面情绪。请：
1. 先认可情绪
2. 不急于解决问题
3. 温和询问原因
4. 如持续高涨，考虑提醒休息
"""

        elif check_result.trigger_type == "boundary_topic":
            return """

【边界注意】
用户问题涉及专业领域（如心理疾病、法律等）。请：
1. 避免给出具体医疗/法律建议
2. 引导回 Philosopher 角色定位
3. 温和建议寻求专业帮助
4. 可以讨论相关哲学问题
"""

        return ""
