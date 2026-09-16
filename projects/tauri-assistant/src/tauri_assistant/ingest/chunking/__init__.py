"""Chunking strategy registry.

Adding a strategy means adding one module under `strategies/` and one entry
here. Everything before chunking (sources) and after it (embedding, storage,
retrieval) is unaffected, because both sides speak only `Document`/`Chunk`.
"""

from __future__ import annotations

from collections.abc import Callable

from tauri_assistant.ingest.chunking.base import Chunker, Section, split_sections
from tauri_assistant.ingest.chunking.postprocess import (
    AttachParent,
    ChunkResult,
    EnforceBudget,
    MergeUndersized,
    Pipeline,
)
from tauri_assistant.ingest.chunking.strategies import (
    FixedTokenChunker,
    HeadingSectionChunker,
    RecordChunker,
    WholeDocumentChunker,
)
from tauri_assistant.ingest.chunking.tokens import TokenCounter, get_token_counter
from tauri_assistant.settings import ChunkingSettings, settings

CHUNKERS: dict[str, Callable[[ChunkingSettings, TokenCounter], Chunker]] = {
    "heading": lambda cfg, counter: HeadingSectionChunker(),
    "record": lambda cfg, counter: RecordChunker(),
    "fixed": lambda cfg, counter: FixedTokenChunker(
        counter=counter, size=counter.budget, overlap=cfg.overlap_tokens
    ),
    "whole": lambda cfg, counter: WholeDocumentChunker(),
}


def build_chunker(
    strategy: str | None = None,
    cfg: ChunkingSettings | None = None,
    counter: TokenCounter | None = None,
) -> Pipeline:
    """Assemble a strategy with the post-processors every strategy shares."""
    cfg = cfg or settings.chunking
    counter = counter or get_token_counter()
    name = strategy or cfg.strategy

    if name not in CHUNKERS:
        known = ", ".join(sorted(CHUNKERS))
        raise ValueError(f"Unknown chunking strategy {name!r}. Available: {known}")

    return Pipeline(
        chunker=CHUNKERS[name](cfg, counter),
        steps=[
            # Order matters: merge stubs while they are still whole sections,
            # capture parents before anything is cut, then enforce the budget.
            MergeUndersized(counter, cfg.min_tokens),
            AttachParent(),
            EnforceBudget(counter),
        ],
        counter=counter,
    )


__all__ = [
    "CHUNKERS",
    "Chunker",
    "ChunkResult",
    "Pipeline",
    "Section",
    "TokenCounter",
    "build_chunker",
    "get_token_counter",
    "split_sections",
]
