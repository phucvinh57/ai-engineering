"""Whole-document chunking -- a measured baseline, not a real option.

97% of tauri-docs pages exceed `all-MiniLM-L6-v2`'s 256-token limit (p50 is
1487), so this strategy loses most of the median page. It is kept so the
sweep can demonstrate that empirically rather than by assertion.
"""

from __future__ import annotations

from collections.abc import Iterable

from tauri_assistant.ingest.types import Chunk, Document


class WholeDocumentChunker:
    name = "whole"

    def split(self, doc: Document) -> Iterable[Chunk]:
        text = doc.text.strip()
        if not text:
            return
        yield Chunk(
            document_id=doc.id,
            text=text,
            breadcrumb=doc.breadcrumb,
            metadata={**doc.metadata, "chunk_index": 0},
        )
