#!/usr/bin/env python3
"""
Skill Atlas 技能图谱提取脚本。
从Oscar哲学咨询对话中提取技能，构建技能之间的关系图谱：
1. 技能分类（核心技能、进阶技能、专项技能）
2. 技能层级关系
3. 技能使用频率和效果
4. 技能组合模式

Usage: python scripts/extract_skill_map.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class Skill:
    """技能定义"""
    id: str
    name: str
    name_en: str
    category: str  # core/advanced/specialized
    level: int  # 1=基础, 2=进阶, 3=专家
    description: str
    examples: List[str]
    techniques: List[str]  # 具体技术
    parent_skills: List[str]  # 前置技能
    keywords: List[str]
    frequency: int = 0


@dataclass
class SkillRelation:
    """技能关系"""
    from_skill: str
    to_skill: str
    relation_type: str  # "prerequisite", "enhances", "alternates_with"
    description: str


@dataclass
class SkillUsage:
    """技能使用实例"""
    skill_id: str
    context: str
    client_response: str
    effectiveness: str  # "breakthrough", "resistance", "neutral"
    turn_index: int


class SkillAtlasExtractor:
    """从对话中提取和构建技能图谱"""

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or "data/raw")
        self.output_dir = Path("data/skills")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 技能定义
        self.skill_definitions = self._init_skill_definitions()

        # 技能出现计数
        self.skill_counts: Counter = Counter()
        self.skill_usage_examples: Dict[str, List[SkillUsage]] = defaultdict(list)
        self.skill_combinations: Counter = Counter()

        # 技能关系
        self.skill_relations: List[SkillRelation] = []

    def _init_skill_definitions(self) -> Dict[str, Skill]:
        """初始化技能定义"""
        return {
            # 核心技能 (Level 1)
            "active_listening": Skill(
                id="active_listening",
                name="积极倾听",
                name_en="Active Listening",
                category="core",
                level=1,
                description="全神贯注地倾听来访者，不打断，理解其话语和情感",
                examples=["认真听客户说完", "保持沉默让客户思考"],
                techniques=["保持眼神接触", "点头示意", "复述确认"],
                parent_skills=[],
                keywords=["I understand", "I see", "you said", "listen"]
            ),
            "socratic_question": Skill(
                id="socratic_question",
                name="苏格拉底追问",
                name_en="Socratic Questioning",
                category="core",
                level=1,
                description="通过连续追问引导来访者发现自己的逻辑盲点",
                examples=["What do you mean by that?", "Can you define what 'X' means?"],
                techniques=["是什么的问题", "为什么的问题", "如果...会怎样的问题"],
                parent_skills=["active_listening"],
                keywords=["what is", "why", "how", "define", "explain"]
            ),

            # 核心技能 - 逻辑类 (Level 1-2)
            "logical_analysis": Skill(
                id="logical_analysis",
                name="逻辑分析",
                name_en="Logical Analysis",
                category="core",
                level=1,
                description="识别和分析来访者话语中的逻辑结构",
                examples=["识别矛盾", "分析推理链条"],
                techniques=["矛盾识别", "推理验证", "前提分析"],
                parent_skills=["socratic_question"],
                keywords=["logic", "reason", "because", "therefore"]
            ),
            "contradiction_pointing": Skill(
                id="contradiction_pointing",
                name="矛盾指出",
                name_en="Contradiction Pointing",
                category="core",
                level=2,
                description="温和但直接地指出来访者的自相矛盾",
                examples=["But you said earlier that...", "So you agree X but also claim Y?"],
                techniques=["引用原话", "展示矛盾", "邀请澄清"],
                parent_skills=["logical_analysis", "socratic_question"],
                keywords=["but you said", "contradiction", "however", "so you agree"]
            ),

            # 情绪类技能 (Level 1-2)
            "emotion_observation": Skill(
                id="emotion_observation",
                name="情绪观察",
                name_en="Emotional Observation",
                category="core",
                level=1,
                description="敏锐察觉来访者的情绪状态变化",
                examples=["I see you're anxious", "You seem nervous"],
                techniques=["直接观察", "询问确认", "镜像反馈"],
                parent_skills=["active_listening"],
                keywords=["anxious", "nervous", "calm", "relaxed", "emotional"]
            ),
            "grounding_technique": Skill(
                id="grounding_technique",
                name="接地技术",
                name_en="Grounding Technique",
                category="core",
                level=1,
                description="帮助来访者回到当下，减少焦虑和过度思考",
                examples=["Stop. Breathe.", "Take a breath.", "Calm down."],
                techniques=["叫停", "呼吸引导", "身体觉察"],
                parent_skills=["emotion_observation"],
                keywords=["stop", "breathe", "calm", "slow down", "relax"]
            ),

            # 简化与聚焦 (Level 1-2)
            "simplification": Skill(
                id="simplification",
                name="简化聚焦",
                name_en="Simplification & Focusing",
                category="core",
                level=1,
                description="将复杂问题分解为简单核心问题",
                examples=["In one word, what is it?", "What's the main issue?"],
                techniques=["单字提问", "核心提炼", "分层剥离"],
                parent_skills=["socratic_question"],
                keywords=["simple", "one word", "main issue", "basically", "core"]
            ),
            "binary_questioning": Skill(
                id="binary_questioning",
                name="二选一追问",
                name_en="Binary Questioning",
                category="core",
                level=2,
                description="通过二选一问题强制明确立场",
                examples=["Is it A or B?", "Yes or no?"],
                techniques=["强制选择", "对比呈现", "立场明确化"],
                parent_skills=["simplification", "socratic_question"],
                keywords=["yes or no", "either", "or", "choose"]
            ),

            # 进阶技能 (Level 2-3)
            "concept_naming": Skill(
                id="concept_naming",
                name="概念命名",
                name_en="Concept Naming",
                category="advanced",
                level=2,
                description="帮助来访者为模糊的感受或状态找到准确的词汇",
                examples=["What do you call this?", "What's the word for that?"],
                techniques=["引导搜索词汇", "提供选项", "确认理解"],
                parent_skills=["simplification", "socratic_question"],
                keywords=["what do you call", "what's the word", "name"]
            ),
            "counterfactual_thinking": Skill(
                id="counterfactual_thinking",
                name="反事实思维",
                name_en="Counterfactual Thinking",
                category="advanced",
                level=2,
                description="引导来访者思考不同的可能性和假设情境",
                examples=["If you could change one thing...", "Suppose X were true..."],
                techniques=["假设引导", "可能性探索", "情景模拟"],
                parent_skills=["socratic_question", "imagination"],
                keywords=["if", "suppose", "imagine", "what if"]
            ),

            # 专家技能 (Level 3)
            "resistance_handling": Skill(
                id="resistance_handling",
                name="阻抗处理",
                name_en="Resistance Handling",
                category="specialized",
                level=3,
                description="识别并优雅处理来访者的防御和阻抗",
                examples=["I don't understand either, let's try again", "Confusion is normal"],
                techniques=["接纳困惑", "降低防御", "温和坚持"],
                parent_skills=["emotion_observation", "socratic_question"],
                keywords=["don't understand", "that's ok", "not sure", "resistance"]
            ),
            "insight_facilitation": Skill(
                id="insight_facilitation",
                name="洞察促进",
                name_en="Insight Facilitation",
                category="specialized",
                level=3,
                description="帮助来访者在对话中获得自我洞察",
                examples=["So what you're saying is...", "What did you discover?"],
                techniques=["复述归纳", "关键点强调", "连接建立"],
                parent_skills=["paraphrase", "logical_analysis"],
                keywords=["so what", "in other words", "you discovered", "realize"]
            ),
            "integration_skills": Skill(
                id="integration_skills",
                name="整合技能",
                name_en="Integration Skills",
                category="specialized",
                level=3,
                description="在咨询结束时整合所学，促进行动承诺",
                examples=["What was most useful?", "What will you take away?"],
                techniques=["要点总结", "收获确认", "行动规划"],
                parent_skills=["insight_facilitation", "paraphrase"],
                keywords=["summarize", "take away", "what's next", "most useful"]
            ),

            # 辅助技能
            "paraphrase": Skill(
                id="paraphrase",
                name="复述确认",
                name_en="Paraphrase",
                category="core",
                level=1,
                description="用自己的话复述来访者的话，确认理解",
                examples=["So what you're saying is...", "Let me make sure I understand..."],
                techniques=["意思复述", "情感反映", "理解确认"],
                parent_skills=["active_listening"],
                keywords=["so what", "in other words", "you mean"]
            ),
            "accepting_confusion": Skill(
                id="accepting_confusion",
                name="接受困惑",
                name_en="Accepting Confusion",
                category="core",
                level=1,
                description="承认理解困难是正常的，鼓励继续探索",
                examples=["You don't understand, and that's okay", "Not knowing is part of process"],
                techniques=["正常化困惑", "鼓励继续", "降低压力"],
                parent_skills=["emotion_observation"],
                keywords=["don't understand", "that's ok", "normal", "not sure"]
            ),
        }

    def load_transcripts(self) -> List[Dict]:
        """加载对话记录"""
        all_turns = []

        for txt_file in self.data_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            turns = self._parse_transcript(content)
            all_turns.extend(turns)

        return all_turns

    def _parse_transcript(self, content: str) -> List[Dict]:
        """解析对话"""
        turns = []
        lines = content.split("\n")

        philosopher_pattern = re.compile(r'^(哲学家|Philosopher|Oscar)[:)]?\s*(.*)', re.IGNORECASE)
        client_pattern = re.compile(r'^(客户|Client|customer|来访者)[:)]?\s*(.*)', re.IGNORECASE)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            philo_match = philosopher_pattern.match(line)
            if philo_match:
                text = re.sub(r'\([0-9:,]+\):?\s*', '', philo_match.group(2))
                if text:
                    turns.append({"speaker": "philosopher", "text": text})
                continue

            client_match = client_pattern.match(line)
            if client_match:
                text = re.sub(r'\([0-9:,]+\):?\s*', '', client_match.group(2))
                if text:
                    turns.append({"speaker": "client", "text": text})

        return turns

    def detect_skill_usage(self, turns: List[Dict]) -> Dict[str, List[SkillUsage]]:
        """检测技能使用"""
        skill_usages = defaultdict(list)

        for i, turn in enumerate(turns):
            if turn["speaker"] != "philosopher":
                continue

            text = turn["text"]
            text_lower = text.lower()

            # 检查每个技能
            for skill_id, skill in self.skill_definitions.items():
                for keyword in skill.keywords:
                    if keyword.lower() in text_lower:
                        # 找到匹配的客户端响应
                        client_response = ""
                        effectiveness = "neutral"
                        if i + 1 < len(turns) and turns[i + 1]["speaker"] == "client":
                            client_response = turns[i + 1]["text"]
                            # 评估效果
                            client_lower = client_response.lower()
                            if any(w in client_lower for w in ["yes", "I see", "exactly", "对的", "明白"]):
                                effectiveness = "breakthrough"
                            elif any(w in client_lower for w in ["but", "however", "可是", "但是"]):
                                effectiveness = "resistance"

                        usage = SkillUsage(
                            skill_id=skill_id,
                            context=text[:100],
                            client_response=client_response[:100] if client_response else "",
                            effectiveness=effectiveness,
                            turn_index=i
                        )
                        skill_usages[skill_id].append(usage)
                        self.skill_counts[skill_id] += 1
                        break

        self.skill_usage_examples = skill_usages
        return skill_usages

    def analyze_skill_combinations(self, turns: List[Dict]) -> List[Tuple[str, str]]:
        """分析技能组合使用模式"""
        combinations = []

        for i in range(len(turns) - 1):
            if turns[i]["speaker"] != "philosopher":
                continue

            current_text = turns[i]["text"].lower()
            next_text = turns[i + 1]["text"].lower() if i + 1 < len(turns) else ""

            # 检测技能组合
            for skill1_id, skill1 in self.skill_definitions.items():
                if any(kw.lower() in current_text for kw in skill1.keywords):
                    for skill2_id, skill2 in self.skill_definitions.items():
                        if skill1_id != skill2_id and any(kw.lower() in next_text for kw in skill2.keywords):
                            combo = tuple(sorted([skill1_id, skill2_id]))
                            combinations.append(combo)
                            self.skill_combinations[combo] += 1

        return combinations

    def build_skill_relations(self) -> List[SkillRelation]:
        """构建技能关系图"""
        relations = []

        # 从技能定义中的parent_skills构建关系
        for skill_id, skill in self.skill_definitions.items():
            for parent_id in skill.parent_skills:
                if parent_id in self.skill_definitions:
                    relations.append(SkillRelation(
                        from_skill=parent_id,
                        to_skill=skill_id,
                        relation_type="prerequisite",
                        description=f"{skill.name}需要先掌握{self.skill_definitions[parent_id].name}"
                    ))

        # 分析共现关系
        top_combos = self.skill_combinations.most_common(10)
        for (skill1, skill2), count in top_combos:
            if count >= 2:
                relations.append(SkillRelation(
                    from_skill=skill1,
                    to_skill=skill2,
                    relation_type="enhances",
                    description=f"{self.skill_definitions[skill1].name}和{self.skill_definitions[skill2].name}常配合使用({count}次)"
                ))

        self.skill_relations = relations
        return relations

    def build_atlas(self) -> Dict:
        """构建完整的技能图谱"""
        # 更新技能的frequency
        for skill_id, count in self.skill_counts.items():
            if skill_id in self.skill_definitions:
                self.skill_definitions[skill_id].frequency = count

        # 按类别分组
        skills_by_category = defaultdict(list)
        for skill in self.skill_definitions.values():
            skills_by_category[skill.category].append(asdict(skill))

        # 按层级分组
        skills_by_level = defaultdict(list)
        for skill in self.skill_definitions.values():
            skills_by_level[f"level_{skill.level}"].append(skill.name)

        # 统计
        total_uses = sum(self.skill_counts.values())
        top_skills = [
            {"skill": self.skill_definitions[sid].name, "count": count}
            for sid, count in self.skill_counts.most_common(10)
        ]

        # 效果统计
        effectiveness_stats = defaultdict(lambda: {"breakthrough": 0, "resistance": 0, "neutral": 0})
        for skill_id, usages in self.skill_usage_examples.items():
            for usage in usages:
                effectiveness_stats[skill_id][usage.effectiveness] += 1

        atlas = {
            "metadata": {
                "total_skill_uses": total_uses,
                "unique_skills": len(self.skill_definitions),
                "skill_categories": list(skills_by_category.keys()),
                "top_skills": top_skills
            },
            "skills": {
                sid: asdict(skill) for sid, skill in self.skill_definitions.items()
            },
            "skill_categories": {
                cat: skills_by_category[cat] for cat in skills_by_category
            },
            "skill_levels": {
                f"level_{lvl}": {
                    "skills": skills_by_level[f"level_{lvl}"],
                    "description": self._get_level_description(lvl)
                }
                for lvl in [1, 2, 3]
            },
            "skill_relations": [asdict(r) for r in self.skill_relations],
            "skill_combinations": [
                {"skills": list(combo), "count": count}
                for combo, count in self.skill_combinations.most_common(15)
            ],
            "effectiveness_stats": {
                sid: dict(stats) for sid, stats in effectiveness_stats.items()
            },
            "learning_path": self._generate_learning_path()
        }

        return atlas

    def _get_level_description(self, level: int) -> str:
        """获取层级描述"""
        descriptions = {
            1: "基础技能 - 从事哲学咨询必备的核心能力",
            2: "进阶技能 - 需要一定基础后才能掌握",
            3: "专家技能 - 需要丰富经验才能灵活运用"
        }
        return descriptions.get(level, "")

    def _generate_learning_path(self) -> List[List[str]]:
        """生成学习路径"""
        path = [
            # Level 1 基础路径
            ["active_listening", "emotion_observation", "paraphrase"],
            ["socratic_question", "simplification", "accepting_confusion"],
            ["logical_analysis", "grounding_technique"],
            # Level 2 进阶
            ["contradiction_pointing", "binary_questioning", "concept_naming"],
            ["counterfactual_thinking"],
            # Level 3 专家
            ["resistance_handling", "insight_facilitation", "integration_skills"]
        ]
        return path

    def save_atlas(self, atlas: Dict):
        """保存技能图谱"""
        # JSON格式
        with open(self.output_dir / "skill_atlas.json", "w", encoding="utf-8") as f:
            json.dump(atlas, f, ensure_ascii=False, indent=2)

        # Markdown格式
        self._save_markdown_atlas(atlas)

        print(f"Saved skill atlas to {self.output_dir / 'skill_atlas.json'}")
        print(f"Saved markdown version to {self.output_dir / 'skill_atlas.md'}")

    def _save_markdown_atlas(self, atlas: Dict):
        """保存Markdown格式的技能图谱"""
        md = "# Oscar 哲学咨询技能图谱\n\n"

        # 元信息
        md += "## 概览\n\n"
        md += f"- **总技能使用次数**: {atlas['metadata']['total_skill_uses']}\n"
        md += f"- **技能总数**: {atlas['metadata']['unique_skills']}\n"
        md += f"- **技能类别**: {', '.join(atlas['metadata']['skill_categories'])}\n\n"

        # 热门技能
        md += "### Top 10 高频技能\n\n"
        md += "| 技能 | 使用次数 |\n|-----|----------|\n"
        for item in atlas['metadata']['top_skills']:
            md += f"| {item['skill']} | {item['count']} |\n"
        md += "\n"

        # 技能层级
        md += "## 技能层级\n\n"
        for level_key, level_data in atlas['skill_levels'].items():
            level_num = level_key.split("_")[1]
            md += f"### Level {level_num}: {level_data['description']}\n\n"
            md += f"- " + "\n- ".join(level_data['skills']) + "\n\n"

        # 技能关系
        md += "## 技能关系\n\n"
        md += "| 关系类型 | 技能A | 技能B | 说明 |\n|---------|------|------|------|\n"
        for rel in atlas['skill_relations']:
            md += f"| {rel['relation_type']} | {rel['from_skill']} | {rel['to_skill']} | {rel['description']} |\n"
        md += "\n"

        # 技能组合
        md += "## 常见技能组合\n\n"
        md += "| 组合 | 使用次数 |\n|-----|----------|\n"
        for combo in atlas['skill_combinations'][:10]:
            md += f"| {' + '.join(combo['skills'])} | {combo['count']} |\n"
        md += "\n"

        # 学习路径
        md += "## 推荐学习路径\n\n"
        path_names = {
            "active_listening": "积极倾听",
            "emotion_observation": "情绪观察",
            "paraphrase": "复述确认",
            "socratic_question": "苏格拉底追问",
            "simplification": "简化聚焦",
            "accepting_confusion": "接受困惑",
            "logical_analysis": "逻辑分析",
            "grounding_technique": "接地技术",
            "contradiction_pointing": "矛盾指出",
            "binary_questioning": "二选一追问",
            "concept_naming": "概念命名",
            "counterfactual_thinking": "反事实思维",
            "resistance_handling": "阻抗处理",
            "insight_facilitation": "洞察促进",
            "integration_skills": "整合技能",
        }
        for i, stage in enumerate(atlas['learning_path']):
            md += f"{i+1}. " + " → ".join(path_names.get(s, s) for s in stage) + "\n"
        md += "\n"

        # 效果统计
        md += "## 技能效果统计\n\n"
        md += "| 技能 | 突破 | 抗拒 | 中性 |\n|-----|------|------|------|\n"
        for sid, stats in atlas['effectiveness_stats'].items():
            skill_name = path_names.get(sid, sid)
            md += f"| {skill_name} | {stats.get('breakthrough', 0)} | {stats.get('resistance', 0)} | {stats.get('neutral', 0)} |\n"

        with open(self.output_dir / "skill_atlas.md", "w", encoding="utf-8") as f:
            f.write(md)


def main():
    print("=" * 60)
    print("Oscar 哲学咨询技能图谱提取")
    print("=" * 60)

    extractor = SkillAtlasExtractor()

    # 加载对话
    print("\n[1/4] 加载对话记录...")
    turns = extractor.load_transcripts()
    print(f"  加载了 {len(turns)} 条对话轮次")

    # 检测技能使用
    print("\n[2/4] 检测技能使用...")
    usages = extractor.detect_skill_usage(turns)
    print(f"  检测到 {sum(len(u) for u in usages.values())} 次技能使用")
    print(f"  涉及 {len(usages)} 种技能")

    # 分析技能组合
    print("\n[3/4] 分析技能组合...")
    combos = extractor.analyze_skill_combinations(turns)
    print(f"  发现 {len(combos)} 个技能组合")

    # 构建关系
    print("\n[4/4] 构建技能图谱...")
    relations = extractor.build_skill_relations()
    atlas = extractor.build_atlas()

    # 保存
    extractor.save_atlas(atlas)

    print("\n" + "=" * 60)
    print("技能图谱构建完成！")
    print("=" * 60)
    print(f"\nTop 5 高频技能:")
    for item in atlas['metadata']['top_skills'][:5]:
        print(f"  {item['skill']}: {item['count']}次")


if __name__ == "__main__":
    main()
