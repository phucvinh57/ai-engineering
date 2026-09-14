import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from tauri_assistant.api.schemas import (
    ChatRequest,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    StatsResponse,
)
from tauri_assistant.config import get_settings
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.rag.chat import stream_chat
from tauri_assistant.rag.retriever import retrieve
from tauri_assistant.sources.manifest import load_manifest

router = APIRouter(prefix="/api")


def _where_filter(source: str | None, maturity: str | None = None) -> dict[str, Any] | None:
    value = source or maturity
    return {"source": value} if value else None


def _sse_format(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    settings = get_settings()
    store = ChromaStore(settings)
    where = _where_filter(request.source, request.maturity)
    messages = [m.model_dump() for m in request.messages]

    def event_stream() -> Iterator[str]:
        for event in stream_chat(messages, settings, store, where=where):
            if event.type == "sources":
                sources = [
                    {
                        "heading_path": s.heading_path,
                        "url": s.url,
                        "source": s.source,
                        "score": s.score,
                    }
                    for s in (event.sources or [])
                ]
                yield _sse_format("sources", {"sources": sources})
            elif event.type == "thinking":
                yield _sse_format("thinking", {"text": event.text})
            elif event.type == "token":
                yield _sse_format("token", {"text": event.text})
            elif event.type == "done":
                yield _sse_format("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    settings = get_settings()
    store = ChromaStore(settings)
    where = _where_filter(request.source)
    chunks = retrieve(request.query, settings, store, top_k=request.top_k, where=where)
    return SearchResponse(
        results=[
            SearchResult(
                text=c.text,
                heading_path=c.heading_path,
                url=c.url,
                source=c.source,
                score=c.score,
            )
            for c in chunks
        ]
    )


@router.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    settings = get_settings()
    store = ChromaStore(settings)
    manifest = load_manifest(settings)
    last_fetch_at = max((e.fetched_at for e in manifest.values()), default=None)
    return StatsResponse(
        total_chunks=store.count(),
        chunks_by_source=store.stats_by_source(),
        last_fetch_at=last_fetch_at,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
