#!/usr/bin/env python3
"""
阶段 7：分块 (Chunking)

功能：
1. 固定窗口分块（512 tokens, 64 overlap）
2. 语义分块（按段落）

使用示例：
    python scripts/stage7_chunking.py <文本文件>
"""
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class FixedWindowChunker:
    """固定窗口分块"""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Dict]:
        """分块并返回元数据"""
        chunks = []
        chars = list(text)
        start = 0

        while start < len(chars):
            end = min(start + self.chunk_size, len(chars))
            chunk_text = ''.join(chars[start:end])

            chunks.append({
                "text": chunk_text,
                "start": start,
                "end": end,
                "size": end - start
            })

            # 移动窗口（考虑overlap）
            start = end - self.overlap if end < len(chars) else end

        return chunks


class SemanticChunker:
    """语义分块（按段落）"""

    def __init__(self, max_chunk_size: int = 512, overlap: int = 64):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_paragraphs(self, paragraphs: List[str]) -> List[Dict]:
        """按段落分块，合并小段落"""
        chunks = []
        current_chunk = ""
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            # 单段落超过限制，进一步分割
            if para_size > self.max_chunk_size:
                # 保存当前chunk
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "size": current_size,
                        "para_count": len([p for p in paragraphs if p <= current_chunk])
                    })

                # 分割长段落
                sub_chunks = self._split_long_paragraph(para)
                chunks.extend(sub_chunks)

                current_chunk = ""
                current_size = 0

            # 合并到当前chunk
            elif current_size + para_size + 2 <= self.max_chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                    current_size += para_size + 2
                else:
                    current_chunk = para
                    current_size = para_size
            else:
                # 超过限制，保存当前chunk
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "size": current_size
                    })

                # overlap处理
                if self.overlap > 0 and len(chunks) > 0:
                    overlap_text = current_chunk[-self.overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                    current_size = len(overlap_text) + 2 + para_size
                else:
                    current_chunk = para
                    current_size = para_size

        # 处理最后一个chunk
        if current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "size": current_size
            })

        return chunks

    def _split_long_paragraph(self, para: str) -> List[Dict]:
        """分割长段落"""
        chunks = []
        start = 0

        while start < len(para):
            end = min(start + self.max_chunk_size, len(para))
            chunk_text = para[start:end]

            # 尝试在句子边界截断
            if end < len(para):
                for sep in ["。", "！", "？", ". ", "\n"]:
                    last_sep = chunk_text.rfind(sep)
                    if last_sep > self.max_chunk_size * 0.7:
                        chunk_text = chunk_text[:last_sep + 1]
                        end = start + len(chunk_text)
                        break

            chunks.append({
                "text": chunk_text.strip(),
                "size": len(chunk_text)
            })
            start = end

        return chunks


def run_demo(file_path: str = None):
    """运行分块演示"""

    if file_path and Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"加载文件: {file_path}")
    else:
        # 测试数据
        content = """
这是第一段内容。这是第一段内容。这是第一段内容。

这是第二段内容。第二段内容。第二段内容。第二段内容。

这是第三段内容。包含更多文字。第三段内容。

这是第四段内容。用于测试分块逻辑。
"""
        print("使用测试数据...")

    # 模拟中英文分离结果
    import re
    zh_paras, en_paras = [], []

    for para in content.split('\n\n'):
        para = para.strip()
        if not para:
            continue
        zh_chars = len(re.findall(r'[\u4e00-\u9fff]', para))
        en_chars = len(re.findall(r'[a-zA-Z]', para))
        if zh_chars > en_chars:
            zh_paras.append(para)
        else:
            en_paras.append(para)

    print(f"\n{'='*60}")
    print("阶段 7：分块 (Chunking)")
    print(f"{'='*60}")

    print(f"\n分块前:")
    print(f"  中文段落: {len(zh_paras)}")
    print(f"  英文段落: {len(en_paras)}")

    # 固定窗口分块
    print(f"\n--- 固定窗口分块 (512 chars, 64 overlap) ---")
    fixed_chunker = FixedWindowChunker(chunk_size=512, overlap=64)

    zh_fixed = []
    for para in zh_paras:
        chunks = fixed_chunker.chunk_text(para)
        zh_fixed.extend(chunks)

    en_fixed = []
    for para in en_paras:
        chunks = fixed_chunker.chunk_text(para)
        en_fixed.extend(chunks)

    print(f"  中文 chunks: {len(zh_fixed)}")
    print(f"  英文 chunks: {len(en_fixed)}")

    # 语义分块
    print(f"\n--- 语义分块 (按段落) ---")
    semantic_chunker = SemanticChunker(max_chunk_size=512, overlap=64)

    zh_semantic = semantic_chunker.chunk_paragraphs(zh_paras)
    en_semantic = semantic_chunker.chunk_paragraphs(en_paras)

    print(f"  中文 chunks: {len(zh_semantic)}")
    print(f"  英文 chunks: {len(en_semantic)}")

    # 统计chunk大小
    zh_sizes = [c['size'] for c in zh_semantic]
    en_sizes = [c['size'] for c in en_semantic]

    print(f"\n中文 chunk 大小统计:")
    print(f"  平均: {sum(zh_sizes)/len(zh_sizes):.0f} chars")
    print(f"  最小: {min(zh_sizes)} chars")
    print(f"  最大: {max(zh_sizes)} chars")

    print(f"\n英文 chunk 大小统计:")
    print(f"  平均: {sum(en_sizes)/len(en_sizes):.0f} chars")
    print(f"  最小: {min(en_sizes)} chars")
    print(f"  最大: {max(en_sizes)} chars")

    # 示例
    print(f"\n中文 chunk 示例:")
    for i, c in enumerate(zh_semantic[:3]):
        print(f"  Chunk {i+1} ({c['size']} chars): {c['text'][:80]}...")

    return {
        "fixed_chunks": {
            "zh": len(zh_fixed),
            "en": len(en_fixed)
        },
        "semantic_chunks": {
            "zh": len(zh_semantic),
            "en": len(en_semantic)
        }
    }


if __name__ == '__main__':
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_demo(file_path)
