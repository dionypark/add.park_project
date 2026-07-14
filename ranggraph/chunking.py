from __future__ import annotations

import re
from dataclasses import dataclass

HEADER_RE = re.compile(r"^(#{1,6}\s+.*)$", re.MULTILINE)


@dataclass
class Chunk:
    text: str
    header: str | None


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    matches = list(HEADER_RE.finditer(text))
    if not matches:
        return [(None, text.strip())]

    sections = []
    if matches[0].start() > 0:
        pre = text[: matches[0].start()].strip()
        if pre:
            sections.append((None, pre))

    for i, m in enumerate(matches):
        header = m.group(1).lstrip("#").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((header, body))

    return sections


def _pack_paragraphs(body: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # a single paragraph longer than chunk_size gets hard-split on its own
        if len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(para), chunk_size - overlap):
                chunks.append(para[start : start + chunk_size])
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        chunks.append(current)
        tail = current[-overlap:] if overlap else ""
        current = f"{tail}\n\n{para}".strip() if tail else para

    if current:
        chunks.append(current)

    return chunks


def chunk_markdown(text: str, chunk_size: int = 800, overlap: int = 100) -> list[Chunk]:
    """Split markdown into overlapping chunks, keeping each section's header as metadata."""
    chunks: list[Chunk] = []
    for header, body in _split_sections(text):
        if not body:
            continue
        for piece in _pack_paragraphs(body, chunk_size, overlap):
            chunks.append(Chunk(text=piece, header=header))
    return chunks
