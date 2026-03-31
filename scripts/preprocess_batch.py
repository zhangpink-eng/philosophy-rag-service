#!/usr/bin/env python3
"""
批量预处理脚本

功能：
1. 处理目录下所有文本文件
2. 逐个输出处理结果
3. 汇总统计

使用示例：
    python scripts/preprocess_batch.py <目录路径>
    python scripts/preprocess_batch.py /Users/caiyuanjie/Desktop/文本预处理
"""
import sys
import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# 阶段1: 文本清洗
# ============================================================

def clean_text(text: str) -> Tuple[str, dict]:
    """文本清洗，返回(清洗后文本, 统计信息)"""
    original = text

    # 控制字符
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
    text = CONTROL_CHARS.sub('', text)

    # HTML标签
    HTML_TAG = re.compile(r'<[^>]+>')
    text = HTML_TAG.sub('', text)

    # URL
    URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
    text = URL_PATTERN.sub('', text)

    # 邮箱
    EMAIL_PATTERN = re.compile(r'\S+@\S+\.\S+')
    text = EMAIL_PATTERN.sub('', text)

    # 连续标点
    MULTI_PUNCT = re.compile(r'([。！？；，：、])\1+')
    text = MULTI_PUNCT.sub(r'\1', text)

    # 去除首尾空白
    text = text.strip()

    stats = {
        "original_length": len(original),
        "cleaned_length": len(text),
        "removed_chars": len(original) - len(text),
        "paragraph_count": text.count('\n\n') + 1 if '\n\n' in text else (1 if text else 0)
    }

    return text, stats


# ============================================================
# 阶段2: 噪声过滤
# ============================================================

def filter_noise(text: str) -> Tuple[str, dict]:
    """噪声过滤"""
    original_paras = text.split('\n\n')
    kept_paras = []
    removed = []

    REPEAT_PATTERN = re.compile(r'(.)\1{4,}')
    PURE_NUMERIC = re.compile(r'^[\d\s.,;:!?()-]+$')
    MIN_LENGTH = 10

    for para in original_paras:
        para = para.strip()
        if not para:
            continue

        # 过短
        if len(para) < MIN_LENGTH:
            removed.append({"reason": "过短", "preview": para[:30]})
            continue

        # 纯数字/符号
        if PURE_NUMERIC.match(para):
            removed.append({"reason": "纯数字/符号", "preview": para[:30]})
            continue

        # 高度重复
        if REPEAT_PATTERN.search(para):
            unique_ratio = len(set(para)) / len(para) if len(para) > 0 else 1
            if unique_ratio < 0.2:
                removed.append({"reason": f"高度重复({unique_ratio:.2f})", "preview": para[:30]})
                continue

        kept_paras.append(para)

    cleaned = '\n\n'.join(kept_paras)

    stats = {
        "original_paragraphs": len(original_paras),
        "kept_paragraphs": len(kept_paras),
        "removed_count": len(removed),
        "removed_samples": removed[:5]
    }

    return cleaned, stats


# ============================================================
# 阶段3: 语言检测
# ============================================================

def detect_language(text: str) -> Tuple[str, dict]:
    """语言检测"""
    ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    EN_PATTERN = re.compile(r'[a-zA-Z]')
    BILINGUAL_MARKERS = re.compile(r'(说话人|Speaker|发言|主持|Talk|CN|EN)', re.IGNORECASE)

    def has_bilingual_format(t):
        has_speaker = bool(BILINGUAL_MARKERS.search(t))
        if has_speaker:
            zh_markers = re.findall(r'说话人|发言|主持|CN', t)
            en_markers = re.findall(r'Speaker|Talk|EN', t, re.IGNORECASE)
            if zh_markers and en_markers:
                return True
        return False

    # 按段落分析
    paragraphs = text.split('\n\n')
    para_langs = []

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
        para_langs.append('zh' if zh_ratio > 0.5 else 'en')

    # 统计
    zh_count = para_langs.count('zh')
    en_count = para_langs.count('en')
    total = len(para_langs)

    # 切换次数
    switches = sum(1 for i in range(1, len(para_langs)) if para_langs[i] != para_langs[i-1])

    # 判断
    is_bilingual = has_bilingual_format(text)

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

    stats = {
        "is_bilingual": is_bilingual,
        "total_paragraphs": total,
        "zh_paragraphs": zh_count,
        "en_paragraphs": en_count,
        "zh_ratio": zh_count / total if total > 0 else 0,
        "language_switches": switches
    }

    return language, stats


# ============================================================
# 阶段4: 结构识别
# ============================================================

def detect_structure(text: str) -> dict:
    """结构识别"""
    PAGE_PATTERNS = [(r'第\s*(\d+)\s*页', 'zh'), (r'Page\s*(\d+)', 'en')]
    INTRO_MARKERS = ["简介", "前言", "序", "Preface", "Introduction"]

    paragraphs = text.split('\n\n')
    structures = {
        "title": 0,
        "author": 0,
        "introduction": 0,
        "body": 0,
        "has_page_numbers": False,
        "has_front_matter": False
    }

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 检测页码
        for pattern, lang in PAGE_PATTERNS:
            if re.search(pattern, para):
                structures["has_page_numbers"] = True
                break

        # 检测前言
        if any(marker in para[:100] for marker in INTRO_MARKERS):
            structures["introduction"] += 1
            structures["has_front_matter"] = True
            continue

        structures["body"] += 1

    return structures


# ============================================================
# 阶段5: 中英文分离
# ============================================================

def separate_bilingual(text: str, language: str) -> Tuple[List[str], List[str], dict]:
    """中英文分离"""
    ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    EN_PATTERN = re.compile(r'[a-zA-Z]')

    def detect_line_lang(line):
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

    zh_paras, en_paras = [], []

    for para in text.split('\n\n'):
        para = para.strip()
        if not para:
            continue

        # 尝试按行分离
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
                # 混合行
                zh_chars = len(ZH_PATTERN.findall(line))
                en_chars = len(EN_PATTERN.findall(line))
                if zh_chars > en_chars:
                    zh_lines.append(line)
                else:
                    en_lines.append(line)

        if zh_lines:
            zh_paras.append('\n'.join(zh_lines))
        if en_lines:
            en_paras.append('\n'.join(en_lines))

    stats = {
        "zh_paragraphs": len(zh_paras),
        "en_paragraphs": len(en_paras),
        "zh_chars": sum(len(p) for p in zh_paras),
        "en_chars": sum(len(p) for p in en_paras)
    }

    return zh_paras, en_paras, stats


# ============================================================
# 阶段6: 去重
# ============================================================

def deduplicate(zh_paras: List[str], en_paras: List[str]) -> Tuple[List[str], List[str], dict]:
    """去重"""
    seen_hashes_zh = set()
    seen_hashes_en = set()
    seen_similar_zh = []
    seen_similar_en = []

    kept_zh, kept_en = [], []
    zh_dups, en_dups = 0, 0

    for p in zh_paras:
        h = hashlib.sha256(p.encode()).hexdigest()[:16]
        if h in seen_hashes_zh:
            zh_dups += 1
            continue

        # 近似去重
        normalized = re.sub(r'\s+', '', re.sub(r'[^\w\u4e00-\u9fff]', '', p)).lower()
        is_dup = False
        for seen in seen_similar_zh[-100:]:
            if SequenceMatcher(None, normalized, seen).ratio() > 0.95:
                zh_dups += 1
                is_dup = True
                break

        if not is_dup:
            seen_hashes_zh.add(h)
            seen_similar_zh.append(normalized)
            kept_zh.append(p)

    for p in en_paras:
        h = hashlib.sha256(p.encode()).hexdigest()[:16]
        if h in seen_hashes_en:
            en_dups += 1
            continue

        normalized = re.sub(r'\s+', '', re.sub(r'[^\w]', '', p)).lower()
        is_dup = False
        for seen in seen_similar_en[-100:]:
            if SequenceMatcher(None, normalized, seen).ratio() > 0.95:
                en_dups += 1
                is_dup = True
                break

        if not is_dup:
            seen_hashes_en.add(h)
            seen_similar_en.append(normalized)
            kept_en.append(p)

    stats = {
        "original_zh": len(zh_paras),
        "original_en": len(en_paras),
        "kept_zh": len(kept_zh),
        "kept_en": len(kept_en),
        "zh_duplicates": zh_dups,
        "en_duplicates": en_dups
    }

    return kept_zh, kept_en, stats


# ============================================================
# 阶段7: 分块
# ============================================================

def chunk_texts(zh_paras: List[str], en_paras: List[str], max_size: int = 512) -> Tuple[List[dict], List[dict], dict]:
    """语义分块"""
    def chunk_paragraphs(paras: List[str]) -> Tuple[List[dict], int]:
        chunks = []
        current = []
        current_size = 0

        for para in paras:
            para_size = len(para)

            if para_size > max_size:
                # 保存当前chunk
                if current:
                    chunks.append('\n\n'.join(current))
                    current = []
                    current_size = 0

                # 分割长段落
                chunks.append(para)  # 简化处理：直接保留原段落
            elif current_size + para_size + 2 <= max_size:
                current.append(para)
                current_size += para_size + 2
            else:
                if current:
                    chunks.append('\n\n'.join(current))
                current = [para]
                current_size = para_size

        if current:
            chunks.append('\n\n'.join(current))

        return [{"text": c, "size": len(c)} for c in chunks], len(chunks)

    zh_chunks, zh_count = chunk_paragraphs(zh_paras)
    en_chunks, en_count = chunk_paragraphs(en_paras)

    stats = {
        "zh_chunks": zh_count,
        "en_chunks": en_count,
        "total_chunks": zh_count + en_count
    }

    return zh_chunks, en_chunks, stats


# ============================================================
# 主处理函数
# ============================================================

def process_file(file_path: Path) -> dict:
    """处理单个文件，返回完整统计"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    result = {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "file_size": len(content),
        "stages": {}
    }

    # 阶段1: 清洗
    cleaned, s1 = clean_text(content)
    result["stages"]["cleaning"] = s1

    # 阶段2: 噪声过滤
    filtered, s2 = filter_noise(cleaned)
    result["stages"]["noise_filter"] = s2

    # 阶段3: 语言检测
    language, s3 = detect_language(filtered)
    result["language"] = language
    result["stages"]["language_detection"] = s3

    # 阶段4: 结构识别
    structure = detect_structure(filtered)
    result["stages"]["structure"] = structure

    # 阶段5: 中英文分离
    if language == "bilingual":
        zh_paras, en_paras, s5 = separate_bilingual(filtered, language)
    else:
        # 单语言文件
        paras = [p.strip() for p in filtered.split('\n\n') if p.strip()]
        if language == "zh":
            zh_paras, en_paras = paras, []
        else:
            zh_paras, en_paras = [], paras
        s5 = {"zh_paragraphs": len(zh_paras), "en_paragraphs": len(en_paras), "zh_chars": sum(len(p) for p in zh_paras), "en_chars": sum(len(p) for p in en_paras)}

    result["stages"]["separation"] = s5

    # 阶段6: 去重
    kept_zh, kept_en, s6 = deduplicate(zh_paras, en_paras)
    result["stages"]["deduplication"] = s6

    # 阶段7: 分块
    zh_chunks, en_chunks, s7 = chunk_texts(kept_zh, kept_en)
    result["stages"]["chunking"] = s7
    result["final_chunks"] = s7["total_chunks"]

    # 保存处理后的内容
    result["processed"] = {
        "zh_chunks": zh_chunks,
        "en_chunks": en_chunks
    }

    return result


def process_directory(dir_path: Path) -> List[dict]:
    """处理目录下所有文件"""
    results = []

    for ext in ['*.txt', '*.md']:
        for file_path in dir_path.rglob(ext):
            if file_path.name.startswith('.'):
                continue

            try:
                result = process_file(file_path)
                results.append(result)
                print(f"  ✓ {file_path.name}")
            except Exception as e:
                print(f"  ✗ {file_path.name}: {e}")

    return results


def print_result(result: dict):
    """打印单个文件结果"""
    print(f"\n{'='*60}")
    print(f"文件: {result['file_name']}")
    print(f"{'='*60}")

    print(f"\n【文件信息】")
    print(f"  原始大小: {result['file_size']:,} 字符")
    print(f"  语言类型: {result['language']}")

    s = result['stages']

    print(f"\n【阶段1-清洗】")
    c = s['cleaning']
    print(f"  {c['original_length']:,} → {c['cleaned_length']:,} 字符 (移除 {c['removed_chars']})")

    print(f"\n【阶段2-噪声过滤】")
    n = s['noise_filter']
    print(f"  {n['original_paragraphs']} → {n['kept_paragraphs']} 段落 (移除 {n['removed_count']})")

    print(f"\n【阶段3-语言检测】")
    l = s['language_detection']
    print(f"  段落: 中文 {l['zh_paragraphs']}, 英文 {l['en_paragraphs']}")
    print(f"  切换次数: {l['language_switches']}")

    print(f"\n【阶段4-结构识别】")
    st = s['structure']
    print(f"  前言: {'有' if st['has_front_matter'] else '无'}")
    print(f"  页码: {'有' if st['has_page_numbers'] else '无'}")

    print(f"\n【阶段5-分离】")
    sep = s['separation']
    print(f"  中文: {sep['zh_paragraphs']} 段落 ({sep['zh_chars']:,} 字符)")
    print(f"  英文: {sep['en_paragraphs']} 段落 ({sep['en_chars']:,} 字符)")

    print(f"\n【阶段6-去重】")
    d = s['deduplication']
    print(f"  中文: {d['original_zh']} → {d['kept_zh']} (移除 {d['zh_duplicates']})")
    print(f"  英文: {d['original_en']} → {d['kept_en']} (移除 {d['en_duplicates']})")

    print(f"\n【阶段7-分块】")
    ch = s['chunking']
    print(f"  中文 chunks: {ch['zh_chunks']}")
    print(f"  英文 chunks: {ch['en_chunks']}")
    print(f"  【最终 chunks: {result['final_chunks']}】")


def print_summary(results: List[dict]):
    """打印汇总"""
    print(f"\n{'='*60}")
    print("汇总统计")
    print(f"{'='*60}")

    total_files = len(results)
    total_chunks = sum(r['final_chunks'] for r in results)

    lang_counts = {"zh": 0, "en": 0, "bilingual": 0, "mixed": 0}
    for r in results:
        lang_counts[r['language']] = lang_counts.get(r['language'], 0) + 1

    print(f"\n总文件数: {total_files}")
    print(f"总 chunks: {total_chunks}")
    print(f"\n语言分布:")
    for lang, count in lang_counts.items():
        if count > 0:
            print(f"  {lang}: {count} 个文件")


def save_results(results: List[dict], output_dir: Path):
    """保存处理结果"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存每个文件的处理结果
    for result in results:
        # 提取基本信息和统计（不包含processed内容）
        output = {
            "file_name": result['file_name'],
            "file_path": result['file_path'],
            "file_size": result['file_size'],
            "language": result['language'],
            "final_chunks": result['final_chunks'],
            "stages": result['stages']
        }

        # 中文 chunks
        zh_chunks = result['processed']['zh_chunks']
        en_chunks = result['processed']['en_chunks']

        # 配对生成pair_id
        paired_chunks = []
        max_len = max(len(zh_chunks), len(en_chunks))
        file_name_clean = result['file_name'].replace('.txt', '').replace(' ', '_')[:20]

        for i in range(max_len):
            zh_text = zh_chunks[i]["text"] if i < len(zh_chunks) else ""
            en_text = en_chunks[i]["text"] if i < len(en_chunks) else ""

            pair_id = f"{file_name_clean}_{i}"

            paired_chunks.append({
                "pair_id": pair_id,
                "index": i,
                "text_zh": zh_text,
                "text_en": en_text,
                "language": "zh" if zh_text and not en_text else ("en" if en_text and not zh_text else "both")
            })

        # 保存完整数据
        output_file = output_dir / f"{file_name_clean}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": output,
                "chunks": paired_chunks
            }, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_dir}")


# ============================================================
# 主函数
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='批量预处理文本文件')
    parser.add_argument('path', nargs='?', default='/Users/caiyuanjie/Desktop/文本预处理',
                       help='文件或目录路径')
    parser.add_argument('--output', '-o', default=None,
                       help='输出目录')

    args = parser.parse_args()

    path = Path(args.path)
    output_dir = Path(args.output) if args.output else path.parent / "预处理结果"

    results = []

    if path.is_file():
        print(f"处理文件: {path.name}")
        result = process_file(path)
        results.append(result)
        print_result(result)
    elif path.is_dir():
        print(f"处理目录: {path}")
        print(f"输出目录: {output_dir}")
        print()

        for subdir in sorted(path.iterdir()):
            if subdir.is_dir():
                print(f"\n[{subdir.name}]")
                sub_results = process_directory(subdir)
                results.extend(sub_results)

        print_summary(results)
    else:
        print(f"路径不存在: {path}")
        return 1

    # 保存结果
    if results:
        save_results(results, output_dir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
