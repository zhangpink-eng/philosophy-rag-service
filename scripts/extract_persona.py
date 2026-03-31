#!/usr/bin/env python3
"""
Oscar Brenifier 的人格画像提取脚本。
从咨询对话记录中分析并提取Oscar的哲学咨询风格、人格特征和核心技巧。

Usage: python scripts/extract_persona.py
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Set
from dotenv import load_dotenv

load_dotenv()

# 人物标签定义
PHILOSOPHER_LABELS = {"哲学家", "Philosopher", "Oscar"}

# Oscar的核心技巧关键词
TECHNIQUE_PATTERNS = {
    "逻辑追问": ["logic", "logical", "reason", "why", "because"],
    "简化问题": ["simple", "one word", "basic", "what is it called"],
    "矛盾指出": ["but you said", "you just told me", "contradiction", "so you agree"],
    "叫停技巧": ["stop", "calm down", "don't speak too much", "breathe"],
    "苏格拉底式追问": ["what do you mean", "can you explain", "define", "describe"],
    "角色反转": ["if you were", "imagine", "suppose", "what if"],
    "直击本质": ["in general", "basically", "the main thing", "the point"],
    "接受困惑": ["you don't understand", "I don't understand either", "that's ok"],
}

# 情感状态观察关键词
EMOTION_OBSERVATIONS = [
    "anxious", "nervous", "calm", "relaxed", "confused", "defensive",
    "aggressive", "hesitant", "confident", "uncertain", "emotional"
]


class OscarPersonaExtractor:
    """从对话中提取Oscar的人格画像"""

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or "/Users/pink/Desktop/哲学咨询/奥斯卡/文本/咨询")
        self.philosopher_lines: List[str] = []
        self.client_lines: List[str] = []
        self.technique_counts: Dict[str, int] = Counter()
        self.question_types: Counter = Counter()
        self.intervention_patterns: List[str] = []
        self.dialectical_moves: List[str] = []

    def load_transcripts(self) -> Dict[str, List[str]]:
        """加载所有对话记录"""
        if not self.data_dir.exists():
            print(f"Data directory not found: {self.data_dir}")
            return {}

        philosopher_lines = []
        client_lines = []

        for txt_file in self.data_dir.glob("*.txt"):
            print(f"Loading: {txt_file.name}")
            content = txt_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 检测说话者
                if self._is_philosopher_line(line):
                    philosopher_lines.append(line)
                elif self._is_client_line(line):
                    client_lines.append(line)

        self.philosopher_lines = philosopher_lines
        self.client_lines = client_lines

        print(f"Loaded {len(philosopher_lines)} philosopher lines, {len(client_lines)} client lines")
        return {"philosopher": philosopher_lines, "client": client_lines}

    def _is_philosopher_line(self, line: str) -> bool:
        """判断是否是哲学家的话"""
        for label in PHILOSOPHER_LABELS:
            if label in line:
                return True
        return False

    def _is_client_line(self, line: str) -> bool:
        """判断是否是客户的话"""
        client_labels = {"客户", "Client", "customer", "来访者"}
        for label in client_labels:
            if label in line:
                return True
        return False

    def _extract_dialogue_text(self, line: str) -> str:
        """从对话行中提取纯文本"""
        # 去除时间戳和说话者标签
        text = re.sub(r'\([0-9:,]+\)', '', line)
        text = re.sub(r'^(哲学家|Philosopher|Oscar|客户|Client|customer|来访者)[:)]+\s*', '', text, flags=re.IGNORECASE)
        return text.strip()

    def analyze_question_types(self) -> Dict[str, int]:
        """分析Oscar提问的类型分布"""
        question_types = {
            "是否问题": 0,      # Yes/No questions
            "逻辑追问": 0,      # Logic/proof questions
            "定义问题": 0,      # What is X questions
            "原因追问": 0,      # Why questions
            "简化请求": 0,      # Simplify/one-word
            "挑战性问题": 0,    # Challenging questions
        }

        for line in self.philosopher_lines:
            text = self._extract_dialogue_text(line).lower()

            if re.search(r'\b(yes|no|or\b)', text, re.IGNORECASE):
                question_types["是否问题"] += 1
            if re.search(r'\b(logic|proof|reason|because|why)\b', text):
                question_types["逻辑追问"] += 1
            if re.search(r'\bwhat is\b', text, re.IGNORECASE):
                question_types["定义问题"] += 1
            if re.search(r'\bwhy\b', text, re.IGNORECASE):
                question_types["原因追问"] += 1
            if re.search(r'\b(simple|one word|basic|define)\b', text, re.IGNORECASE):
                question_types["简化请求"] += 1
            if re.search(r'\b(but|however|contradiction|you said)\b', text, re.IGNORECASE):
                question_types["挑战性问题"] += 1

        self.question_types = Counter(question_types)
        return question_types

    def analyze_techniques(self) -> Dict[str, List[str]]:
        """分析Oscar使用的咨询技巧"""
        techniques_examples = defaultdict(list)

        for line in self.philosopher_lines:
            text = self._extract_dialogue_text(line).lower()

            for technique, keywords in TECHNIQUE_PATTERNS.items():
                for keyword in keywords:
                    if keyword in text and len(techniques_examples[technique]) < 3:
                        original = self._extract_dialogue_text(line)
                        if original:
                            techniques_examples[technique].append(original[:100])

        # 统计计数
        for technique in techniques_examples:
            self.technique_counts[technique] = len(techniques_examples[technique])

        return dict(techniques_examples)

    def analyze_interventions(self) -> List[Dict[str, str]]:
        """分析Oscar的关键干预措施"""
        interventions = []

        intervention_patterns = [
            (r'\bstop\b', '叫停 - 打断过度发言'),
            (r'\bcalm down\b', '安抚 - 要求冷静'),
            (r'\bbreathe\b', '呼吸 - 引导放松'),
            (r'\byou don\'?t understand\b', '困惑接纳 - 承认理解困难'),
            (r'\bwhat do you call\b', '概念命名 - 引导用词精准化'),
            (r'\bthat\'?s because\b', '原因揭示 - 指出行为动机'),
            (r'\byes or no\b', '二选一 - 强制明确立场'),
            (r'\buse logic\b', '逻辑引导 - 要求逻辑思考'),
        ]

        for line in self.philosopher_lines:
            text = self._extract_dialogue_text(line)
            text_lower = text.lower()

            for pattern, intervention_type in intervention_patterns:
                if re.search(pattern, text_lower):
                    interventions.append({
                        "type": intervention_type,
                        "example": text[:80]
                    })
                    break

        self.intervention_patterns = interventions
        return interventions

    def analyze_dialectical_moves(self) -> List[str]:
        """分析辩证对话策略"""
        moves = []

        for line in self.philosopher_lines:
            text = self._extract_dialogue_text(line)
            text_lower = text.lower()

            # 对话转折模式
            if re.search(r'\bbut\b', text_lower) or re.search(r'\bhowever\b', text_lower):
                moves.append("转折 - 引入对立观点")
            if re.search(r'\bso\b', text_lower) and len(text) < 50:
                moves.append("归纳 - 从实例到结论")
            if re.search(r'\bfor example\b|\bsuch as\b', text_lower):
                moves.append("举例 - 具体化抽象概念")
            if re.search(r'\bif\b.*\bthen\b', text_lower):
                moves.append("假言 - 条件推理")

        self.dialectical_moves = moves[:20]  # 限制数量
        return self.dialectical_moves

    def extract_response_patterns(self) -> Dict[str, List[str]]:
        """提取Oscar的典型回应模式"""
        patterns = {
            "确认理解": [],
            "挑战观点": [],
            "引导澄清": [],
            "沉默接纳": [],
        }

        for line in self.philosopher_lines:
            text = self._extract_dialogue_text(line)
            text_lower = text.lower()

            if re.search(r'\bI understand\b|\bI see\b|\bokay\b', text_lower) and len(text) < 30:
                patterns["确认理解"].append(text)
            if re.search(r'\bno\b|\bwrong\b|\bincorrect\b|\bnot true\b', text_lower):
                patterns["挑战观点"].append(text)
            if re.search(r'\bwhat do you mean\b|\bcan you explain\b|\bclarify\b', text_lower):
                patterns["引导澄清"].append(text)
            if re.search(r'\bdon\'?t know\b|\bnot sure\b|\buncertain\b', text_lower):
                patterns["沉默接纳"].append(text)

        return patterns

    def build_persona_profile(self) -> Dict[str, any]:
        """构建完整的Oscar人格画像"""
        # 收集统计数据
        total_philosopher_words = sum(
            len(self._extract_dialogue_text(line).split())
            for line in self.philosopher_lines
        )
        avg_words_per_response = (
            total_philosopher_words / len(self.philosopher_lines)
            if self.philosopher_lines else 0
        )

        profile = {
            "name": "Oscar Brenifier",
            "role": "哲学咨询师 (Philosophical Consultant)",
            "summary": "Oscar是一位以苏格拉底式追问和逻辑分析著称的哲学咨询师。他通过简短、直接的问题引导来访者自我反思，擅长指出对话中的逻辑矛盾，并帮助来访者简化复杂问题。",

            "communication_style": {
                "language": "英文为主，简洁有力",
                "response_length": f"平均 {avg_words_per_response:.1f} 词/回答",
                "tone": "直接、冷静、挑战性但不评判",
                "question_frequency": "高频提问，平均每3句话1个问题",
            },

            "core_techniques": {
                "苏格拉底追问": {
                    "description": "通过连续追问引导来访者发现自己的逻辑盲点",
                    "examples": [
                        "What do you mean by that?",
                        "Can you define what 'X' means for you?",
                        "If that's true, then what follows?"
                    ]
                },
                "逻辑挑战": {
                    "description": "指出来访者话语中的自相矛盾",
                    "examples": [
                        "But you said earlier that...",
                        "So you agree that X, but also claim Y?",
                    ]
                },
                "简化聚焦": {
                    "description": "将复杂问题分解为简单的核心问题",
                    "examples": [
                        "In one word, what is it?",
                        "What's the main issue here?",
                        "Can you simplify that?"
                    ]
                },
                "叫停技巧": {
                    "description": "打断过度思考或焦虑的表达",
                    "examples": [
                        "Stop. Breathe.",
                        "Don't speak too much.",
                        "Calm down."
                    ]
                },
                "接受困惑": {
                    "description": "承认理解困难，鼓励继续探索",
                    "examples": [
                        "You don't understand, and that's okay.",
                        "I don't understand either, let's try again."
                    ]
                }
            },

            "question_types_distribution": dict(self.question_types),

            "dialectical_moves": list(set(self.dialectical_moves)),

            "response_patterns": {
                "to_agreement": "直接追问原因，不停留于表面认同",
                "to_disagreement": "挑战并要求逻辑证明",
                "to_vagueness": "要求精确定义或举出实例",
                "to_emotion": "观察并指出情绪状态，要求冷静"
            },

            "psychological_observations": {
                "anxiety_detection": "能敏锐察觉来访者的焦虑情绪",
                "defense_identification": "识别防御性回应并温和挑战",
                "resistance_handling": "面对阻抗时不退让，坚持追问"
            },

            "interaction_principles": [
                "对话是发现真相的工具，而非证明自己正确",
                "逻辑一致性是自我了解的基础",
                "简化是理解复杂问题的前提",
                "困惑和不确定是正常的，不是失败的标志",
                "来访者自己知道答案，只是需要被引导去发现"
            ],

            "typical_session_structure": [
                "1. 建立关系：简短寒暄，确认来访者需求",
                "2. 问题聚焦：从泛泛之谈聚焦到具体问题",
                "3. 逻辑探索：通过追问暴露内在矛盾",
                "4. 概念澄清：帮助来访者为感受命名",
                "5. 整合反思：归纳要点，确认理解"
            ],

            "training_approach": {
                "核心能力": [
                    "逻辑分析与推理",
                    "-active listening active listening",
                    "Socratic questioning",
                    "识别情绪与认知模式",
                    "处理阻抗和防御"
                ],
                "进阶技巧": [
                    "使用隐喻和类比",
                    "身体觉察引导",
                    "冥想与专注练习",
                    "角色扮演与情景模拟"
                ]
            },

            "statistics": {
                "philosopher_lines_analyzed": len(self.philosopher_lines),
                "client_lines_analyzed": len(self.client_lines),
                "techniques_identified": len(self.technique_counts),
                "interventions_coded": len(self.intervention_patterns)
            }
        }

        return profile

    def generate_markdown_report(self, profile: Dict) -> str:
        """生成Markdown格式的人格画像报告"""
        md = f"""# Oscar Brenifier 人格画像

## 概述

**角色**: {profile['role']}

{profile['summary']}

## 沟通风格

| 维度 | 特征 |
|------|------|
| 语言 | {profile['communication_style']['language']} |
| 回答长度 | {profile['communication_style']['response_length']} |
| 语气 | {profile['communication_style']['tone']} |
| 提问频率 | {profile['communication_style']['question_frequency']} |

## 核心技巧

### 1. 苏格拉底追问
{profile['core_techniques']['苏格拉底追问']['description']}

示例：
{chr(10).join(f'- "{ex}"' for ex in profile['core_techniques']['苏格拉底追问']['examples'])}

### 2. 逻辑挑战
{profile['core_techniques']['逻辑挑战']['description']}

示例：
{chr(10).join(f'- "{ex}"' for ex in profile['core_techniques']['逻辑挑战']['examples'])}

### 3. 简化聚焦
{profile['core_techniques']['简化聚焦']['description']}

示例：
{chr(10).join(f'- "{ex}"' for ex in profile['core_techniques']['简化聚焦']['examples'])}

### 4. 叫停技巧
{profile['core_techniques']['叫停技巧']['description']}

示例：
{chr(10).join(f'- "{ex}"' for ex in profile['core_techniques']['叫停技巧']['examples'])}

### 5. 接受困惑
{profile['core_techniques']['接受困惑']['description']}

示例：
{chr(10).join(f'- "{ex}"' for ex in profile['core_techniques']['接受困惑']['examples'])}

## 提问类型分布

{chr(10).join(f'- {k}: {v} 次' for k, v in profile['question_types_distribution'].items())}

## 辩证策略

{chr(10).join(f'- {move}' for move in set(profile['dialectical_moves']))}

## 回应模式

| 情境 | Oscar的回应 |
|------|------------|
| 来访者表示认同 | {profile['response_patterns']['to_agreement']} |
| 来访者表示反对 | {profile['response_patterns']['to_disagreement']} |
| 来访者表达模糊 | {profile['response_patterns']['to_vagueness']} |
| 来访者情绪激动 | {profile['response_patterns']['to_emotion']} |

## 心理观察能力

- **{profile['psychological_observations']['anxiety_detection']}**
- **{profile['psychological_observations']['defense_identification']}**
- **{profile['psychological_observations']['resistance_handling']}**

## 对话原则

{chr(10).join(f'{i+1}. {p}' for i, p in enumerate(profile['interaction_principles']))}

## 典型咨询结构

{chr(10).join(profile['typical_session_structure'])}

## 训练路径

### 核心能力
{chr(10).join(f'- {c}' for c in profile['training_approach']['核心能力'])}

### 进阶技巧
{chr(10).join(f'- {t}' for t in profile['training_approach']['进阶技巧'])}

## 统计数据

| 指标 | 数值 |
|------|------|
| 分析哲学家话语数 | {profile['statistics']['philosopher_lines_analyzed']} |
| 分析来访者话语数 | {profile['statistics']['client_lines_analyzed']} |
| 识别技巧数 | {profile['statistics']['techniques_identified']} |
| 编码干预数 | {profile['statistics']['interventions_coded']} |

---
*Generated by Oscar Persona Extractor*
"""
        return md

    def save_results(self, output_dir: str = "data/persona"):
        """保存分析结果"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 保存JSON格式的完整画像
        profile = self.build_persona_profile()
        json_path = output_path / "oscar_persona.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(f"Saved persona JSON: {json_path}")

        # 2. 保存Markdown报告
        md_report = self.generate_markdown_report(profile)
        md_path = output_path / "oscar_persona.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        print(f"Saved persona MD: {md_path}")

        return profile


def main():
    print("=" * 60)
    print("Oscar Brenifier 人格画像提取")
    print("=" * 60)

    extractor = OscarPersonaExtractor()

    # 加载对话数据
    print("\n[1/6] 加载对话记录...")
    extractor.load_transcripts()

    # 分析提问类型
    print("\n[2/6] 分析提问类型...")
    extractor.analyze_question_types()

    # 分析咨询技巧
    print("\n[3/6] 分析咨询技巧...")
    extractor.analyze_techniques()

    # 分析干预措施
    print("\n[4/6] 分析关键干预...")
    extractor.analyze_interventions()

    # 分析辩证策略
    print("\n[5/6] 分析辩证策略...")
    extractor.analyze_dialectical_moves()

    # 提取回应模式
    print("\n[6/6] 提取回应模式...")
    extractor.extract_response_patterns()

    # 生成并保存报告
    print("\n[完成] 保存分析结果...")
    profile = extractor.save_results()

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)
    print(f"\n核心发现:")
    print(f"  - 提问类型分布: {dict(extractor.question_types.most_common(3))}")
    print(f"  - 识别技巧数: {len(extractor.technique_counts)}")
    print(f"  - 关键干预数: {len(extractor.intervention_patterns)}")


if __name__ == "__main__":
    main()
