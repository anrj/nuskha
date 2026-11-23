"""Split pages into overlapping chunks on sentence boundaries, keeping the page number for citations."""
import re
from dataclasses import dataclass

from .parse import Page

_SENTENCE = re.compile(r"(?<=[.!?։;])\s+|\n{2,}")


@dataclass
class Chunk:
    page: int
    text: str


def chunk_pages(pages: list[Page], size: int = 800, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        sentences = [s.strip() for s in _SENTENCE.split(page.text) if s and s.strip()]
        current = ""
        for s in sentences:
            while len(s) > size:  # one giant "sentence" (tables, no punctuation): hard split
                if current:
                    chunks.append(Chunk(page.number, current))
                    current = ""
                chunks.append(Chunk(page.number, s[:size]))
                s = s[size - overlap:]
            if current and len(current) + len(s) + 1 > size:
                chunks.append(Chunk(page.number, current))
                current = current[-overlap:].split(" ", 1)[-1]  # overlap without cutting a word
            current = f"{current} {s}".strip()
        if current:
            chunks.append(Chunk(page.number, current))
    return chunks
