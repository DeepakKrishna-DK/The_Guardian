"""
Guardian Knowledge — Chunker
==============================
Splits documents into overlapping chunks for vector indexing.

Constitution reference: Section 8 (Memory) — Knowledge tier.

Design:
  - Word-count based chunking (no tokenizer dependency)
  - Configurable chunk_size and overlap
  - Each chunk carries source + position metadata for attribution
  - Chunks IDs are deterministic: sha256(source:index)[:16]

Authority: Level 0 — read-only, no side effects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

CHUNK_SIZE_WORDS  = 250   # ~375 tokens for English prose
CHUNK_OVERLAP_WORDS = 40  # ~60 tokens overlap between chunks


@dataclass
class Chunk:
    """A piece of a document ready for embedding and storage."""
    id: str
    content: str
    source: str          # original file path (relative to workspace)
    chunk_index: int     # 0-based position in source
    total_chunks: int    # total chunks for this source
    word_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def preview(self, max_chars: int = 120) -> str:
        text = self.content.replace("\n", " ").strip()
        return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _make_chunk_id(source: str, index: int) -> str:
    raw = f"{source}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


class Chunker:
    """
    Splits plain text into overlapping word-count chunks.

    Usage:
        chunker = Chunker(chunk_size=250, overlap=40)
        chunks = chunker.chunk(text, source="docs/guide.md")
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE_WORDS,
        overlap: int = CHUNK_OVERLAP_WORDS,
    ) -> None:
        if overlap >= chunk_size:
            raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")
        self._size    = chunk_size
        self._overlap = overlap

    def chunk(self, text: str, source: str) -> list[Chunk]:
        """Split text into overlapping chunks. Returns empty list for empty text."""
        if not text or not text.strip():
            return []

        words = text.split()
        if not words:
            return []

        step   = self._size - self._overlap
        starts = list(range(0, len(words), step))
        raw_chunks = [
            " ".join(words[s : s + self._size])
            for s in starts
            if words[s : s + self._size]
        ]

        # Remove duplicates that can appear when text is shorter than one chunk
        seen: set[str] = set()
        deduped: list[str] = []
        for c in raw_chunks:
            if c not in seen:
                seen.add(c)
                deduped.append(c)

        total = len(deduped)
        return [
            Chunk(
                id=_make_chunk_id(source, i),
                content=c,
                source=source,
                chunk_index=i,
                total_chunks=total,
                word_count=len(c.split()),
            )
            for i, c in enumerate(deduped)
        ]
