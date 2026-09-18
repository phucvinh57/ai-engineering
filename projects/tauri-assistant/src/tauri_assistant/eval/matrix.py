"""The variant matrix: four (embedding_model, chunking) combinations to
compare retrieval quality and build cost across, with the corpus (source git
shas) held fixed.

Built directly rather than through `Variant.from_settings` -- that reads
process-global `settings.embedding` / `settings.chunking`, which is exactly
what a matrix needs to vary independently of whatever the running process
happens to be configured with. `min_tokens` / `overlap_tokens` /
`include_translations` / `exclude_globs` are deliberately not part of the
matrix (kept at `ChunkingSettings`'s own defaults for every entry) -- only
`embedding_model`, `strategy`, and `max_tokens` are the axes under test.
"""

from __future__ import annotations

from dataclasses import dataclass

from tauri_assistant.ingest.variant import Variant
from tauri_assistant.settings import ChunkingSettings
from tauri_assistant.sources import get_sources

_DEFAULTS = ChunkingSettings()


@dataclass(frozen=True, slots=True)
class MatrixEntry:
    label: str
    embedding_model: str
    strategy: str
    max_tokens: int


MATRIX: tuple[MatrixEntry, ...] = (
    # Baseline: what's already deployed.
    MatrixEntry("bge-m3-heading-1024", "BAAI/bge-m3", "heading", 1024),
    # The structure-blind chunker `FixedTokenChunker` exists specifically to
    # be beaten by `heading` -- this is that comparison.
    MatrixEntry("bge-m3-fixed-1024", "BAAI/bge-m3", "fixed", 1024),
    # Tighter budget: the live corpus's chunk token p50 is only 84, so 1024
    # may be far more headroom than sections actually need.
    MatrixEntry("bge-m3-heading-512", "BAAI/bge-m3", "heading", 512),
    # A much smaller/cheaper embedding model. 256 is not a free choice: it's
    # MiniLM's own `max_seq_length`, and `HuggingFaceTokenCounter` raises
    # `ChunkBudgetError` above it (ingest/chunking/tokens.py).
    MatrixEntry("minilm-heading-256", "sentence-transformers/all-MiniLM-L6-v2", "heading", 256),
)


def build_variant(entry: MatrixEntry, source_shas: dict[str, str] | None = None) -> Variant:
    source_shas = source_shas if source_shas is not None else {s.name: s.git_sha for s in get_sources()}
    return Variant(
        embedding_model=entry.embedding_model,
        chunking={
            "strategy": entry.strategy,
            "max_tokens": entry.max_tokens,
            "min_tokens": _DEFAULTS.min_tokens,
            "overlap_tokens": _DEFAULTS.overlap_tokens,
        },
        sources={
            "include_translations": _DEFAULTS.include_translations,
            "exclude_globs": sorted(_DEFAULTS.exclude_globs),
        },
        source_shas=dict(sorted(source_shas.items())),
    )


def all_variants(source_shas: dict[str, str] | None = None) -> list[Variant]:
    """One `Variant` per `MATRIX` entry, sharing the same corpus snapshot
    (source shas resolved once) so the matrix compares config, not corpus
    drift between entries."""
    source_shas = source_shas if source_shas is not None else {s.name: s.git_sha for s in get_sources()}
    return [build_variant(entry, source_shas) for entry in MATRIX]
