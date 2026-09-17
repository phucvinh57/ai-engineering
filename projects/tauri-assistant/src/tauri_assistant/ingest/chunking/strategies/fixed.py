"""Fixed-size token windows with overlap -- the baseline to measure against.

Deliberately structure-blind: it cuts wherever the token count runs out,
including through a code fence. That is the behaviour `heading` is meant to
beat, so the sweep needs it available rather than argued about.
"""

from __future__ import annotations

from collections.abc import Iterable

from tauri_assistant.ingest.chunking.strategies.base import Chunker
from tauri_assistant.ingest.chunking.textsplit import window_by_tokens
from tauri_assistant.ingest.chunking.tokens import TokenCounter, get_token_counter
from tauri_assistant.ingest.types import Chunk, Document


class FixedTokenChunker(Chunker):
    name = "fixed"

    def __init__(
        self,
        counter: TokenCounter | None = None,
        size: int | None = None,
        overlap: int | None = None,
    ) -> None:
        self._counter = counter or get_token_counter()
        self._size = size or self._counter.budget
        self._overlap = overlap if overlap is not None else 0

    def split(self, doc: Document) -> Iterable[Chunk]:
        windows = window_by_tokens(doc.text, self._counter, self._size, self._overlap)
        for index, window in enumerate(windows):
            yield Chunk(
                document_id=doc.id,
                text=window,
                breadcrumb=doc.breadcrumb,
                metadata={**doc.metadata, "chunk_index": index},
            )

