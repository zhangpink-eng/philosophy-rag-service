#!/usr/bin/env python3
"""
完整的文本预处理模块

功能：
1. 文本清洗（去除控制字符、HTML、URL、邮箱等）
2. 噪声过滤（过短、重复、纯符号内容）
3. 语言检测（bilingual/zh_en_mixed/zh/en/mixed）
4. 结构识别（页码、前言、章节）
5. 中英文分离（双语文件按行分离）
6. 去重（精确hash + 近似相似度）
7. 分块（语义分块，使用共享 SemanticChunker）
8. 独立存储（中英文分开，不强制配对）

使用示例：
```python
from core.preprocessor import Preprocessor

preprocessor = Preprocessor()
result = preprocessor.process_file("/path/to/file.txt")

# result 结构
{
    "metadata": {...},  # 处理统计信息
    "chunks": [...]    # 处理后的chunks
}
```

或批量处理：
```python
results = preprocessor.process_directory("/path/to/dir")
```
"""
import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

from core.chunker import SemanticChunker
from core.translator import translate_texts


# ============================================================
# 常量定义
# ============================================================

# 控制字符
CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

# HTML标签
HTML_TAG = re.compile(r'<[^>]+>')

# URL
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')

# 邮箱
EMAIL_PATTERN = re.compile(r'\S+@\S+\.\S+')

# 连续标点
MULTI_PUNCT = re.compile(r'([。！？；，：、])\1+')

# 中文模式
ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')

# 英文模式
EN_PATTERN = re.compile(r'[a-zA-Z]')

# 双语标记
BILINGUAL_MARKERS = re.compile(
    r'(说话人|Speaker|发言|主持|Talk|CN|EN)', re.IGNORECASE
)

# 噪声模式
REPEAT_PATTERN = re.compile(r'(.)\1{4,}')
PURE_NUMERIC = re.compile(r'^[\d\s.,;:!?()-]+$')
MIN_LENGTH = 10

# 页码模式
PAGE_PATTERNS = [
    (r'第\s*(\d+)\s*页', 'zh'),
    (r'Page\s*(\d+)', 'en'),
    (r'P\.?\s*(\d+)', 'en'),
]

# 前言标记
INTRO_MARKERS = ["简介", "前言", "序", "Preface", "Introduction"]


# ============================================================
# 数据类
# ============================================================

@dataclass
class PreprocessMetadata:
    """预处理元数据"""
    file_name: str
    file_path: str
    file_size: int
    language: str
    final_chunks: int
    cleaning_removed: int
    noise_removed: int
    zh_paragraphs: int
    en_paragraphs: int
    zh_duplicates: int
    en_duplicates: int
    zh_chunks: int
    en_chunks: int
    has_front_matter: bool
    has_page_numbers: bool


@dataclass
class Chunk:
    """单个Chunk"""
    chunk_id: str
    text_zh: str
    text_en: str
    language: str  # "zh", "en"（决定用哪个索引检索）


# ============================================================
# 分析函数（独立使用）
# ============================================================

def analyze_document(text: str) -> Dict:
    """
    分析文档结构，返回语言类型和分离后的文本

    Args:
        text: 原始文本

    Returns:
        {
            "language": "bilingual" | "zh_en_mixed" | "zh" | "en" | "mixed" | "unknown",
            "text_zh": str,  # 分离后的中文内容（bilingual格式时）
            "text_en": str,  # 分离后的英文内容（bilingual格式时）
            "stats": {
                "zh_paragraphs": int,
                "en_paragraphs": int,
                "zh_chars": int,
                "en_chars": int,
                "is_bilingual": bool,
                "total_paragraphs": int
            }
        }
    """
    ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    EN_PATTERN = re.compile(r'[a-zA-Z]')

    def has_bilingual_format(t: str) -> bool:
        """检测说话人交替格式（中英文混杂）
        要求：有说话人格式（名字+时间戳），且同时有中文行和英文行
        """
        if not re.search(r'\([0-9:]+\):', t):
            return False

        lines = [l.strip() for l in t.split('\n') if l.strip() and len(l.strip()) > 10]
        zh_lines = 0
        en_lines = 0

        for line in lines:
            match = re.match(r'^.+?\([0-9:]+\):\s*(.*)$', line)
            if match:
                content = match.group(1)
            else:
                content = line

            zh_chars = len(ZH_PATTERN.findall(content))
            en_chars = len(EN_PATTERN.findall(content))
            if zh_chars > en_chars:
                zh_lines += 1
            elif en_chars > zh_chars:
                en_lines += 1

        return zh_lines >= 5 and en_lines >= 5

    def has_zh_en_alternating_format(t: str) -> bool:
        """检测英文+中文翻译交替格式"""
        lines = [l.strip() for l in t.split('\n') if l.strip() and len(l.strip()) > 20]
        if len(lines) < 4:
            return False

        def get_lang_ratio(line: str) -> Tuple[str, float]:
            zh_chars = len(ZH_PATTERN.findall(line))
            en_chars = len(EN_PATTERN.findall(line))
            total = zh_chars + en_chars
            if total < 5:
                return ('unknown', 0)
            zh_ratio = zh_chars / total
            if zh_ratio > 0.7:
                return ('zh', zh_ratio)
            elif (1 - zh_ratio) > 0.7:
                return ('en', 1 - zh_ratio)
            else:
                return ('mixed', 0.5)

        alternating_count = 0
        for i in range(len(lines) - 1):
            curr_lang, _ = get_lang_ratio(lines[i])
            next_lang, _ = get_lang_ratio(lines[i + 1])

            if curr_lang == 'en' and next_lang == 'zh':
                alternating_count += 1
            elif curr_lang == 'zh' and next_lang == 'en':
                alternating_count += 1

        total_pairs = len(lines) - 1
        alternating_ratio = alternating_count / total_pairs if total_pairs > 0 else 0
        return len(lines) >= 4 and alternating_ratio > 0.4

    def detect_line_lang(line: str) -> str:
        """检测行的语言"""
        match = re.match(r'^[^:]+:\s*(.*)$', line)
        if match:
            content = match.group(1).strip()
            if content:
                zh_chars = len(ZH_PATTERN.findall(content))
                en_chars = len(EN_PATTERN.findall(content))
                total = zh_chars + en_chars
                if total > 0:
                    return 'zh' if zh_chars / total > 0.5 else 'en'
            return 'mixed'
        zh_chars = len(ZH_PATTERN.findall(line))
        en_chars = len(EN_PATTERN.findall(line))
        total = zh_chars + en_chars
        if total == 0:
            return 'mixed'
        return 'zh' if zh_chars / total > 0.5 else 'en'

    def separate_bilingual_text(t: str) -> Tuple[List[str], List[str]]:
        """分离中英文段落"""
        zh_paras, en_paras = [], []

        sections = re.split(r'\n\s*\n|\n\xa0\n', t)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            lines = section.split('\n')
            zh_lines, en_lines = [], []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                lang = detect_line_lang(line)

                if lang == 'zh':
                    zh_lines.append(line)
                elif lang == 'en':
                    en_lines.append(line)
                else:
                    zh_chars = len(ZH_PATTERN.findall(line))
                    en_chars = len(EN_PATTERN.findall(line))
                    if zh_chars >= en_chars:
                        zh_lines.append(line)
                    else:
                        en_lines.append(line)

            if zh_lines:
                zh_paras.append('\n'.join(zh_lines))
            if en_lines:
                en_paras.append('\n'.join(en_lines))

        return zh_paras, en_paras

    # 1. 检测 bilingual 格式
    if has_bilingual_format(text):
        language = 'bilingual'
        zh_paras, en_paras = separate_bilingual_text(text)
        return {
            "language": language,
            "text_zh": '\n\n'.join(zh_paras),
            "text_en": '\n\n'.join(en_paras),
            "stats": {
                "zh_paragraphs": len(zh_paras),
                "en_paragraphs": len(en_paras),
                "zh_chars": sum(len(p) for p in zh_paras),
                "en_chars": sum(len(p) for p in en_paras),
                "is_bilingual": True,
                "total_paragraphs": len(zh_paras) + len(en_paras)
            }
        }

    # 2. 检测 zh_en_mixed 格式
    if has_zh_en_alternating_format(text):
        language = 'zh_en_mixed'
        zh_paras, en_paras = separate_bilingual_text(text)
        return {
            "language": language,
            "text_zh": '\n\n'.join(zh_paras),
            "text_en": '\n\n'.join(en_paras),
            "stats": {
                "zh_paragraphs": len(zh_paras),
                "en_paragraphs": len(en_paras),
                "zh_chars": sum(len(p) for p in zh_paras),
                "en_chars": sum(len(p) for p in en_paras),
                "is_bilingual": False,
                "total_paragraphs": len(zh_paras) + len(en_paras)
            }
        }

    # 3. 按段落分析语言比例
    paragraphs = text.split('\n\n')
    zh_count = en_count = 0

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 5:
            continue

        zh_chars = len(ZH_PATTERN.findall(para))
        en_chars = len(EN_PATTERN.findall(para))
        total = zh_chars + en_chars

        if total == 0:
            continue

        if zh_chars / total > 0.5:
            zh_count += 1
        else:
            en_count += 1

    total = zh_count + en_count
    if total == 0:
        return {
            "language": "unknown",
            "text_zh": "",
            "text_en": "",
            "stats": {"zh_paragraphs": 0, "en_paragraphs": 0, "zh_chars": 0, "en_chars": 0, "is_bilingual": False, "total_paragraphs": 0}
        }

    zh_ratio = zh_count / total

    if zh_ratio > 0.8:
        language = 'zh'
    elif (1 - zh_ratio) > 0.8:
        language = 'en'
    else:
        language = 'mixed'

    # 对于单语言文件，不分离
    return {
        "language": language,
        "text_zh": text if language in ('zh', 'mixed') else "",
        "text_en": text if language in ('en', 'mixed') else "",
        "stats": {
            "zh_paragraphs": zh_count,
            "en_paragraphs": en_count,
            "zh_chars": sum(len(ZH_PATTERN.findall(p)) for p in paragraphs),
            "en_chars": sum(len(EN_PATTERN.findall(p)) for p in paragraphs),
            "is_bilingual": False,
            "total_paragraphs": total
        }
    }


# ============================================================
# 预处理类
# ============================================================

class Preprocessor:
    """完整预处理器"""

    def __init__(
        self,
        max_chunk_size: int = 512,
        similarity_threshold: float = 0.95,
        chunk_overlap: int = 64
    ):
        self.max_chunk_size = max_chunk_size
        self.similarity_threshold = similarity_threshold
        # 使用共享的 SemanticChunker
        self.chunker = SemanticChunker(
            max_chunk_size=max_chunk_size,
            overlap=chunk_overlap
        )

    # ---- 阶段1: 文本清洗 ----

    def clean_text(self, text: str) -> Tuple[str, int]:
        """
        文本清洗

        Returns:
            (清洗后文本, 移除字符数)
        """
        original_len = len(text)

        # 去除控制字符
        text = CONTROL_CHARS.sub('', text)

        # 去除HTML标签
        text = HTML_TAG.sub('', text)

        # 去除URL
        text = URL_PATTERN.sub('', text)

        # 去除邮箱
        text = EMAIL_PATTERN.sub('', text)

        # 压缩连续标点
        text = MULTI_PUNCT.sub(r'\1', text)

        # 去除首尾空白
        text = text.strip()

        return text, original_len - len(text)

    # ---- 阶段2: 噪声过滤 ----

    def filter_noise(self, text: str) -> Tuple[str, int]:
        """
        噪声过滤

        Returns:
            (过滤后文本, 移除段落数)
        """
        original_paras = text.split('\n\n')
        kept_paras = []

        for para in original_paras:
            para = para.strip()
            if not para:
                continue

            # 过短
            if len(para) < MIN_LENGTH:
                continue

            # 纯数字/符号
            if PURE_NUMERIC.match(para):
                continue

            # 高度重复
            if REPEAT_PATTERN.search(para):
                unique_ratio = len(set(para)) / len(para) if len(para) > 0 else 1
                if unique_ratio < 0.2:
                    continue

            kept_paras.append(para)

        return '\n\n'.join(kept_paras), len(original_paras) - len(kept_paras)

    # ---- 阶段3: 语言检测 ----

    def detect_language(self, text: str) -> str:
        """
        语言检测

        Returns:
            'bilingual' (说话人/Speaker交替格式)
            'zh_en_mixed' (英文+中文翻译交替格式，如The Unsatisfied)
            'zh', 'en', 'mixed', 'unknown'
        """
        def has_bilingual_format(t: str) -> bool:
            """检测说话人交替格式（中英文混杂）
            要求：有说话人格式（名字+时间戳），且同时有中文行和英文行
            """
            # 必须有说话人+时间戳格式才可能是 bilingual
            if not re.search(r'\([0-9:]+\):', t):
                return False

            # 统计有中文内容的行和有英文内容的行
            lines = [l.strip() for l in t.split('\n') if l.strip() and len(l.strip()) > 10]
            zh_lines = 0
            en_lines = 0

            for line in lines:
                # 提取说话人(时间): 内容 中的实际内容
                # 格式: 名字(时间): 内容
                match = re.match(r'^.+?\([0-9:]+\):\s*(.*)$', line)
                if match:
                    content = match.group(1)
                else:
                    content = line

                zh_chars = len(ZH_PATTERN.findall(content))
                en_chars = len(EN_PATTERN.findall(content))
                if zh_chars > 0 and en_chars > 0:
                    # 混合行
                    pass
                elif zh_chars > en_chars:
                    zh_lines += 1
                elif en_chars > zh_chars:
                    en_lines += 1

            # 如果同时有中文行和英文行，且各自超过一定数量，判定为bilingual
            # 中文行至少 5 行，英文行至少 5 行
            return zh_lines >= 5 and en_lines >= 5

        def has_zh_en_alternating_format(t: str) -> bool:
            """检测英文+中文翻译交替格式（The Unsatisfied模式）
            特征：英文行后面紧跟中文翻译行
            """
            # 按单换行分割，过滤空行
            lines = [l.strip() for l in t.split('\n') if l.strip() and len(l.strip()) > 20]
            if len(lines) < 4:
                return False

            def get_lang_ratio(line: str) -> Tuple[str, float]:
                """返回语言类型和比例"""
                zh_chars = len(ZH_PATTERN.findall(line))
                en_chars = len(EN_PATTERN.findall(line))
                total = zh_chars + en_chars
                if total < 5:
                    return ('unknown', 0)
                zh_ratio = zh_chars / total
                if zh_ratio > 0.7:
                    return ('zh', zh_ratio)
                elif (1 - zh_ratio) > 0.7:
                    return ('en', 1 - zh_ratio)
                else:
                    return ('mixed', 0.5)

            alternating_count = 0
            for i in range(len(lines) - 1):
                curr_line = lines[i]
                next_line = lines[i + 1]

                curr_lang, curr_ratio = get_lang_ratio(curr_line)
                next_lang, next_ratio = get_lang_ratio(next_line)

                # 判断交替模式：英文后面跟中文，或中文后面跟英文
                if curr_lang == 'en' and next_lang == 'zh':
                    alternating_count += 1
                elif curr_lang == 'zh' and next_lang == 'en':
                    alternating_count += 1

            # 如果超过40%的行对是交替的，认为是翻译格式
            total_pairs = len(lines) - 1
            alternating_ratio = alternating_count / total_pairs if total_pairs > 0 else 0
            if len(lines) >= 4 and alternating_ratio > 0.4:
                return True
            return False

        # 1. 检测说话人/Speaker交替格式（字幕格式）
        if has_bilingual_format(text):
            return 'bilingual'

        # 2. 检测英文+中文翻译交替格式（The Unsatisfied模式）
        if has_zh_en_alternating_format(text):
            return 'zh_en_mixed'

        # 3. 按段落分析语言比例
        paragraphs = text.split('\n\n')
        zh_count = en_count = 0

        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < 5:
                continue

            zh_chars = len(ZH_PATTERN.findall(para))
            en_chars = len(EN_PATTERN.findall(para))
            total = zh_chars + en_chars

            if total == 0:
                continue

            if zh_chars / total > 0.5:
                zh_count += 1
            else:
                en_count += 1

        total = zh_count + en_count
        if total == 0:
            return 'unknown'

        zh_ratio = zh_count / total

        if zh_ratio > 0.8:
            return 'zh'
        elif (1 - zh_ratio) > 0.8:
            return 'en'
        else:
            return 'mixed'

    # ---- 阶段4: 结构识别 ----

    def detect_structure(self, text: str) -> Dict:
        """检测文档结构"""
        paragraphs = text.split('\n\n')

        has_front_matter = False
        has_page_numbers = False

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 检测页码
            for pattern, _ in PAGE_PATTERNS:
                if re.search(pattern, para):
                    has_page_numbers = True
                    break

            # 检测前言
            if any(marker in para[:100] for marker in INTRO_MARKERS):
                has_front_matter = True

        return {
            'has_front_matter': has_front_matter,
            'has_page_numbers': has_page_numbers
        }

    # ---- 阶段5: 中英文分离 ----

    def separate_bilingual(self, text: str) -> Tuple[List[str], List[str]]:
        """
        中英文分离

        Returns:
            (zh_paragraphs, en_paragraphs)
        """
        def detect_line_lang(line: str) -> str:
            """检测行的语言 - 按实际内容判断"""
            # 说话人标签格式: 名字(时间戳): 内容
            # 提取冒号后面的实际内容进行判断
            match = re.match(r'^[^:]+:\s*(.*)$', line)
            if match:
                content = match.group(1).strip()
                if content:
                    zh_chars = len(ZH_PATTERN.findall(content))
                    en_chars = len(EN_PATTERN.findall(content))
                    total = zh_chars + en_chars
                    if total > 0:
                        return 'zh' if zh_chars / total > 0.5 else 'en'
                return 'mixed'
            # 无标签行，按字符比例
            zh_chars = len(ZH_PATTERN.findall(line))
            en_chars = len(EN_PATTERN.findall(line))
            total = zh_chars + en_chars
            if total == 0:
                return 'mixed'
            return 'zh' if zh_chars / total > 0.5 else 'en'

        zh_paras, en_paras = [], []

        # 首先按空行分割成translation pairs (用于zh_en_mixed格式)
        # 空行可能是 \n\n 或 单独的 \n 或 \xa0
        sections = re.split(r'\n\s*\n|\n\xa0\n', text)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 如果section只有一行，直接按语言分类
            lines = section.split('\n')
            if len(lines) <= 2:
                zh_lines, en_lines = [], []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    lang = detect_line_lang(line)
                    if lang == 'zh':
                        zh_lines.append(line)
                    elif lang == 'en':
                        en_lines.append(line)
                    else:
                        zh_chars = len(ZH_PATTERN.findall(line))
                        en_chars = len(EN_PATTERN.findall(line))
                        if zh_chars >= en_chars:
                            zh_lines.append(line)
                        else:
                            en_lines.append(line)
            else:
                # 多行section，按行处理
                zh_lines, en_lines = [], []
                for line in section.split('\n'):
                    line = line.strip()
                    if not line:
                        continue

                    lang = detect_line_lang(line)

                    if lang == 'zh':
                        zh_lines.append(line)
                    elif lang == 'en':
                        en_lines.append(line)
                    else:
                        # 混合行，按字符比例
                        zh_chars = len(ZH_PATTERN.findall(line))
                        en_chars = len(EN_PATTERN.findall(line))
                        if zh_chars >= en_chars:
                            zh_lines.append(line)
                        else:
                            en_lines.append(line)

            if zh_lines:
                zh_paras.append('\n'.join(zh_lines))
            if en_lines:
                en_paras.append('\n'.join(en_lines))

        return zh_paras, en_paras

    # ---- 阶段6: 去重 ----

    def deduplicate(
        self,
        zh_paras: List[str],
        en_paras: List[str]
    ) -> Tuple[List[str], List[str], int, int]:
        """
        去重

        Returns:
            (kept_zh, kept_en, zh_dup_count, en_dup_count)
        """
        seen_hashes_zh = set()
        seen_hashes_en = set()
        seen_similar_zh = []
        seen_similar_en = []

        kept_zh, kept_en = [], []
        zh_dups, en_dups = 0, 0

        # 去重中文
        for p in zh_paras:
            h = hashlib.sha256(p.encode()).hexdigest()[:16]
            if h in seen_hashes_zh:
                zh_dups += 1
                continue

            normalized = re.sub(r'\s+', '', re.sub(r'[^\w\u4e00-\u9fff]', '', p)).lower()
            is_dup = False
            for seen in seen_similar_zh[-100:]:
                if SequenceMatcher(None, normalized, seen).ratio() > self.similarity_threshold:
                    zh_dups += 1
                    is_dup = True
                    break

            if not is_dup:
                seen_hashes_zh.add(h)
                seen_similar_zh.append(normalized)
                kept_zh.append(p)

        # 去重英文
        for p in en_paras:
            h = hashlib.sha256(p.encode()).hexdigest()[:16]
            if h in seen_hashes_en:
                en_dups += 1
                continue

            normalized = re.sub(r'\s+', '', re.sub(r'[^\w]', '', p)).lower()
            is_dup = False
            for seen in seen_similar_en[-100:]:
                if SequenceMatcher(None, normalized, seen).ratio() > self.similarity_threshold:
                    en_dups += 1
                    is_dup = True
                    break

            if not is_dup:
                seen_hashes_en.add(h)
                seen_similar_en.append(normalized)
                kept_en.append(p)

        return kept_zh, kept_en, zh_dups, en_dups

    # ---- 阶段7: 分块 ----

    def chunk_paragraphs(
        self,
        zh_paras: List[str],
        en_paras: List[str],
        preserve_pairs: bool = False
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        语义分块（使用共享 SemanticChunker）

        Args:
            zh_paras: 中文段落
            en_paras: 英文段落
            preserve_pairs: 是否保持翻译对的独立性（用于zh_en_mixed格式）

        Returns:
            (zh_chunks, en_chunks) - 每项包含 {"text": str, "size": int}
        """
        zh_chunks = self.chunker.chunk_paragraphs(zh_paras, preserve_pairs)
        en_chunks = self.chunker.chunk_paragraphs(en_paras, preserve_pairs)

        return zh_chunks, en_chunks

    # ---- 阶段8: 配对 ----

    def create_paired_chunks(
        self,
        file_name: str,
        zh_chunks: List[Dict],
        en_chunks: List[Dict],
        original_lang: str
    ) -> List[Chunk]:
        """
        创建配对chunk

        Args:
            original_lang: 原文语言 ("zh" 或 "en")，决定检索时用哪个向量
        """
        # 生成文件前缀
        prefix = file_name.replace('.txt', '').replace(' ', '_').replace('-', '_')[:20]

        chunks = []
        max_len = max(len(zh_chunks), len(en_chunks))

        for i in range(max_len):
            zh_text = zh_chunks[i]["text"] if i < len(zh_chunks) else ""
            en_text = en_chunks[i]["text"] if i < len(en_chunks) else ""

            # 语言：按实际内容判断
            # - 只有中文 -> "zh"
            # - 只有英文 -> "en"
            # - 中英文都有 -> "mix"
            if zh_text and en_text:
                lang = "mix"
            elif zh_text:
                lang = "zh"
            elif en_text:
                lang = "en"
            else:
                continue

            chunk = Chunk(
                chunk_id=f"{prefix}_{i}",
                text_zh=zh_text,
                text_en=en_text,
                language=lang
            )
            chunks.append(chunk)

        return chunks

    def _create_independent_chunks(
        self,
        file_name: str,
        zh_chunks: List[Dict],
        en_chunks: List[Dict],
        original_lang: str
    ) -> List[Chunk]:
        """
        为zh_en_mixed格式创建独立chunk（中英文不配对）

        Returns:
            List[Chunk]
        """
        prefix = file_name.replace('.txt', '').replace(' ', '_').replace('-', '_')[:20]
        chunks = []

        # 创建中文chunk（使用zh_前缀）
        for i, zh_chunk in enumerate(zh_chunks):
            chunk = Chunk(
                chunk_id=f"{prefix}_zh_{i}",
                text_zh=zh_chunk["text"],
                text_en="",
                language="zh"
            )
            chunks.append(chunk)

        # 创建英文chunk（使用en_前缀）
        for i, en_chunk in enumerate(en_chunks):
            chunk = Chunk(
                chunk_id=f"{prefix}_en_{i}",
                text_zh="",
                text_en=en_chunk["text"],
                language="en"
            )
            chunks.append(chunk)

        return chunks

    # ---- 主处理流程 ----

    def process_file(self, file_path: Path) -> Dict:
        """
        处理单个文件

        Returns:
            {
                "metadata": PreprocessMetadata,
                "chunks": List[Chunk]
            }
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_size = len(content)
        file_name = file_path.name

        # 阶段1: 清洗
        cleaned, removed_chars = self.clean_text(content)

        # 阶段2: 噪声过滤
        filtered, removed_paras = self.filter_noise(cleaned)

        # 阶段3: 语言检测
        language = self.detect_language(filtered)

        # 阶段4: 结构识别
        structure = self.detect_structure(filtered)

        # 阶段5: 中英文分离
        if language == "bilingual" or language == "zh_en_mixed":
            # bilingual: 说话人/Speaker交替格式
            # zh_en_mixed: 英文+中文翻译交替格式（如The Unsatisfied）
            zh_paras, en_paras = self.separate_bilingual(filtered)
        else:
            paras = [p.strip() for p in filtered.split('\n\n') if p.strip()]
            if language == "zh":
                zh_paras, en_paras = paras, []
            elif language == "en":
                zh_paras, en_paras = [], paras
            else:
                # mixed: 按段落自己判断
                zh_paras, en_paras = self.separate_bilingual(filtered)

        # 阶段6: 去重
        kept_zh, kept_en, zh_dups, en_dups = self.deduplicate(zh_paras, en_paras)

        # 阶段6.5: 翻译（纯中文或纯英文需要翻译补充）
        # 注意：bilingual 和 zh_en_mixed 格式不需要翻译
        if language == "zh" and not kept_en and kept_zh:
            # 纯中文 → 翻译成英文
            print(f"  翻译 {len(kept_zh)} 个中文段落 → 英文")
            kept_en = translate_texts(kept_zh, target_lang="en")
        elif language == "en" and not kept_zh and kept_en:
            # 纯英文 → 翻译成中文
            print(f"  翻译 {len(kept_en)} 个英文段落 → 中文")
            kept_zh = translate_texts(kept_en, target_lang="zh")

        # 阶段7: 分块
        # zh_en_mixed格式保持翻译对独立，不合并
        preserve_pairs = (language == "zh_en_mixed")
        zh_chunks, en_chunks = self.chunk_paragraphs(kept_zh, kept_en, preserve_pairs)

        # 阶段8: 创建 chunks
        # bilingual 和 zh_en_mixed 格式：中英文独立存储（不配对）
        # zh 或 en：可能需要翻译后配对
        if language in ("bilingual", "zh_en_mixed"):
            # 中英文独立存储
            chunks = self._create_independent_chunks(file_name, zh_chunks, en_chunks, language)
        else:
            # 纯语言文件，翻译后配对
            chunks = self.create_paired_chunks(file_name, zh_chunks, en_chunks, language)

        # 构建元数据
        metadata = PreprocessMetadata(
            file_name=file_name,
            file_path=str(file_path),
            file_size=original_size,
            language=language,
            final_chunks=len(chunks),
            cleaning_removed=removed_chars,
            noise_removed=removed_paras,
            zh_paragraphs=len(kept_zh),
            en_paragraphs=len(kept_en),
            zh_duplicates=zh_dups,
            en_duplicates=en_dups,
            zh_chunks=len(zh_chunks),
            en_chunks=len(en_chunks),
            has_front_matter=structure['has_front_matter'],
            has_page_numbers=structure['has_page_numbers']
        )

        return {
            "metadata": metadata,
            "chunks": chunks
        }

    def process_file_to_dict(self, file_path: Path) -> Dict:
        """处理文件并返回字典格式（用于JSON序列化）"""
        result = self.process_file(file_path)
        return {
            "metadata": asdict(result["metadata"]),
            "chunks": [asdict(c) for c in result["chunks"]]
        }

    def save_result(self, result: Dict, output_path: Path):
        """保存处理结果到JSON文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def process_directory(
        self,
        dir_path: Path,
        output_dir: Optional[Path] = None,
        extensions: List[str] = ['.txt', '.md']
    ) -> List[Dict]:
        """
        批量处理目录

        Args:
            dir_path: 目录路径
            output_dir: 输出目录（可选）
            extensions: 处理的扩展名

        Returns:
            所有文件的处理结果列表
        """
        results = []

        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                if file_path.name.startswith('.'):
                    continue

                try:
                    result = self.process_file_to_dict(file_path)

                    # 保存到输出目录
                    if output_dir:
                        output_dir.mkdir(parents=True, exist_ok=True)
                        prefix = file_path.name.replace('.txt', '').replace(' ', '_')[:20]
                        output_file = output_dir / f"{prefix}.json"
                        self.save_result(result, output_file)

                    results.append(result)
                except Exception as e:
                    print(f"Error processing {file_path.name}: {e}")

        return results


# ============================================================
# 命令行接口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='文本预处理 - 清洗、检测、分离、去重、分块、翻译',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理单个文件
  python -m core.preprocessor /path/to/file.txt

  # 处理目录并保存结果
  python -m core.preprocessor /path/to/dir --output /output/dir

  # 指定分块大小
  python -m core.preprocessor /path/to/dir -o /output --chunk-size 512

  # 翻译 provider
  python -m core.preprocessor /path/to/dir -o /output --translator minimax
        """
    )
    parser.add_argument('path', help='文件或目录路径')
    parser.add_argument('-o', '--output', help='输出目录（批量模式）')
    parser.add_argument('--chunk-size', type=int, default=512, help='分块大小（字符数，默认512）')
    parser.add_argument('--chunk-overlap', type=int, default=64, help='分块重叠大小（默认64）')
    parser.add_argument('--translator', choices=['minimax', 'deepseek'], default='minimax',
                        help='翻译服务（默认minimax）')
    parser.add_argument('--extensions', nargs='+', default=['.txt', '.md'],
                        help='处理的文件扩展名（默认 .txt .md）')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')

    args = parser.parse_args()

    if args.verbose:
        print(f"初始化预处理器...")
        print(f"  分块大小: {args.chunk_size}")
        print(f"  翻译服务: {args.translator}")
        print()

    preprocessor = Preprocessor(
        max_chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    path = Path(args.path)

    if path.is_file():
        # 单文件模式
        if args.verbose:
            print(f"处理文件: {path}")

        result = preprocessor.process_file_to_dict(path)

        if args.verbose:
            print(f"  语言: {result['metadata']['language']}")
            print(f"  Chunks: {result['metadata']['final_chunks']}")

        # 输出到 stdout 或文件
        if args.output:
            output_file = Path(args.output)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            preprocessor.save_result(result, output_file)
            print(f"结果已保存到: {output_file}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    elif path.is_dir():
        # 批量模式
        output_dir = Path(args.output) if args.output else path.parent / "预处理结果"

        if args.verbose:
            print(f"处理目录: {path}")
            print(f"输出目录: {output_dir}")
            print(f"文件扩展名: {args.extensions}")
            print()

        results = preprocessor.process_directory(
            path,
            output_dir,
            extensions=args.extensions
        )

        # 汇总统计
        total_chunks = sum(r['metadata']['final_chunks'] for r in results)
        print(f"\n处理完成!")
        print(f"  文件数: {len(results)}")
        print(f"  总 chunks: {total_chunks}")
        print(f"  输出目录: {output_dir}")

    else:
        print(f"错误: 路径不存在: {path}")
        return 1

    return 0


if __name__ == '__main__':
    main()
