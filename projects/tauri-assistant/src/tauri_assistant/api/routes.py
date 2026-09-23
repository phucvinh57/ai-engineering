"""Fetch and ingest, triggered as fire-and-forget background actions.

Both can run for minutes (a shallow clone/pull, or a full embedding pass), so
a request only starts the job and returns immediately -- progress lives in
the server logs and, for ingest, in `catalog.latest_runs`. A per-action lock
rejects a second trigger while one is already in flight, since concurrent
writers to the same Chroma collection / SQLite catalog would race.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from tauri_assistant import telemetry
from tauri_assistant.api.schemas import (
    ActionAccepted,
    ChatRequest,
    IngestRequest,
    IngestRunListResponse,
    RunSummary,
    SearchRequest,
    SearchResponse,
    SearchResult,
    VariantListResponse,
    VariantSummary,
)
from tauri_assistant.chat.llm import stream_completion
from tauri_assistant.chat.retrieval import NotIngestedError, current_variant, retrieve
from tauri_assistant.chat.turn import PreparedTurn, prepare_turn
from tauri_assistant.ingest.pipeline import ingest
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository import get_repository
from tauri_assistant.sources.fetch import sync_repos

router = APIRouter()

_fetch_lock = threading.Lock()
_ingest_lock = threading.Lock()


def _run_fetch() -> None:
    try:
        sync_repos()
    except Exception:
        logger.exception("Fetch failed")
    finally:
        _fetch_lock.release()


def _run_ingest(force: bool) -> None:
    try:
        ingest(force=force)
    except Exception:
        logger.exception("Ingest failed")
    finally:
        _ingest_lock.release()


@router.post("/fetch", status_code=202, response_model=ActionAccepted)
def fetch(tasks: BackgroundTasks) -> ActionAccepted:
    """Clone or pull the upstream repositories."""
    if not _fetch_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A fetch is already running.")
    tasks.add_task(_run_fetch)
    return ActionAccepted()


@router.post("/ingest", status_code=202, response_model=ActionAccepted)
def trigger_ingest(request: IngestRequest, tasks: BackgroundTasks) -> ActionAccepted:
    """Chunk, embed and upsert into the current variant's collection."""
    if not _ingest_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An ingest is already running.")
    tasks.add_task(_run_ingest, request.force)
    return ActionAccepted()


def _chat_events(prepared: PreparedTurn, root: Any) -> Iterator[str]:
    """NDJSON events: one `sources` event, then `delta` events, then `done`.

    Errors from the LLM call land mid-stream (after a 200 has already gone
    out), so they're reported as a `type: error` event rather than an HTTP
    error status.

    `root` is the trace's root span, created by `chat()` before this
    generator starts and ended here once it's fully drained -- never as a
    `with` block spanning a `yield` (see telemetry.py's module docstring for
    why Starlette's sync-generator streaming makes that unsafe).
    """
    yield (
        json.dumps(
            {
                "type": "sources",
                "trace_id": root.trace_id,
                "sources": [
                    {
                        "document_id": p.metadata.get("document_id", ""),
                        "heading_path": p.metadata.get("heading_path", ""),
                        "url": p.metadata.get("url"),
                        "score": p.score,
                    }
                    for p in prepared.passages
                ],
            }
        )
        + "\n"
    )

    usage = None
    try:
        for chunk in stream_completion(prepared.chat_messages, parent=root):
            if chunk.usage is not None:
                usage = chunk.usage.model_dump()
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield json.dumps({"type": "delta", "text": delta}) + "\n"
    except Exception as exc:
        logger.exception("Chat completion failed")
        root.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
        yield json.dumps({"type": "error", "detail": str(exc), "trace_id": root.trace_id}) + "\n"
        return
    finally:
        root.end()

    yield json.dumps({"type": "done", "usage": usage, "trace_id": root.trace_id}) + "\n"


@router.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    """Retrieve context for the last user turn, then stream a grounded reply.

    Response body is newline-delimited JSON, one object per line:
    `{"type": "sources", ...}`, then any number of `{"type": "delta", "text": ...}`,
    then a final `{"type": "done", "usage": ...}` (or `{"type": "error", ...}`).
    """
    if not request.messages or request.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="The last message must be from the user.")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    question = messages[-1]["content"]

    # No-ops end to end when telemetry is inactive -- see telemetry.py.
    root = telemetry.start_root(
        "chat", trace_id=telemetry.new_trace_id(), input={"question": question}, metadata={"k": request.k}
    )
    try:
        with telemetry.observe(root, "retrieve", as_type="retriever", input={"query": question}) as span:
            prepared = prepare_turn(messages, k=request.k)
            span.update(output={"passage_count": len(prepared.passages)})
    except NotIngestedError as exc:
        root.update(level="ERROR", status_message=str(exc))
        root.end()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return StreamingResponse(_chat_events(prepared, root), media_type="application/x-ndjson")


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Retrieve passages for a query, without completing a chat response."""
    try:
        passages = retrieve(request.query, k=request.k)
    except NotIngestedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return SearchResponse(
        results=[
            SearchResult(
                document_id=p.metadata.get("document_id", ""),
                heading_path=p.metadata.get("heading_path", ""),
                url=p.metadata.get("url"),
                score=p.score,
                text=p.text,
            )
            for p in passages
        ]
    )


def _run_summary(run: dict) -> RunSummary:
    return RunSummary(
        id=run["id"],
        started_at=run["started_at"],
        finished_at=run["finished_at"],
        status=run["status"],
        docs_total=run["docs_total"],
        sources_total=run["sources_total"],
        chunks_written=run["chunks_written"],
        embed_seconds=run["embed_seconds"],
    )


@router.get("/variants", response_model=VariantListResponse)
def list_variants() -> VariantListResponse:
    """Every variant ever registered, with its live chunk count and last ingest run."""
    db = get_repository()

    try:
        current_fingerprint = current_variant().fingerprint
    except Exception:
        # Sources aren't cloned yet (no /fetch has run), so nothing is "current" yet.
        current_fingerprint = None

    counts = {c.fingerprint: c.count for c in db.embedding.list()}

    variants = [
        VariantSummary(
            fingerprint=row["fingerprint"],
            collection_name=row["collection_name"],
            embedding_model=row["embedding_model"],
            strategy=row["strategy"],
            created_at=row["created_at"],
            chunk_count=counts.get(row["fingerprint"], 0),
            is_current=row["fingerprint"] == current_fingerprint,
            latest_run=next(
                (_run_summary(r) for r in db.ingest_run.for_variant(row["fingerprint"], limit=1)), None
            ),
        )
        for row in db.variant.list()
    ]
    return VariantListResponse(variants=variants, current_fingerprint=current_fingerprint)


@router.get("/variants/{fingerprint}/runs", response_model=IngestRunListResponse)
def variant_runs(fingerprint: str) -> IngestRunListResponse:
    """Full ingest run history for one variant, most recently started first."""
    runs = get_repository().ingest_run.for_variant(fingerprint, limit=50)
    return IngestRunListResponse(runs=[_run_summary(r) for r in runs])


@router.delete("/variants/{fingerprint}", status_code=204)
def drop_variant(fingerprint: str) -> None:
    """Delete a variant's Chroma collection to reclaim space.

    Catalog history (the variant row and its ingest runs) is kept, so past
    measurements stay keyed to the config and corpus state that produced
    them -- only the vectors themselves are removed.
    """
    db = get_repository()
    row = db.variant.get(fingerprint)
    if row is None:
        raise HTTPException(status_code=404, detail="No such variant.")
    variant = Variant.from_dict(json.loads(row["config_json"]))
    db.embedding(variant).drop()
