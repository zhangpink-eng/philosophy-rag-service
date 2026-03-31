#!/usr/bin/env python3
"""
分阶段预处理演示脚本

每个阶段完成后展示结果，确认后再进入下一阶段

使用示例：
    python scripts/preprocessing_demo.py <文件路径>
"""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================
# 测试数据
# ============================================================

SAMPLE_TEXT = """
<html>
<body>
第 198 页

第十一章 哲学咨询

https://example.com
test@email.com

哲学咨询，在法国鲜有人知，但在荷兰、西班牙、意大利和美国
较为常见。哲学咨询的方法十分多样，这取决于设计和应用这些方法
的实践者。在本文中，我们将讨论我们在这个领域多年来一直在工作
中所使用的概念和方法。


说话人01(00:00:04): 我们现在开始。
Oscar(00:00:04): Okay, so we're gonna start our session.
说话人01(00:00:09): 有的朋友是第一次参加。
Oscar(00:00:09): Some people are new to our workshop.


哈哈哈哈哈哈哈！！！

11111111111111

The philosophical consultation is a method that helps people think.
"""

# 书籍样本
BOOK_SAMPLE = """
第 1 页

封面
《哲学实践的艺术》
作者：奥斯卡·柏尼菲 (Oscar Brenifier)
出版社：Z-Library

简介
本书探讨了哲学咨询的实践方法...

第 2 页

第一章 哲学的本质

哲学是一种思维方式，它帮助我们审视生活中的根本问题...
"""


# ============================================================
# 阶段 1：文本清洗
# ============================================================

def stage1_text_cleaning(text: str) -> dict:
    """阶段1：文本清洗（保持段落结构）"""
    import re
    print("\n" + "="*60)
    print("阶段 1：文本清洗（保持段落结构）")
    print("="*60)

    original = text

    # 先按段落分割，保留 \n\n
    # 这样后续处理时不会丢失段落边界

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

    # 处理每个段落
    cleaned_paragraphs = []
    for para in text.split('\n\n'):
        # 去除控制字符
        para = CONTROL_CHARS.sub('', para)
        # 去除HTML标签
        para = HTML_TAG.sub('', para)
        # 去除URL
        para = URL_PATTERN.sub('', para)
        # 去除邮箱
        para = EMAIL_PATTERN.sub('', para)
        # 压缩连续标点
        para = MULTI_PUNCT.sub(r'\1', para)
        # 去除首尾空白
        para = para.strip()
        if para:
            cleaned_paragraphs.append(para)

    cleaned = '\n\n'.join(cleaned_paragraphs)

    return {
        "original_length": len(original),
        "cleaned_length": len(cleaned),
        "original": original,
        "cleaned": cleaned,
        "paragraph_count": len(cleaned_paragraphs),
        "changes": {
            "control_chars_removed": len(original) - len(CONTROL_CHARS.sub('', original)),
        }
    }


# ============================================================
# 阶段 2：噪声过滤
# ============================================================

def stage2_noise_filtering(text: str) -> dict:
    """阶段2：噪声过滤（按段落处理）"""
    import re
    print("\n" + "="*60)
    print("阶段 2：噪声过滤（按段落处理）")
    print("="*60)

    original_paragraphs = text.split('\n\n')
    kept_paragraphs = []
    removed_paragraphs = []

    REPEAT_PATTERN = re.compile(r'(.)\1{4,}')
    PURE_NUMERIC = re.compile(r'^[\d\s.,;:!?()-]+$')
    MIN_LENGTH = 10

    for para in original_paragraphs:
        para = para.strip()
        if not para:
            continue

        # 过短
        if len(para) < MIN_LENGTH:
            removed_paragraphs.append({"para": para[:50], "reason": "过短"})
            continue

        # 纯数字/符号
        if PURE_NUMERIC.match(para):
            removed_paragraphs.append({"para": para[:50], "reason": "纯数字/符号"})
            continue

        # 高度重复
        if REPEAT_PATTERN.search(para):
            unique_ratio = len(set(para)) / len(para) if len(para) > 0 else 1
            if unique_ratio < 0.2:
                removed_paragraphs.append({"para": para[:50], "reason": f"高度重复 (unique={unique_ratio:.2f})"})
                continue

        kept_paragraphs.append(para)

    cleaned = '\n\n'.join(kept_paragraphs)

    return {
        "original_paragraphs": len(original_paragraphs),
        "kept_paragraphs": len(kept_paragraphs),
        "removed_paragraphs": len(removed_paragraphs),
        "removed_detail": removed_paragraphs[:10],  # 只显示前10个
        "cleaned": cleaned
    }


# ============================================================
# 阶段 3：语言检测
# ============================================================

def stage3_language_detection(text: str) -> dict:
    """阶段3：语言检测"""
    print("\n" + "="*60)
    print("阶段 3：语言检测")
    print("="*60)

    import re

    ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    EN_PATTERN = re.compile(r'[a-zA-Z]')

    # 双语格式检测
    BILINGUAL_MARKERS = re.compile(
        r'(说话人|Speaker|发言|主持|Talk|CN|EN)', re.IGNORECASE
    )

    def has_bilingual_format(t):
        has_speaker = bool(BILINGUAL_MARKERS.search(t))
        if has_speaker:
            zh_markers = re.findall(r'说话人|发言|主持|CN', t)
            en_markers = re.findall(r'Speaker|Talk|EN', t, re.IGNORECASE)
            if zh_markers and en_markers:
                return True
        return False

    def detect_by_paragraphs(t):
        paragraphs = t.split('\n\n')
        langs = []
        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < 5:
                continue
            zh_chars = len(ZH_PATTERN.findall(para))
            en_chars = len(EN_PATTERN.findall(para))
            total = zh_chars + en_chars
            if total == 0:
                continue
            zh_ratio = zh_chars / total
            if zh_ratio > 0.5:
                langs.append('zh')
            else:
                langs.append('en')
        return langs

    def count_switches(langs):
        switches = 0
        for i in range(1, len(langs)):
            if langs[i] != langs[i-1]:
                switches += 1
        return switches

    # 检测
    is_bilingual = has_bilingual_format(text)
    para_langs = detect_by_paragraphs(text)

    zh_count = para_langs.count('zh')
    en_count = para_langs.count('en')
    total = len(para_langs)

    switches = count_switches(para_langs)

    # 判断
    if is_bilingual:
        language = "bilingual"
    elif total > 0:
        zh_ratio = zh_count / total
        if zh_ratio > 0.8:
            language = "zh"
        elif (1 - zh_ratio) > 0.8:
            language = "en"
        else:
            language = "mixed"
    else:
        language = "unknown"

    return {
        "is_bilingual": is_bilingual,
        "paragraph_stats": {
            "total": total,
            "zh": zh_count,
            "en": en_count,
            "zh_ratio": zh_count / total if total > 0 else 0
        },
        "language_switches": switches,
        "detected_language": language
    }


# ============================================================
# 阶段 4：结构识别
# ============================================================

def stage4_structure_recognition(text: str) -> dict:
    """阶段4：结构识别"""
    import re
    print("\n" + "="*60)
    print("阶段 4：结构识别")
    print("="*60)

    # 页码模式
    PAGE_PATTERNS = [
        (r'第\s*(\d+)\s*页', 'zh'),
        (r'Page\s*(\d+)', 'en'),
        (r'P\.?\s*(\d+)', 'en'),
    ]

    # 元数据模式
    TITLE_PATTERNS = [
        r'《(.+?)》',
        r'"(.+?)"',  # 英文书名
    ]

    AUTHOR_PATTERNS = [
        r'作者[：:]\s*(.+)',
        r'by\s+(.+?)(?:\.|,|$)',
        r'Oscar\s+Brenifier',
    ]

    # 简介标记
    INTRO_MARKERS = ["简介", "前言", "序", "Preface", "Introduction"]

    paragraphs = text.split('\n\n')
    structures = []

    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue

        structure = {
            "index": i,
            "type": "body",
            "preview": para[:50] + "..." if len(para) > 50 else para
        }

        # 检测页码
        for pattern, lang in PAGE_PATTERNS:
            match = re.search(pattern, para)
            if match:
                structure["page_number"] = int(match.group(1))
                break

        # 检测书名
        for pattern in TITLE_PATTERNS:
            match = re.search(pattern, para)
            if match:
                structure["type"] = "title"
                structure["title"] = match.group(1)
                break

        # 检测作者
        for pattern in AUTHOR_PATTERNS:
            match = re.search(pattern, para)
            if match:
                structure["type"] = "author"
                structure["author"] = match.group(1).strip()
                break

        # 检测简介
        if any(marker in para[:100] for marker in INTRO_MARKERS):
            structure["type"] = "introduction"
            structure["is_front_matter"] = True

        structures.append(structure)

    return {
        "total_paragraphs": len(structures),
        "structures": structures[:10],  # 只显示前10个
        "structure_types": {
            "title": sum(1 for s in structures if s.get("type") == "title"),
            "author": sum(1 for s in structures if s.get("type") == "author"),
            "introduction": sum(1 for s in structures if s.get("type") == "introduction"),
            "body": sum(1 for s in structures if s.get("type") == "body"),
        },
        "has_page_numbers": any(s.get("page_number") for s in structures),
        "has_front_matter": any(s.get("is_front_matter") for s in structures)
    }


# ============================================================
# 阶段 5：中英文分离
# ============================================================

def stage5_bilingual_separation(text: str, language: str) -> dict:
    """阶段5：中英文分离"""
    import re
    from typing import List, Tuple
    print("\n" + "="*60)
    print("阶段 5：中英文分离")
    print("="*60)

    ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    EN_PATTERN = re.compile(r'[a-zA-Z]')

    def detect_line_lang(line):
        """检测单行语言"""
        if re.match(r'说话人', line):
            return 'zh'
        if re.match(r'Speaker', line, re.IGNORECASE):
            return 'en'
        zh_chars = len(ZH_PATTERN.findall(line))
        en_chars = len(EN_PATTERN.findall(line))
        total = zh_chars + en_chars
        if total == 0:
            return 'mixed'
        return 'zh' if zh_chars / total > 0.5 else 'en'

    def separate_paragraph(para: str) -> Tuple[List[str], List[str]]:
        """分离单个段落中的中英文行"""
        zh_lines, en_lines = [], []
        for line in para.split('\n'):
            line = line.strip()
            if not line:
                continue
            lang = detect_line_lang(line)
            if lang == 'zh':
                zh_lines.append(line)
            elif lang == 'en':
                en_lines.append(line)
            else:
                # 混合行，尝试按字符比例分离
                zh_chars = len(ZH_PATTERN.findall(line))
                en_chars = len(EN_PATTERN.findall(line))
                if zh_chars > en_chars:
                    zh_lines.append(line)
                else:
                    en_lines.append(line)
        return zh_lines, en_lines

    if language == "bilingual":
        # 双语文件：逐行分离
        paragraphs = text.split('\n\n')
        zh_all, en_all = [], []

        for para in paragraphs:
            if not para.strip():
                continue
            zh_lines, en_lines = separate_paragraph(para)
            if zh_lines:
                zh_all.append('\n'.join(zh_lines))
            if en_lines:
                en_all.append('\n'.join(en_lines))

        return {
            "mode": "bilingual",
            "zh_paragraphs": len(zh_all),
            "en_paragraphs": len(en_all),
            "zh_total_chars": sum(len(p) for p in zh_all),
            "en_total_chars": sum(len(p) for p in en_all),
            "zh_sample": '\n\n'.join(zh_all[:3])[:500] if zh_all else "",
            "en_sample": '\n\n'.join(en_all[:3])[:500] if en_all else "",
        }
    else:
        # 单语言文件
        return {
            "mode": "monolingual",
            "language": language,
            "text_sample": text[:500]
        }


# ============================================================
# 主函数
# ============================================================

def run_demo(file_path: str = None):
    """运行演示"""

    if file_path and Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"加载文件: {file_path}")
        print(f"文件大小: {len(text)} 字符")
    else:
        print("使用测试数据...")
        text = SAMPLE_TEXT

    # 阶段1
    result1 = stage1_text_cleaning(text)
    print(f"\n清洗前: {result1['original_length']} 字符")
    print(f"清洗后: {result1['cleaned_length']} 字符")
    print(f"\n清洗后内容预览:")
    print(result1['cleaned'][:500])

    # 阶段2
    result2 = stage2_noise_filtering(result1['cleaned'])
    print(f"\n原始段落数: {result2['original_paragraphs']}")
    print(f"保留段落数: {result2['kept_paragraphs']}")
    print(f"过滤段落数: {result2['removed_paragraphs']}")
    if result2['removed_detail']:
        print(f"过滤详情: {result2['removed_detail'][:5]}")

    # 阶段3
    result3 = stage3_language_detection(result2['cleaned'])
    print(f"\n检测到双语格式: {result3['is_bilingual']}")
    print(f"段落统计: {result3['paragraph_stats']}")
    print(f"语言切换次数: {result3['language_switches']}")
    print(f"判定语言: {result3['detected_language']}")

    # 阶段4
    result4 = stage4_structure_recognition(result2['cleaned'])
    print(f"\n段落数: {result4['total_paragraphs']}")
    print(f"结构类型: {result4['structure_types']}")
    print(f"有页码: {result4['has_page_numbers']}")
    print(f"有前言: {result4['has_front_matter']}")

    # 阶段5
    result5 = stage5_bilingual_separation(result2['cleaned'], result3['detected_language'])
    print(f"\n处理模式: {result5['mode']}")
    if result5['mode'] == 'bilingual':
        print(f"中文段落: {result5['zh_paragraphs']} ({result5['zh_total_chars']} 字符)")
        print(f"英文段落: {result5['en_paragraphs']} ({result5['en_total_chars']} 字符)")
        print(f"\n中文预览:\n{result5['zh_sample'][:300]}")
        print(f"\n英文预览:\n{result5['en_sample'][:300]}")
    else:
        print(f"语言: {result5['language']}")

    return {
        "stage1": result1,
        "stage2": result2,
        "stage3": result3,
        "stage4": result4,
        "stage5": result5
    }


if __name__ == '__main__':
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_demo(file_path)
