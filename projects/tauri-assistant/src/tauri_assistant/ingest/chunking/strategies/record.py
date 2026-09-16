"""Identity chunking for sources that arrive pre-split.

Permission entries, TS symbols and Rust items are already atomic: one record
is one answer. The source does the segmenting, so this strategy only has to
pass documents through and let the post-processors enforce the size bounds.
"""

from __future__ import annotations

from collections.abc import Iterable

from tauri_assistant.ingest.types import Chunk, Document


class RecordChunker:
    name = "record"

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
