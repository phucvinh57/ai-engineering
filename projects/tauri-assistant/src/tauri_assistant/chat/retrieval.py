"""Query the current variant's collection, expanding hits to parent text.

"Current variant" is computed the same way `ingest()` does -- config plus each
source's live git sha -- so chat always reads whatever collection the most
recent matching ingest actually wrote, without a separate "active variant"
pointer to keep in sync.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tauri_assistant.ingest.embedding import Embedder
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository import get_repository
from tauri_assistant.sources import get_sources


class NotIngestedError(RuntimeError):
    """The current (corpus, chunking, embedding) variant has no collection yet."""


@dataclass(frozen=True, slots=True)
class Passage:
    text: str
    metadata: Mapping[str, Any]
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalTiming:
    embed_ms: float
    query_ms: float
    expand_ms: float


def current_variant() -> Variant:
    source_shas = {s.name: s.git_sha for s in get_sources()}
    return Variant.from_settings(source_shas)


def retrieve_with_timing(
    query: str, k: int = 6, variant: Variant | None = None
) -> tuple[list[Passage], RetrievalTiming]:
    """`retrieve()` below and `chat/turn.py`'s `prepare_turn()` both funnel
    through this -- one implementation of embed -> query -> parent-expand, so
    the eval runner's per-stage latency numbers can never drift from what
    the live path actually does."""
    db = get_repository()
    variant = variant or current_variant()
    store = db.embedding(variant)
    if not store.exists():
        raise NotIngestedError(f"No ingested data for {variant.describe()}; POST /ingest first.")

    t0 = time.perf_counter()
    vector = Embedder(variant.embedding_model).embed_query(query)
    t1 = time.perf_counter()
    hits = store.query(vector, k=k)
    t2 = time.perf_counter()

    parent_ids = sorted({pid for h in hits if (pid := h.metadata.get("parent_id"))})
    parents = db.parent_section.get(variant.fingerprint, parent_ids) if parent_ids else {}

    passages = []
    for hit in hits:
        parent_id = hit.metadata.get("parent_id")
        text = parents.get(parent_id, hit.text) if parent_id else hit.text
        passages.append(Passage(text=text, metadata=hit.metadata, score=hit.score))
    t3 = time.perf_counter()

    timing = RetrievalTiming(embed_ms=(t1 - t0) * 1000, query_ms=(t2 - t1) * 1000, expand_ms=(t3 - t2) * 1000)
    return passages, timing


def retrieve(query: str, k: int = 6, variant: Variant | None = None) -> list[Passage]:
    """`variant` defaults to `current_variant()` -- the live `/chat` and
    `/search` routes always call this with the default. Passing one
    explicitly is what lets the eval runner query an arbitrary variant's
    collection in-process, without restarting the server per variant."""
    passages, _timing = retrieve_with_timing(query, k, variant)
    return passages
