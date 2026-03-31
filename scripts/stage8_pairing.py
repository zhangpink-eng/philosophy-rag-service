#!/usr/bin/env python3
"""
阶段 8：配对关联

功能：
1. 为中英文chunk生成pair_id
2. 建立配对关系
3. 生成最终索引数据

使用示例：
    python scripts/stage8_pairing.py <预处理结果.json>
"""
import sys
import json
import hashlib
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_pair_id(file_name: str, index: int, is_zh: bool) -> str:
    """生成pair_id"""
    prefix = file_name.replace('.txt', '').replace(' ', '_')[:20]
    lang = 'zh' if is_zh else 'en'
    return f"{prefix}_{lang}_{index}"


def create_paired_chunks(
    file_name: str,
    zh_chunks: List[str],
    en_chunks: List[str]
) -> List[Dict]:
    """
    创建配对的chunk列表

    策略：
    1. 中文chunk和英文chunk分别生成pair_id
    2. 相同位置的chunk使用相同的base_id
    3. 保留原始语言和翻译语言信息
    """
    chunks = []

    # 处理中文chunks
    for i, chunk_text in enumerate(zh_chunks):
        pair_id = generate_pair_id(file_name, i, is_zh=True)
        chunks.append({
            "pair_id": pair_id,
            "index": i,
            "text_zh": chunk_text,
            "text_en": "",  # 中文chunk没有英文翻译
            "language": "zh",
            "zh_source": "original",  # 原文
            "en_source": None,  # 无英文
        })

    # 处理英文chunks
    for i, chunk_text in enumerate(en_chunks):
        pair_id = generate_pair_id(file_name, i, is_zh=False)
        chunks.append({
            "pair_id": pair_id,
            "index": i,
            "text_zh": "",  # 英文chunk没有中文翻译
            "text_en": chunk_text,
            "language": "en",
            "zh_source": None,  # 无中文
            "en_source": "original",  # 原文
        })

    return chunks


def create_paired_chunks_v2(
    file_name: str,
    zh_chunks: List[Dict],
    en_chunks: List[Dict],
    pairing_mode: str = "parallel"
) -> List[Dict]:
    """
    创建配对的chunk列表（改进版）

    pairing_mode:
    - "parallel": 按位置配对（假设相同索引的中英文互为翻译）
    - "similarity": 按相似度配对（更准确但更慢）
    """
    chunks = []

    if pairing_mode == "parallel":
        # 按位置配对
        max_len = max(len(zh_chunks), len(en_chunks))

        for i in range(max_len):
            zh_text = zh_chunks[i]["text"] if i < len(zh_chunks) else ""
            en_text = en_chunks[i]["text"] if i < len(en_chunks) else ""

            # 生成pair_id
            if zh_text:
                pair_id = generate_pair_id(file_name, i, is_zh=True)
            else:
                pair_id = generate_pair_id(file_name, i, is_zh=False)

            chunks.append({
                "pair_id": pair_id,
                "index": i,
                "text_zh": zh_text,
                "text_en": en_text,
                "language": "both" if (zh_text and en_text) else ("zh" if zh_text else "en"),
                "zh_source": "original" if zh_text else None,
                "en_source": "original" if en_text else None,
            })

    return chunks


def run_demo():
    """运行配对演示"""

    print(f"\n{'='*60}")
    print("阶段 8：配对关联")
    print(f"{'='*60}")

    # 模拟语义分块结果
    file_name = "Coach_consultation_02242023"

    # 示例：按位置配对的中英文chunk
    zh_chunks = [
        {"text": "说话人01: 我会用中文介绍一下哲学咨询。", "size": 25},
        {"text": "Oscar: No, it's okay. I tell her.", "size": 30},
        {"text": "说话人02: 他说我相信你一定会做的好。", "size": 20},
    ]

    en_chunks = [
        {"text": "Speaker 01: I'll introduce philosophical consultation in Chinese.", "size": 60},
        {"text": "Oscar: I trust Angela.", "size": 20},
    ]

    print(f"\n配对前:")
    print(f"  中文 chunks: {len(zh_chunks)}")
    print(f"  英文 chunks: {len(en_chunks)}")

    # 创建配对
    paired = create_paired_chunks_v2(file_name, zh_chunks, en_chunks)

    print(f"\n配对后:")
    print(f"  总 chunks: {len(paired)}")

    print(f"\n配对结果示例:")
    for i, chunk in enumerate(paired):
        print(f"\n  Chunk {i+1}:")
        print(f"    pair_id: {chunk['pair_id']}")
        print(f"    language: {chunk['language']}")
        if chunk['text_zh']:
            print(f"    text_zh: {chunk['text_zh'][:50]}...")
        if chunk['text_en']:
            print(f"    text_en: {chunk['text_en'][:50]}...")

    # 生成索引数据
    print(f"\n{'='*60}")
    print("生成的索引数据结构")
    print(f"{'='*60}")

    for chunk in paired:
        print(f"""
{{
    "pair_id": "{chunk['pair_id']}",
    "text_zh": "{chunk['text_zh'][:30]}..." if chunk['text_zh'] else "",
    "text_en": "{chunk['text_en'][:30]}..." if chunk['text_en'] else "",
    "language": "{chunk['language']}",
    "source": "{file_name}"
}}
        """)

    return paired


def save_preprocessed_data(
    file_name: str,
    zh_chunks: List[Dict],
    en_chunks: List[Dict],
    output_path: str
):
    """保存预处理后的数据"""
    paired = create_paired_chunks_v2(file_name, zh_chunks, en_chunks)

    data = {
        "file_name": file_name,
        "language": "bilingual",
        "total_chunks": len(paired),
        "chunks": paired
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"保存到: {output_path}")
    return data


if __name__ == '__main__':
    paired = run_demo()
