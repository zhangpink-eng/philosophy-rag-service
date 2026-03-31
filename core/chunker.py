from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class Chunk:
    """通用 Chunk 结构"""
    text: str
    source_file: str
    chunk_index: int
    start_char: int
    end_char: int


class SemanticChunker:
    """
    语义分块器 - 预处理和索引共用

    策略：
    - 普通段落：保留或合并小段落
    - 超长段落：按句子边界截断
    - preserve_pairs 模式：每个段落独立，不合并（用于翻译对照格式）
    """

    def __init__(self, max_chunk_size: int = 512, overlap: int = 64):
        """
        Args:
            max_chunk_size: 最大 chunk 大小（字符数）
            overlap: 重叠大小（保留用于上下文连贯）
        """
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_paragraphs(
        self,
        paragraphs: List[str],
        preserve_pairs: bool = False
    ) -> List[Dict]:
        """
        按段落分块

        Args:
            paragraphs: 段落列表
            preserve_pairs: 是否保持段落独立（不合并）

        Returns:
            List[Dict]: [{"text": str, "size": int}, ...]
        """
        chunks = []
        current = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            if preserve_pairs:
                # zh_en_mixed 格式：每个段落独立，不合并
                chunks.append({'text': para, 'size': para_size})
                continue

            if para_size > self.max_chunk_size:
                # 保存当前 chunk
                if current:
                    chunks.append({
                        'text': '\n\n'.join(current),
                        'size': current_size
                    })
                    current = []
                    current_size = 0

                # 分割超长段落
                sub_chunks = self._split_long_paragraph(para)
                chunks.extend(sub_chunks)

            elif current_size + para_size + 2 <= self.max_chunk_size:
                # 合并到当前 chunk
                current.append(para)
                current_size += para_size + 2

            else:
                # 超过限制，保存当前 chunk
                if current:
                    chunks.append({
                        'text': '\n\n'.join(current),
                        'size': current_size
                    })

                # overlap 处理
                if self.overlap > 0 and current:
                    overlap_text = current[-1][-self.overlap:]
                    current = [overlap_text, para]
                    current_size = len(overlap_text) + 2 + para_size
                else:
                    current = [para]
                    current_size = para_size

        # 处理最后一个 chunk
        if current:
            chunks.append({
                'text': '\n\n'.join(current),
                'size': current_size
            })

        return chunks

    def _split_long_paragraph(self, para: str) -> List[Dict]:
        """
        分割超长段落（保持句子边界）

        Args:
            para: 段落文本

        Returns:
            List[Dict]: 分割后的 chunks
        """
        chunks = []
        start = 0

        while start < len(para):
            end = min(start + self.max_chunk_size, len(para))
            chunk_text = para[start:end]

            # 尝试在句子边界截断
            if end < len(para):
                truncated = False
                for sep in ["。", "！", "？", ". ", "\n"]:
                    last_sep = chunk_text.rfind(sep)
                    if last_sep > self.max_chunk_size * 0.7:
                        chunk_text = chunk_text[:last_sep + 1]
                        end = start + len(chunk_text)
                        truncated = True
                        break

                # 如果找不到合适的句子边界，但已经超过限制，强制截断
                if not truncated and end - start > self.max_chunk_size:
                    last_space = chunk_text.rfind(' ')
                    if last_space > self.max_chunk_size * 0.5:
                        chunk_text = chunk_text[:last_space]
                        end = start + len(chunk_text)

            chunks.append({
                'text': chunk_text.strip(),
                'size': len(chunk_text)
            })
            start = end

        return chunks


class FixedWindowChunker:
    """固定窗口分块器"""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        """
        Args:
            chunk_size: 固定窗口大小
            overlap: 重叠大小
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Dict]:
        """
        固定窗口分块

        Args:
            text: 文本

        Returns:
            List[Dict]: [{"text": str, "start": int, "end": int, "size": int}, ...]
        """
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

            start = end - self.overlap if end < len(chars) else end

        return chunks


def create_chunker(
    chunker_type: str = "semantic",
    max_chunk_size: int = 512,
    overlap: int = 64
):
    """
    工厂函数：创建分块器

    Args:
        chunker_type: "semantic" 或 "fixed"
        max_chunk_size: 最大 chunk 大小
        overlap: 重叠大小

    Returns:
        SemanticChunker 或 FixedWindowChunker
    """
    if chunker_type == "semantic":
        return SemanticChunker(max_chunk_size=max_chunk_size, overlap=overlap)
    elif chunker_type == "fixed":
        return FixedWindowChunker(chunk_size=max_chunk_size, overlap=overlap)
    else:
        raise ValueError(f"Unknown chunker type: {chunker_type}")


if __name__ == '__main__':
    # 测试 SemanticChunker
    print("=" * 60)
    print("测试 SemanticChunker")
    print("=" * 60)

    chunker = SemanticChunker(max_chunk_size=100, overlap=20)

    paragraphs = [
        "这是一个普通的段落。",
        "这是第二个段落，包含一些内容。",
        "这是一段很长的文字。" * 50,  # 超长段落
    ]

    chunks = chunker.chunk_paragraphs(paragraphs)

    print(f"生成了 {len(chunks)} 个 chunks")
    for i, chunk in enumerate(chunks):
        text = chunk['text']
        print(f"\nChunk {i+1} ({chunk['size']} chars):")
        print(text[:80] + "..." if len(text) > 80 else text)

    # 测试 preserve_pairs 模式
    print("\n" + "=" * 60)
    print("测试 preserve_pairs 模式")
    print("=" * 60)

    chunks_preserve = chunker.chunk_paragraphs(paragraphs, preserve_pairs=True)
    print(f"生成了 {len(chunks_preserve)} 个 chunks (preserve_pairs=True)")
    for i, chunk in enumerate(chunks_preserve):
        print(f"Chunk {i+1}: {chunk['text'][:40]}...")
