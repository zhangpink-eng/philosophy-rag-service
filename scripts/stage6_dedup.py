#!/usr/bin/env python3
"""
阶段 6：去重

功能：
1. 精确去重（SHA256 hash）
2. 近似去重（编辑距离 < 5%）

使用示例：
    python scripts/stage6_dedup.py <文本文件>
"""
import sys
import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def normalize_for_comparison(text: str) -> str:
    """标准化文本用于比较"""
    # 去除空白、标点、小写
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    return text.lower()


def compute_hash(text: str) -> str:
    """计算文本hash"""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def is_duplicate_exact(text: str, seen_hashes: set) -> bool:
    """精确去重"""
    text_hash = compute_hash(text)
    if text_hash in seen_hashes:
        return True
    seen_hashes.add(text_hash)
    return False


def is_duplicate_similar(
    text: str,
    normalized_texts: List[str],
    threshold: float = 0.95
) -> Tuple[bool, str]:
    """
    近似去重

    Returns:
        (is_duplicate, similar_to)
    """
    normalized = normalize_for_comparison(text)

    for seen in normalized_texts[-100:]:  # 只比较最近100条
        similarity = SequenceMatcher(None, normalized, seen).ratio()
        if similarity > threshold:
            return True, seen[:50]

    return False, ""


def deduplicate_paragraphs(
    zh_texts: List[str],
    en_texts: List[str],
    similarity_threshold: float = 0.95
) -> Dict:
    """
    对双语段落进行去重

    Args:
        zh_texts: 中文段落列表
        en_texts: 英文段落列表
        similarity_threshold: 相似度阈值

    Returns:
        去重结果统计
    """
    # 合并中英文一起去重（因为它们内容相同）
    all_texts = zh_texts + en_texts
    all_is_zh = [True] * len(zh_texts) + [False] * len(en_texts)

    seen_hashes = set()
    normalized_texts = []

    kept_indices = []
    duplicate_indices = []
    duplicates_detail = []

    for i, text in enumerate(all_texts):
        # 精确去重
        if is_duplicate_exact(text, seen_hashes):
            duplicate_indices.append(i)
            duplicates_detail.append({
                "index": i,
                "is_zh": all_is_zh[i],
                "preview": text[:50],
                "reason": "exact_duplicate"
            })
            continue

        # 近似去重
        is_dup, similar_to = is_duplicate_similar(
            text, normalized_texts, similarity_threshold
        )
        if is_dup:
            duplicate_indices.append(i)
            duplicates_detail.append({
                "index": i,
                "is_zh": all_is_zh[i],
                "preview": text[:50],
                "reason": f"similar ({similar_to[:30]}...)"
            })
            continue

        normalized_texts.append(normalize_for_comparison(text))
        kept_indices.append(i)

    # 分离保留的中英文
    kept_zh = [all_texts[i] for i in kept_indices if all_is_zh[i]]
    kept_en = [all_texts[i] for i in kept_indices if not all_is_zh[i]]

    return {
        "original_zh_count": len(zh_texts),
        "original_en_count": len(en_texts),
        "kept_zh_count": len(kept_zh),
        "kept_en_count": len(kept_en),
        "total_duplicates": len(duplicate_indices),
        "duplicates_detail": duplicates_detail[:10],  # 只显示前10个
        "kept_zh_samples": kept_zh[:3],
        "kept_en_samples": kept_en[:3]
    }


def run_demo(file_path: str = None):
    """运行去重演示"""

    if file_path and Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"加载文件: {file_path}")
    else:
        # 测试数据
        content = """
说话人01: 这是第一句话。
Oscar: This is the first sentence.
说话人02: 这是第二句话。
Oscar: This is the second sentence.
说话人01: 这是第一句话。  # 重复
Oscar: This is the first sentence.  # 重复
说话人03: 这是第三句话。
Oscar: This is the third sentence.
        """
        print("使用测试数据...")

    # 模拟中英文分离结果（阶段5的输出）
    zh_texts = []
    en_texts = []

    for para in content.split('\n\n'):
        para = para.strip()
        if not para:
            continue

        # 检测语言
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', para))
        en_chars = len(re.findall(r'[a-zA-Z]', para))

        if zh_chars > en_chars:
            zh_texts.append(para)
        else:
            en_texts.append(para)

    print(f"\n{'='*60}")
    print("阶段 6：去重")
    print(f"{'='*60}")

    print(f"\n去重前:")
    print(f"  中文段落: {len(zh_texts)}")
    print(f"  英文段落: {len(en_texts)}")

    # 执行去重
    result = deduplicate_paragraphs(zh_texts, en_texts)

    print(f"\n去重后:")
    print(f"  中文段落: {result['kept_zh_count']} (移除 {result['original_zh_count'] - result['kept_zh_count']})")
    print(f"  英文段落: {result['kept_en_count']} (移除 {result['original_en_count'] - result['kept_en_count']})")
    print(f"  总计移除: {result['total_duplicates']}")

    if result['duplicates_detail']:
        print(f"\n重复详情 (前10个):")
        for dup in result['duplicates_detail']:
            print(f"  [{dup['is_zh'] and '中文' or '英文'}] {dup['reason']}: {dup['preview']}...")

    print(f"\n保留的中文段落示例:")
    for s in result['kept_zh_samples']:
        print(f"  - {s[:50]}...")

    print(f"\n保留的英文段落示例:")
    for s in result['kept_en_samples']:
        print(f"  - {s[:50]}...")

    return result


if __name__ == '__main__':
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_demo(file_path)
