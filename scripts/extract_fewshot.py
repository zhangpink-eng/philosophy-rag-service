#!/usr/bin/env python3
"""
Few-shot 范例提取脚本。
从Oscar哲学咨询对话中提取高质量的咨询范例，用于：
1. 训练数据
2. Prompt工程few-shot示例
3. 技能评估

Usage: python scripts/extract_fewshot.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

# 说话者标签
PHILOSOPHER_LABELS = {"哲学家", "Philosopher", "Oscar"}
CLIENT_LABELS = {"客户", "Client", "customer", "来访者"}


@dataclass
class DialogueSnippet:
    """对话片段"""
    id: str
    topic: str
    technique: str
    philosopher_line: str
    client_line: str
    context_before: str
    context_after: str
    quality_score: float
    keywords: List[str]


@dataclass
class ConsultationExample:
    """完整咨询范例"""
    id: str
    topic: str
    category: str  # 问题类型: 人生意义/关系/情绪/职业/自我认知等
    sub_technique: str  # 具体技巧
    dialogue_turns: List[Dict[str, str]]
    key_moment: str  # 关键时刻描述
    outcome: str  # 结果/来访者反馈
    quality_tags: List[str]  # 质量标签
    usable_as: List[str]  # 可用于: few-shot/prompt/training


class FewShotExtractor:
    """提取高质量的哲学咨询范例"""

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or "/Users/pink/Desktop/哲学咨询/奥斯卡/文本/咨询")
        self.output_dir = Path("data/fewshot")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 问题类型分类
        self.topic_patterns = {
            "人生意义": ["meaning", "purpose", "life", "exist", "worth", "价值", "意义", "人生"],
            "情绪管理": ["anxiety", "stress", "fear", "anger", "sad", "calm", "情绪", "焦虑", "压力"],
            "人际关系": ["relationship", "family", "friend", "partner", "关系", "家庭", "朋友"],
            "职业发展": ["work", "career", "job", "balance", "工作", "职业", "平衡"],
            "自我认知": ["self", "identity", "who am I", "understand", "自我", "认识", "我是谁"],
            "决策困惑": ["decision", "choose", "confused", "uncertain", "决定", "选择", "困惑"],
            "价值冲突": ["value", "conflict", "should", "right", "价值", "冲突", "应该"],
        }

        # 技巧分类
        self.technique_patterns = {
            "苏格拉底追问": ["why", "what is", "can you explain", "define"],
            "逻辑矛盾指出": ["but you said", "so you agree", "contradiction", "但是你说"],
            "简化问题": ["one word", "simple", "basic", "what's the main", "简单", "主要"],
            "二选一": ["yes or no", "either", "or", "choose"],
            "叫停安抚": ["stop", "calm", "breathe", "slow down", "停", "冷静", "呼吸"],
            "接受困惑": ["don't understand", "that's ok", "not sure", "不理解", "没关系"],
        }

        # 质量指标
        self.quality_markers = {
            "insight": ["I understand", "I see", "realize", "发现", "理解"],
            "breakthrough": ["yes, because", "that's it", "exactly", "对的", "就是"],
            "resistance": ["but", "however", "defensive", "抗拒"],
            "emotional": ["anxious", "nervous", "calm", "relaxed", "焦虑", "平静"],
        }

    def load_transcripts(self) -> List[Dict]:
        """加载所有对话记录并解析"""
        all_turns = []

        for txt_file in self.data_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            turns = self._parse_transcript(content, txt_file.stem)
            all_turns.extend(turns)

        return all_turns

    def _parse_transcript(self, content: str, source: str) -> List[Dict]:
        """解析对话记录为结构化回合"""
        turns = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            speaker, text, timestamp = self._parse_line(line)

            if speaker and text:
                turns.append({
                    "speaker": speaker,
                    "text": text,
                    "timestamp": timestamp,
                    "source": source
                })

        return turns

    def _parse_line(self, line: str) -> tuple:
        """解析单行对话"""
        # 时间戳模式: (00:01:23)
        timestamp_match = re.match(r'\(([0-9:,]+)\):?\s*(.*)', line)

        # 说话者模式
        for label in PHILOSOPHER_LABELS:
            if label in line:
                text = line.replace(label, "").strip()
                text = re.sub(r'\([0-9:,]+\):?\s*', '', text)
                return ("philosopher", text, timestamp_match.group(1) if timestamp_match else "")

        for label in CLIENT_LABELS:
            if label in line:
                text = line.replace(label, "").strip()
                text = re.sub(r'\([0-9:,]+\):?\s*', '', text)
                return ("client", text, timestamp_match.group(1) if timestamp_match else "")

        return (None, None, None)

    def identify_topic(self, text: str) -> Optional[str]:
        """识别对话主题"""
        text_lower = text.lower()
        for topic, keywords in self.topic_patterns.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return topic
        return "其他"

    def identify_technique(self, text: str) -> Optional[str]:
        """识别使用的咨询技巧"""
        text_lower = text.lower()
        for technique, patterns in self.technique_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return technique
        return None

    def score_quality(self, philosopher_text: str, client_text: str, turns_before: List[Dict], turns_after: List[Dict]) -> float:
        """评估对话片段质量"""
        score = 0.5  # 基础分

        # 检查关键时刻标记
        combined_text = (philosopher_text + " " + client_text).lower()

        # 有洞见时刻
        for marker in self.quality_markers["insight"]:
            if marker.lower() in client_text.lower():
                score += 0.15

        # 有突破时刻
        for marker in self.quality_markers["breakthrough"]:
            if marker.lower() in client_text.lower():
                score += 0.2

        # 有抗拒
        for marker in self.quality_markers["resistance"]:
            if marker.lower() in client_text.lower():
                score -= 0.1

        # 有情绪描写
        for marker in self.quality_markers["emotional"]:
            if marker.lower() in combined_text:
                score += 0.1

        # 长度适中 (不是太长也不是太短)
        if 20 < len(client_text.split()) < 100:
            score += 0.1

        # 问句类型 (好的追问)
        if "?" in philosopher_text or "？" in philosopher_text:
            score += 0.1

        return min(max(score, 0.0), 1.0)

    def extract_snippets(self, turns: List[Dict], window_size: int = 2) -> List[DialogueSnippet]:
        """提取高质量对话片段"""
        snippets = []

        for i, turn in enumerate(turns):
            if turn["speaker"] != "philosopher":
                continue

            # 获取后续客户回应
            client_turns = []
            for j in range(i + 1, min(i + 1 + window_size, len(turns))):
                if turns[j]["speaker"] == "client":
                    client_turns.append(turns[j])
                    break

            if not client_turns:
                continue

            client_text = client_turns[0]["text"]
            philosopher_text = turn["text"]

            # 识别主题和技巧
            topic = self.identify_topic(philosopher_text + " " + client_text)
            technique = self.identify_technique(philosopher_text)
            if not technique:
                technique = "一般对话"

            # 获取上下文
            context_before = " ".join(t["text"] for t in turns[max(0, i-2):i])
            context_after = " ".join(t["text"] for t in turns[min(len(turns)-1, i+2):min(len(turns), i+4)])

            # 评分
            score = self.score_quality(philosopher_text, client_text, turns[:i], turns[i+1:])

            # 提取关键词
            keywords = self._extract_keywords(philosopher_text, client_text, topic)

            snippet = DialogueSnippet(
                id=f"snip_{i:04d}",
                topic=topic,
                technique=technique,
                philosopher_line=philosopher_text,
                client_line=client_text,
                context_before=context_before[-100:] if context_before else "",
                context_after=context_after[:100] if context_after else "",
                quality_score=score,
                keywords=keywords
            )

            snippets.append(snippet)

        # 按质量排序
        snippets.sort(key=lambda x: x.quality_score, reverse=True)

        return snippets

    def _extract_keywords(self, philo_text: str, client_text: str, topic: str) -> List[str]:
        """提取关键词"""
        combined = (philo_text + " " + client_text).lower()
        words = re.findall(r'\b\w{4,}\b', combined)
        word_freq = defaultdict(int)
        for w in words:
            word_freq[w] += 1
        # 返回最常见的词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:5]]

    def build_consultation_examples(self, turns: List[Dict], snippets: List[DialogueSnippet]) -> List[ConsultationExample]:
        """构建完整的咨询范例"""
        examples = []
        high_quality_snippets = [s for s in snippets if s.quality_score >= 0.6]

        # 按主题分组
        by_topic = defaultdict(list)
        for snip in high_quality_snippets:
            by_topic[snip.topic].append(snip)

        # 为每个主题选取最佳范例
        for topic, topic_snippets in by_topic.items():
            # 选取该主题下评分最高的片段
            best_snippets = sorted(topic_snippets, key=lambda x: x.quality_score, reverse=True)[:3]

            for snip in best_snippets:
                # 找到对应的完整对话轮次
                dialogue_turns = []
                for turn in turns:
                    if turn["text"] == snip.philosopher_line or turn["text"] == snip.client_line:
                        dialogue_turns.append({
                            "speaker": turn["speaker"],
                            "text": turn["text"][:200]  # 限制长度
                        })

                # 确定质量标签
                quality_tags = []
                if snip.quality_score >= 0.8:
                    quality_tags.append("优秀范例")
                elif snip.quality_score >= 0.7:
                    quality_tags.append("良好范例")
                else:
                    quality_tags.append("一般范例")

                if any(k in snip.client_line.lower() for k in ["yes", "对的", "明白了", "I see"]):
                    quality_tags.append("有突破")

                if len(snip.philosopher_line.split()) < 20:
                    quality_tags.append("简洁有力")

                example = ConsultationExample(
                    id=f"ex_{topic}_{snip.id}",
                    topic=topic,
                    category=self._categorize_topic(topic),
                    sub_technique=snip.technique,
                    dialogue_turns=dialogue_turns,
                    key_moment=self._describe_key_moment(snip),
                    outcome=self._extract_outcome(snip),
                    quality_tags=quality_tags,
                    usable_as=self._determine_uses(snip)
                )
                examples.append(example)

        return examples

    def _categorize_topic(self, topic: str) -> str:
        """细分主题分类"""
        mapping = {
            "人生意义": "生命意义探索",
            "情绪管理": "情绪识别与调节",
            "人际关系": "关系模式分析",
            "职业发展": "工作生活平衡",
            "自我认知": "自我觉察",
            "决策困惑": "价值观澄清",
            "价值冲突": "内在冲突处理",
            "其他": "一般咨询"
        }
        return mapping.get(topic, topic)

    def _describe_key_moment(self, snip: DialogueSnippet) -> str:
        """描述关键时刻"""
        moments = []
        if "why" in snip.philosopher_line.lower():
            moments.append("追问原因")
        if "but" in snip.philosopher_line.lower() or "但是" in snip.philosopher_line:
            moments.append("指出矛盾")
        if "yes" in snip.client_line.lower() and len(snip.client_line.split()) < 10:
            moments.append("简短确认")
        if snip.quality_score >= 0.8:
            moments.append("高质量对话")

        return "; ".join(moments) if moments else "一般互动"

    def _extract_outcome(self, snip: DialogueSnippet) -> str:
        """提取结果/反馈"""
        outcome = ""
        client_lower = snip.client_line.lower()

        if any(k in client_lower for k in ["yes", "yeah", "对的", "是"]):
            outcome = "来访者认同"
        if any(k in client_lower for k in ["I see", "understand", "明白"]):
            outcome = "来访者理解"
        if any(k in client_lower for k in ["because", "因为"]):
            outcome = "来访者给出理由"
        if any(k in client_lower for k in ["but", "however", "但是"]):
            outcome = "来访者有保留认同"

        return outcome if outcome else "待观察"

    def _determine_uses(self, snip: DialogueSnippet) -> List[str]:
        """确定用途"""
        uses = ["few-shot-example"]

        if snip.quality_score >= 0.75:
            uses.append("prompt-example")

        if "why" in snip.philosopher_line.lower():
            uses.append("technique-demo")

        if len(snip.philosopher_line.split()) < 15:
            uses.append("concise-response")

        return uses

    def generate_fewshot_prompts(self, examples: List[ConsultationExample]) -> List[Dict]:
        """生成可用于prompt的few-shot示例"""
        prompts = []

        for ex in examples:
            if "prompt-example" not in ex.usable_as:
                continue

            prompt = {
                "id": ex.id,
                "category": ex.category,
                "topic": ex.topic,
                "instruction": f"你是一位哲学咨询师。来访者的问题是关于「{ex.topic}」的咨询。",
                "dialogue": self._format_dialogue(ex.dialogue_turns),
                "explanation": f"技巧: {ex.sub_technique} | 关键时刻: {ex.key_moment}",
                "quality": ex.quality_tags
            }
            prompts.append(prompt)

        return prompts

    def _format_dialogue(self, turns: List[Dict]) -> str:
        """格式化对话用于prompt"""
        lines = []
        for turn in turns:
            speaker = "Oscar" if turn["speaker"] == "philosopher" else "来访者"
            lines.append(f"{speaker}: {turn['text']}")
        return "\n".join(lines)

    def save_results(self, snippets: List[DialogueSnippet], examples: List[ConsultationExample], prompts: List[Dict]):
        """保存所有结果"""
        # 1. 高质量片段
        high_quality = [s for s in snippets if s.quality_score >= 0.6]
        snippets_data = [asdict(s) for s in high_quality[:50]]  # 最多50条
        with open(self.output_dir / "snippets.json", "w", encoding="utf-8") as f:
            json.dump(snippets_data, f, ensure_ascii=False, indent=2)

        # 2. 完整范例
        examples_data = [asdict(e) for e in examples]
        with open(self.output_dir / "examples.json", "w", encoding="utf-8") as f:
            json.dump(examples_data, f, ensure_ascii=False, indent=2)

        # 3. Few-shot prompts
        with open(self.output_dir / "prompts.json", "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)

        # 4. Markdown格式便于阅读
        self._save_markdown_examples(examples)
        self._save_markdown_prompts(prompts)

        print(f"Saved {len(snippets_data)} snippets to {self.output_dir / 'snippets.json'}")
        print(f"Saved {len(examples_data)} examples to {self.output_dir / 'examples.json'}")
        print(f"Saved {len(prompts)} prompts to {self.output_dir / 'prompts.json'}")

    def _save_markdown_examples(self, examples: List[ConsultationExample]):
        """保存Markdown格式的范例"""
        md = "# Oscar 哲学咨询 Few-shot 范例\n\n"

        # 按类别分组
        by_category = defaultdict(list)
        for ex in examples:
            by_category[ex.category].append(ex)

        for category, cat_examples in by_category.items():
            md += f"\n## {category}\n\n"
            for ex in cat_examples:
                md += f"### [{ex.id}] {ex.topic}\n"
                md += f"- **技巧**: {ex.sub_technique}\n"
                md += f"- **关键时刻**: {ex.key_moment}\n"
                md += f"- **结果**: {ex.outcome}\n"
                md += f"- **标签**: {', '.join(ex.quality_tags)}\n\n"
                md += "**对话**:\n```\n"
                md += self._format_dialogue(ex.dialogue_turns)
                md += "\n```\n\n"

        with open(self.output_dir / "examples.md", "w", encoding="utf-8") as f:
            f.write(md)

    def _save_markdown_prompts(self, prompts: List[Dict]):
        """保存Markdown格式的prompts"""
        md = "# Few-shot Prompts for Philosophy Consultation AI\n\n"
        md += "## 使用说明\n"
        md += "这些prompts可用于构建Oscar哲学咨询AI助手。\n\n"

        for prompt in prompts:
            md += f"\n### {prompt['category']} - {prompt['topic']}\n"
            md += f"> {prompt['instruction']}\n\n"
            md += "```\n" + prompt['dialogue'] + "\n```\n"
            md += f"\n*{prompt['explanation']}*\n"

        with open(self.output_dir / "prompts.md", "w", encoding="utf-8") as f:
            f.write(md)


def main():
    print("=" * 60)
    print("Oscar 哲学咨询 Few-shot 范例提取")
    print("=" * 60)

    extractor = FewShotExtractor()

    # 加载对话
    print("\n[1/4] 加载对话记录...")
    turns = extractor.load_transcripts()
    print(f"  加载了 {len(turns)} 条对话轮次")

    # 提取高质量片段
    print("\n[2/4] 提取高质量对话片段...")
    snippets = extractor.extract_snippets(turns)
    print(f"  提取了 {len(snippets)} 个片段")
    print(f"  高质量片段(>=0.6): {len([s for s in snippets if s.quality_score >= 0.6])}")

    # 构建完整范例
    print("\n[3/4] 构建咨询范例...")
    examples = extractor.build_consultation_examples(turns, snippets)
    print(f"  构建了 {len(examples)} 个完整范例")

    # 生成few-shot prompts
    print("\n[4/4] 生成few-shot prompts...")
    prompts = extractor.generate_fewshot_prompts(examples)
    print(f"  生成了 {len(prompts)} 个prompts")

    # 保存结果
    print("\n[完成] 保存结果...")
    extractor.save_results(snippets, examples, prompts)

    print("\n" + "=" * 60)
    print("提取完成！")
    print("=" * 60)
    print(f"\n按主题分布:")
    topic_counts = defaultdict(int)
    for ex in examples:
        topic_counts[ex.topic] += 1
    for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {topic}: {count}")


if __name__ == "__main__":
    main()
