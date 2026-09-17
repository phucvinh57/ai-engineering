"""Fetch and ingest, triggered as fire-and-forget background actions.

Both can run for minutes (a shallow clone/pull, or a full embedding pass), so
a request only starts the job and returns immediately -- progress lives in
the server logs and, for ingest, in `catalog.latest_runs`. A per-action lock
rejects a second trigger while one is already in flight, since concurrent
writers to the same Chroma collection / SQLite catalog would race.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger

from tauri_assistant.api.schemas import ActionAccepted, IngestRequest
from tauri_assistant.ingest.pipeline import ingest
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


def _run_ingest(source: list[str], force: bool) -> None:
    try:
        ingest(source_names=source, force=force)
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
    tasks.add_task(_run_ingest, request.source, request.force)
    return ActionAccepted()
