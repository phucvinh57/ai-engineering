"""Chunking strategy registry.

Adding a strategy means adding one module under `strategies/` and one entry
here. Everything before chunking (sources) and after it (embedding, storage,
retrieval) is unaffected, because both sides speak only `Document`/`Chunk`.
"""

from __future__ import annotations

from collections.abc import Callable

from tauri_assistant.ingest.chunking.base import Section, split_sections
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
)
from tauri_assistant.ingest.chunking.strategies.base import Chunker
from tauri_assistant.ingest.chunking.tokens import ChunkBudgetError, TokenCounter, get_token_counter
from tauri_assistant.settings import ChunkingSettings, settings

CHUNKERS: dict[str, Callable[[ChunkingSettings, TokenCounter], Chunker]] = {
    "heading": lambda cfg, counter: HeadingSectionChunker(),
    "record": lambda cfg, counter: RecordChunker(),
    "fixed": lambda cfg, counter: FixedTokenChunker(
        counter=counter, size=counter.budget, overlap=cfg.overlap_tokens
    ),
}


def build_chunker(
    strategy: str | None = None,
    cfg: ChunkingSettings | None = None,
    counter: TokenCounter | None = None,
) -> Pipeline:
    cfg = cfg or settings.chunking
    counter = counter or get_token_counter()
    strategy = strategy or cfg.strategy

    if strategy not in CHUNKERS:
        known = ", ".join(sorted(CHUNKERS))
        raise ValueError(f"Unknown chunking strategy {strategy!r}. Available: {known}")

    return Pipeline(
        chunker=CHUNKERS[strategy](cfg, counter),
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
    "ChunkBudgetError",
    "Chunker",
    "ChunkResult",
    "Pipeline",
    "Section",
    "TokenCounter",
    "build_chunker",
    "get_token_counter",
    "split_sections",
]
