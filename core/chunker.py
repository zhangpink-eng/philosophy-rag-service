from typing import List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    source_file: str
    chunk_index: int
    start_char: int
    end_char: int


class TextChunker:
    """Text chunking using RecursiveCharacterTextSplitter."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: Optional[List[str]] = None
    ):
        if separators is None:
            separators = ["\n\n", "\n", ". ", " "]

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len
        )

    def chunk_text(self, text: str, source_file: str) -> List[Chunk]:
        """Split text into chunks with metadata."""
        splits = self.splitter.split_text(text)

        chunks = []
        for i, split_text in enumerate(splits):
            chunk = Chunk(
                text=split_text.strip(),
                source_file=source_file,
                chunk_index=i,
                start_char=i * (self.chunk_size - self.chunk_overlap),
                end_char=i * (self.chunk_size - self.chunk_overlap) + len(split_text)
            )
            chunks.append(chunk)

        return chunks

    def chunk_file(self, file_path: str) -> List[Chunk]:
        """Load a text file and chunk its content."""
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        source_file = file_path.split("/")[-1]
        return self.chunk_text(text, source_file)
