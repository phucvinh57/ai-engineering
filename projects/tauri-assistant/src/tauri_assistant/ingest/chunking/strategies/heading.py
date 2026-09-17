"""Heading-section chunking -- the default for prose.

Measured on the 161 English tauri-docs pages: 7.3 sections per page, p50 186
tokens. The docs are written so each `##`/`###` answers one question, which
makes the heading the unit a retriever actually wants. Bounding the tails
(27% of sections are stubs, 35% overrun MiniLM's budget) is left to the
post-processors so every strategy gets the same treatment.
"""

from __future__ import annotations

from collections.abc import Iterable

from tauri_assistant.ingest.chunking.base import split_sections
from tauri_assistant.ingest.chunking.strategies.base import Chunker
from tauri_assistant.ingest.types import Chunk, Document


class HeadingSectionChunker(Chunker):
    name = "heading"

    def __init__(self, min_level: int = 2, max_level: int = 4) -> None:
        self._min_level = min_level
        self._max_level = max_level

    def split(self, doc: Document) -> Iterable[Chunk]:
        sections = split_sections(doc.text, self._min_level, self._max_level)
        for index, section in enumerate(sections):
            yield Chunk(
                document_id=doc.id,
                text=section.text,
                breadcrumb=doc.breadcrumb + section.path,
                metadata={**doc.metadata, "chunk_index": index, "heading_level": section.level},
            )
