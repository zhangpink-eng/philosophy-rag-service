#!/usr/bin/env python3
"""
Prompt Builder - Oscar哲学咨询Prompt构建器。
基于人格画像、技能图谱和few-shot范例构建最优Prompt。

Usage:
    from core.prompt_builder import PromptBuilder
    builder = PromptBuilder()
    system_prompt = builder.build_system_prompt()
    user_prompt = builder.build_consultation_prompt(query, context, phase="exploration")
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class PromptConfig:
    """Prompt配置"""
    persona_enabled: bool = True
    skills_enabled: bool = True
    fewshot_enabled: bool = True
    tone: str = "direct"  # direct, gentle, formal
    response_length: str = "short"  # short, medium, long
    language: str = "bilingual"  # chinese, english, bilingual
    scenario: str = "consultation"  # consultation, supervision, workshop


@dataclass
class ConsultationContext:
    """咨询上下文"""
    user_id: str
    session_id: str
    current_topic: Optional[str] = None
    consultation_phase: str = "problem_exploration"
    user_emotional_state: Optional[str] = None
    techniques_used: List[str] = field(default_factory=list)
    key_insights: List[str] = field(default_factory=list)
    previous_turns: List[Dict] = field(default_factory=list)
    scenario: str = "consultation"  # consultation, supervision, workshop


class PromptBuilder:
    """
    Oscar哲学咨询Prompt构建器。
    """

    def __init__(
        self,
        persona_path: str = "data/persona/oscar_persona.json",
        skill_atlas_path: str = "data/skills/skill_atlas.json",
        fewshot_examples_path: str = "data/fewshot/examples.json"
    ):
        self.persona = self._load_json(persona_path)
        self.skill_atlas = self._load_json(skill_atlas_path)
        self.fewshot_examples = self._load_json(fewshot_examples_path)
        self.prompt_templates = self._load_templates()

        # 延迟导入避免循环依赖
        from data.prompts.scenario_templates import ScenarioTemplates
        self.scenario_templates = ScenarioTemplates()

    def _load_json(self, path: str) -> Dict:
        """加载JSON文件"""
        try:
            p = Path(path)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _load_templates(self) -> Dict[str, str]:
        """加载Prompt模板"""
        return {
            "system_prefix": """You are Oscar, a philosophical consultant specializing in Socratic dialogue and philosophical practice.

Your role is to guide clients through self-reflection using logical questioning, not to give advice or solutions.""",

            "persona_template": """## Your Character

- **Communication Style**: {style}
- **Response Length**: {length}
- **Tone**: {tone}

## Core Principles
{principles}

## Techniques You Use
{techniques}
""",

            "skill_template": """## Relevant Skills
{skills}
""",

            "fewshot_template": """## Examples of Your Approach

### Example: {topic}
**Dialogue:**
{dialogue}

**Key Moment**: {key_moment}
""",

            "consultation_prefix": """## Current Consultation Context
- **Topic**: {topic}
- **Phase**: {phase}
- **Emotional State**: {emotion}
""",

            "question_prompt": """## Your Task

As Oscar, respond to the client's latest message. Use your techniques appropriately:

{guidance}

Remember:
- Keep responses brief (10-30 words)
- Use questions to guide, not statements
- Challenge logical inconsistencies gently but directly
- Accept confusion as normal

**Your Response:**
""",

            "reflection_prompt": """## Session Reflection

Based on the consultation so far, provide:
1. A brief observation about the client's progress
2. A suggested technique for the next exchange
3. A possible insight the client might be approaching

**Reflection:**
""",

            "closing_prompt": """## Session Closing

The consultation is coming to an end. Guide the client through a brief reflection:

- What was most useful today?
- What is one key takeaway?
- Is there anything left unresolved?

**Closing Guidance:**
"""
        }

    def build_system_prompt(
        self,
        config: PromptConfig = None
    ) -> str:
        """
        构建完整的系统Prompt。

        Args:
            config: Prompt配置

        Returns:
            系统Prompt字符串
        """
        config = config or PromptConfig()

        parts = [self.prompt_templates["system_prefix"]]

        # 添加人格
        if config.persona_enabled and self.persona:
            persona_part = self._build_persona_section(config)
            parts.append(persona_part)

        # 添加技能
        if config.skills_enabled and self.skill_atlas:
            skills_part = self._build_skills_section(config)
            parts.append(skills_part)

        # 添加few-shot示例
        if config.fewshot_enabled and self.fewshot_examples:
            fewshot_part = self._build_fewshot_section(config)
            parts.append(fewshot_part)

        return "\n\n".join(parts)

    def _build_persona_section(self, config: PromptConfig) -> str:
        """构建人格部分"""
        if not self.persona:
            return ""

        comm_style = self.persona.get("communication_style", {})

        # 根据config调整风格
        if config.tone == "gentle":
            tone = "warm but still challenging"
        elif config.tone == "formal":
            tone = "formal and professional"
        else:
            tone = comm_style.get("tone", "direct, calm, challenging but non-judgmental")

        if config.response_length == "long":
            length = "detailed, up to 50 words when needed"
        elif config.response_length == "medium":
            length = "moderate, 20-40 words"
        else:
            length = comm_style.get("response_length", "brief, 10-30 words")

        principles = self.persona.get("interaction_principles", [])
        principles_text = "\n".join(f"- {p}" for p in principles[:5]) if principles else ""

        techniques = self.persona.get("core_techniques", {})
        techniques_text = "\n".join(
            f"- **{name}**: {info.get('description', '')[:50]}"
            for name, info in list(techniques.items())[:4]
        ) if techniques else ""

        return self.prompt_templates["persona_template"].format(
            style=comm_style.get("language", "English with occasional Chinese"),
            length=length,
            tone=tone,
            principles=principles_text,
            techniques=techniques_text
        )

    def _build_skills_section(self, config: PromptConfig) -> str:
        """构建技能部分"""
        if not self.skill_atlas:
            return ""

        # 获取当前最相关的技能（按使用频率）
        top_skills = self.skill_atlas.get("metadata", {}).get("top_skills", [])
        skill_list = [
            f"- {s['skill']}" for s in top_skills[:5]
        ]

        return self.prompt_templates["skill_template"].format(
            skills="\n".join(skill_list)
        )

    def _build_fewshot_section(self, config: PromptConfig) -> str:
        """构建few-shot示例部分"""
        if not self.fewshot_examples:
            return ""

        examples = self.fewshot_examples[:3]  # 最多3个
        parts = []

        for ex in examples:
            dialogue_lines = []
            for turn in ex.get("dialogue_turns", [])[:4]:  # 最多4轮
                speaker = "Oscar" if turn.get("speaker") == "philosopher" else "Client"
                dialogue_lines.append(f"{speaker}: {turn.get('text', '')[:80]}")

            parts.append(self.prompt_templates["fewshot_template"].format(
                topic=ex.get("category", ex.get("topic", "")),
                dialogue="\n".join(dialogue_lines),
                key_moment=ex.get("key_moment", "")
            ))

        return "\n\n".join(parts)

    def build_consultation_prompt(
        self,
        query: str,
        context: ConsultationContext,
        retrieved_docs: List[Dict] = None,
        config: PromptConfig = None
    ) -> Tuple[str, str]:
        """
        构建咨询场景的Prompt。

        Args:
            query: 用户输入
            context: 咨询上下文
            retrieved_docs: 从RAG检索到的相关文档
            config: Prompt配置

        Returns:
            (system_prompt, user_prompt) 元组
        """
        config = config or PromptConfig()

        # 获取对应场景的模板
        phase = context.consultation_phase or "problem_exploration"
        scenario = context.scenario or config.scenario or "consultation"

        template = self.scenario_templates.get_template(phase)
        if not template:
            # Fallback to base prompt
            return self.build_system_prompt(config), query

        # 构建系统Prompt: 场景化角色 + Persona + Skills
        system_parts = []

        # 1. 场景化角色前缀
        system_parts.append(self._get_scenario_prefix(scenario))

        # 2. Persona 部分（从模板获取）
        if config.persona_enabled and self.persona:
            persona_part = self._build_persona_section(config)
            system_parts.append(persona_part)

        # 3. Skills 部分
        if config.skills_enabled and self.skill_atlas:
            skills_part = self._build_skills_section(config)
            system_parts.append(skills_part)

        system_prompt = "\n\n".join(system_parts)

        # 构建用户Prompt: 模板 + RAG + 对话历史
        user_parts = []

        # 1. 模板渲染（注入 query 和 context）
        template_vars = {
            "client_message": query,
            "topic": context.current_topic or "unspecified topic",
            "emotional_signs": context.user_emotional_state or "unknown",
            "anxiety_level": context.user_emotional_state or "unknown",
            "dialogue_history": self._format_dialogue_history(context.previous_turns),
            "previous_message": context.previous_turns[-1]["message"] if context.previous_turns else "",
            "pattern": "",
            "signs": "",
            "resistance_type": "",
            "key_moments": ", ".join(context.key_insights[-3:]) or "none yet",
            "turn_count": len(context.previous_turns) // 2,
        }
        rendered = self.scenario_templates.render_template(phase, template_vars)
        if rendered:
            user_parts.append(rendered["user"])
        else:
            # Fallback
            user_parts.append(f"## Client's Message\n{query}")

        # 2. RAG 上下文
        if retrieved_docs:
            rag_part = self._build_rag_context(retrieved_docs)
            user_parts.append(rag_part)

        # 3. Few-shot 示例
        if config.fewshot_enabled and template.examples:
            examples_part = self._build_examples_section(template.examples)
            user_parts.append(examples_part)

        user_prompt = "\n\n".join(user_parts)

        return system_prompt, user_prompt

    def _get_scenario_prefix(self, scenario: str) -> str:
        """获取场景化角色前缀"""
        prefixes = {
            "consultation": """You are Oscar, a philosophical consultant specializing in Socratic dialogue and philosophical practice.

Your role is to guide clients through self-reflection using logical questioning, not to give advice or solutions.

SCENARIO: One-on-one philosophical consultation with a client.""",

            "supervision": """You are Oscar, a senior philosophical consultant supervising other practitioners.

Your role is to help coaches/supervisees reflect on their practice, identify blind spots, and improve their technique.

SCENARIO: Clinical supervision of a philosophical practice coach.""",

            "workshop": """You are Oscar, an experienced workshop facilitator leading group philosophical exploration.

Your role is to guide group discussions, manage dynamics, ensure participation, and help the group discover insights together.

SCENARIO: Group workshop facilitation with multiple participants."""
        }
        return prefixes.get(scenario, prefixes["consultation"])

    def _format_dialogue_history(self, turns: List[Dict]) -> str:
        """格式化对话历史"""
        if not turns:
            return "(beginning of conversation)"
        lines = []
        for t in turns[-6:]:
            speaker = "Oscar" if t.get("speaker", "").lower() in ["oscar", "philosopher"] else "Client"
            lines.append(f"**{speaker}**: {t.get('message', '')[:100]}")
        return "\n".join(lines)

    def _build_examples_section(self, examples: List[Dict]) -> str:
        """构建 few-shot 示例部分"""
        if not examples:
            return ""
        parts = ["## Example Dialogues\n"]
        for ex in examples[:2]:
            if isinstance(ex, dict):
                client = ex.get("client", ex.get("text", ""))
                oscar = ex.get("oscar", ex.get("response", ""))
                parts.append(f"**Client**: {client}\n**Oscar**: {oscar}\n")
            elif isinstance(ex, str):
                parts.append(f"- {ex}\n")
        return "\n".join(parts)

    def _build_consultation_context(self, context: ConsultationContext) -> str:
        """构建咨询上下文"""
        return self.prompt_templates["consultation_prefix"].format(
            topic=context.current_topic or "unspecified topic",
            phase=self._format_phase(context.consultation_phase),
            emotion=context.user_emotional_state or "unknown"
        )

    def _format_phase(self, phase: str) -> str:
        """格式化阶段名称"""
        phase_names = {
            "greeting": "开场 (Greeting)",
            "problem_exploration": "问题探索 (Problem Exploration)",
            "focusing": "聚焦问题 (Focusing)",
            "logical_exploration": "逻辑探索 (Logical Exploration)",
            "concept_clarification": "概念澄清 (Concept Clarification)",
            "integration": "整合反思 (Integration)",
            "closing": "结束 (Closing)"
        }
        return phase_names.get(phase, phase)

    def _build_rag_context(self, docs: List[Dict]) -> str:
        """构建RAG检索上下文"""
        if not docs:
            return ""

        parts = ["## Relevant Knowledge\n"]
        parts.append("Use this information to inform your response, but don't directly quote it:\n")

        for i, doc in enumerate(docs[:3], 1):
            text_zh = doc.get("text_zh", "")[:200]
            source = doc.get("source", "")
            parts.append(f"[{i}] {source}:\n{text_zh}...\n")

        return "\n".join(parts)

    def _build_dialogue_section(self, context: ConsultationContext) -> str:
        """构建对话历史部分"""
        if not context.previous_turns:
            return "## Dialogue\n**Client**: (first message)\n"

        lines = ["## Recent Dialogue\n"]
        for turn in context.previous_turns[-6:]:  # 最近6轮
            speaker = turn.get("speaker", "Unknown")
            text = turn.get("message", "")[:150]
            if speaker.lower() in ["oscar", "philosopher"]:
                lines.append(f"**Oscar**: {text}")
            else:
                lines.append(f"**Client**: {text}")

        return "\n".join(lines)

    def _build_guidance(self, context: ConsultationContext) -> str:
        """构建指导部分"""
        # 根据阶段和情绪状态生成指导
        guidance_parts = []

        if context.user_emotional_state == "anxiety":
            guidance_parts.append("- The client seems anxious. Consider using grounding techniques (stop, breathe).")
        elif context.user_emotional_state == "resistance":
            guidance_parts.append("- The client is showing resistance. Use acceptance and don't push too hard.")
        elif context.user_emotional_state == "insight":
            guidance_parts.append("- The client seems to be having a breakthrough. Support this moment.")

        if context.consultation_phase == "closing":
            guidance_parts.append("- Guide the client toward reflection and summary.")

        if not guidance_parts:
            guidance_parts.append("- Continue the philosophical exploration naturally.")

        return self.prompt_templates["question_prompt"].format(
            guidance="\n".join(guidance_parts)
        )

    def build_reflection_prompt(
        self,
        session_history: List[Dict]
    ) -> str:
        """
        构建反思Prompt，用于会话结束后的反思。

        Args:
            session_history: 会话历史

        Returns:
            反思Prompt
        """
        parts = [self.prompt_templates["system_prefix"]]

        # 添加简短人格
        if self.persona:
            parts.append(self._build_persona_section(PromptConfig(
                persona_enabled=True,
                skills_enabled=False,
                fewshot_enabled=False
            )))

        parts.append(self.prompt_templates["reflection_prompt"])

        return "\n\n".join(parts)

    def build_closing_prompt(
        self,
        context: ConsultationContext
    ) -> str:
        """
        构建结束语Prompt。

        Args:
            context: 咨询上下文

        Returns:
            结束语Prompt
        """
        parts = [self.prompt_templates["system_prefix"]]
        parts.append(self.prompt_templates["closing_prompt"])
        return "\n\n".join(parts)

    def select_fewshot_example(
        self,
        topic: str,
        category: str = None,
        technique: str = None
    ) -> Optional[Dict]:
        """
        根据主题/类别/技巧选择最合适的few-shot示例。

        Args:
            topic: 主题
            category: 类别
            technique: 技巧

        Returns:
            最匹配的示例
        """
        if not self.fewshot_examples:
            return None

        # 优先级: 技巧 > 类别 > 主题
        candidates = list(self.fewshot_examples)

        if technique:
            candidates = [e for e in candidates if e.get("sub_technique") == technique]
        if not candidates and category:
            candidates = [e for e in candidates if e.get("category") == category]
        if not candidates and topic:
            candidates = [e for e in candidates if topic in e.get("topic", "")]

        # 如果没找到精确匹配，返回随机一个
        if not candidates:
            return random.choice(self.fewshot_examples) if self.fewshot_examples else None

        return random.choice(candidates)

    def get_technique_suggestion(
        self,
        phase: str,
        emotional_state: str = None,
        recent_techniques: List[str] = None
    ) -> str:
        """
        根据当前状态建议使用的技巧。

        Args:
            phase: 当前阶段
            emotional_state: 情绪状态
            recent_techniques: 最近使用的技巧

        Returns:
            建议的技巧名称
        """
        if not self.skill_atlas:
            return "socratic_question"

        # 阶段对应的技巧
        phase_techniques = {
            "greeting": ["socratic_question", "active_listening"],
            "problem_exploration": ["socratic_question", "simplification"],
            "focusing": ["binary_questioning", "concept_naming"],
            "logical_exploration": ["logical_analysis", "contradiction_pointing"],
            "concept_clarification": ["binary_questioning", "socratic_question"],
            "integration": ["paraphrase", "integration_skills"],
            "closing": ["integration_skills", "paraphrase"]
        }

        # 情绪对应的技巧
        emotion_techniques = {
            "anxiety": ["grounding_technique", "stop_and_breathe"],
            "resistance": ["accepting_confusion", "resistance_handling"],
            "confusion": ["accepting_confusion", "simplification"],
            "insight": ["paraphrase", "insight_facilitation"]
        }

        suggestions = phase_techniques.get(phase, ["socratic_question"])

        if emotional_state in emotion_techniques:
            suggestions = emotion_techniques[emotional_state]

        # 避免重复
        if recent_techniques:
            for s in suggestions[:]:
                if s in recent_techniques:
                    suggestions.remove(s)

        return suggestions[0] if suggestions else "socratic_question"

    def save_prompt_template(
        self,
        output_path: str,
        config: PromptConfig = None
    ):
        """保存完整的Prompt模板到文件"""
        config = config or PromptConfig()
        system_prompt = self.build_system_prompt(config)

        Path(output_path).write_text(system_prompt, encoding="utf-8")
        print(f"Saved prompt template to: {output_path}")


def demo():
    """演示Prompt Builder的使用"""
    print("=" * 60)
    print("Oscar Prompt Builder Demo")
    print("=" * 60)

    builder = PromptBuilder()

    # 构建系统Prompt
    print("\n[1] Building system prompt...")
    config = PromptConfig(
        persona_enabled=True,
        skills_enabled=True,
        fewshot_enabled=True,
        tone="direct",
        response_length="short"
    )
    system_prompt = builder.build_system_prompt(config)
    print(f"System prompt length: {len(system_prompt)} chars")

    # 构建咨询Prompt
    print("\n[2] Building consultation prompt...")
    context = ConsultationContext(
        user_id="demo_user",
        session_id="session_001",
        current_topic="工作与生活平衡",
        consultation_phase="logical_exploration",
        user_emotional_state="anxiety",
        previous_turns=[
            {"speaker": "Client", "message": "I feel stressed about my work-life balance."},
            {"speaker": "Oscar", "message": "What is the main issue regarding work-life balance?"},
            {"speaker": "Client", "message": "I think I work too much and neglect my family."},
        ]
    )

    system_prompt, user_prompt = builder.build_consultation_prompt(
        query="Yes, but I can't reduce my workload because of financial pressure.",
        context=context,
        config=config
    )

    print(f"System prompt length: {len(system_prompt)} chars")
    print(f"User prompt length: {len(user_prompt)} chars")

    # 技巧建议
    print("\n[3] Technique suggestions...")
    technique = builder.get_technique_suggestion(
        phase="logical_exploration",
        emotional_state="anxiety"
    )
    print(f"Suggested technique: {technique}")

    # 保存模板
    print("\n[4] Saving prompt template...")
    builder.save_prompt_template("data/prompts/oscar_system_prompt.txt")


if __name__ == "__main__":
    demo()
