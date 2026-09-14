import json
import time
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from tauri_assistant import telemetry
from tauri_assistant.api.schemas import (
    ChatRequest,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    StatsResponse,
)
from tauri_assistant.config import Settings, get_settings
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.rag.chat import stream_chat
from tauri_assistant.rag.retriever import retrieve
from tauri_assistant.sources.manifest import load_manifest

router = APIRouter(prefix="/api")


def get_store(settings: Settings = Depends(get_settings)) -> ChromaStore:
    return ChromaStore(settings)


def _where_filter(source: str | None, maturity: str | None = None) -> dict[str, Any] | None:
    value = source or maturity
    return {"source": value} if value else None


def _sse_format(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat")
def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    store: ChromaStore = Depends(get_store),
) -> StreamingResponse:
    where = _where_filter(request.source, request.maturity)
    messages = [m.model_dump() for m in request.messages]
    history_turns = len(messages) - 1
    # Minted here (before the generator body runs) so it can go both in a
    # response header -- available the instant headers arrive, before any
    # token streams -- and in the `done` SSE event.
    trace_id = telemetry.new_trace_id()

    def event_stream() -> Iterator[str]:
        t0 = time.perf_counter()
        answer_parts: list[str] = []
        ttft_ms: float | None = None
        disconnected = False

        # Created and ended *inside* this generator, since Starlette runs the
        # generator body after `chat()` has already returned (it iterates a
        # sync generator one item at a time via anyio.to_thread.run_sync --
        # see api/main.py's lifespan docstring / telemetry.py's module
        # docstring for why that also rules out ambient-context spans here).
        root = telemetry.start_root(
            "chat_turn",
            trace_id=trace_id,
            input={"question": messages[-1]["content"], "history_turns": history_turns, "where": where},
            metadata={
                "chat_model": settings.chat_model,
                "embedding_model": settings.embedding_model,
                "top_k": settings.retrieval_top_k,
                "condensed": history_turns > 0,
            },
            session_id=request.session_id,
            user_id=request.user_id,
            tags=["chat", settings.langfuse_environment],
        )
        chunks_returned = 0
        try:
            for event in stream_chat(messages, settings, store, where=where, span=root):
                if event.type == "sources":
                    chunks_returned = len(event.sources or [])
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
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t0) * 1000
                    yield _sse_format("thinking", {"text": event.text})
                elif event.type == "token":
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t0) * 1000
                    answer_parts.append(event.text or "")
                    yield _sse_format("token", {"text": event.text})
                elif event.type == "done":
                    yield _sse_format("done", {"trace_id": trace_id})
        except GeneratorExit:
            # A client disconnect closes this generator at the suspended
            # `yield`; re-raising is mandatory (swallowing it raises
            # "generator ignored GeneratorExit"). The `finally` below still
            # runs, so the span always ends -- possibly a beat late, since
            # the close is CPython refcount/GC-timed rather than immediate.
            disconnected = True
            raise
        except Exception as exc:
            root.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            answer = "".join(answer_parts)
            total_ms = (time.perf_counter() - t0) * 1000
            root.update(
                output=answer,
                metadata={
                    "ttft_ms": ttft_ms,
                    "total_ms": total_ms,
                    "chunks_returned": chunks_returned,
                    "client_disconnected": disconnected,
                },
            )
            root.update_trace(output=answer)
            root.end()
            # No flush() here -- the SDK batches on a background thread and
            # this must stay fire-and-forget.
            if trace_id:
                if ttft_ms is not None:
                    telemetry.record_score(trace_id=trace_id, name="ttft_ms", value=ttft_ms)
                telemetry.record_score(trace_id=trace_id, name="total_ms", value=total_ms)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Trace-Id": trace_id or "",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # don't let a proxy buffer away the TTFT we just measured
        },
    )


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    settings: Settings = Depends(get_settings),
    store: ChromaStore = Depends(get_store),
) -> SearchResponse:
    where = _where_filter(request.source)
    root = telemetry.start_root(
        "search",
        trace_id=telemetry.new_trace_id(),
        input=request.query,
        session_id=request.session_id,
        tags=["search", settings.langfuse_environment],
    )
    try:
        chunks = retrieve(request.query, settings, store, top_k=request.top_k, where=where, parent=root)
        results = [
            SearchResult(text=c.text, heading_path=c.heading_path, url=c.url, source=c.source, score=c.score)
            for c in chunks
        ]
        output = [r.model_dump() for r in results]
        root.update(output=output, metadata={"returned": len(chunks)})
        root.update_trace(output=output)
        return SearchResponse(results=results)
    except Exception as exc:
        root.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        root.end()


@router.post("/feedback", response_model=FeedbackResponse, status_code=202)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    # 202 + ok=True regardless of outcome: telemetry failure must never
    # surface as a UI error. `recorded` carries the truth for debugging.
    recorded = telemetry.record_score(
        trace_id=request.trace_id,
        name="user_feedback",
        value=float(request.value),
        data_type="BOOLEAN",
        comment=request.comment,
    )
    return FeedbackResponse(ok=True, recorded=recorded)


@router.get("/stats", response_model=StatsResponse)
def stats(
    settings: Settings = Depends(get_settings),
    store: ChromaStore = Depends(get_store),
) -> StatsResponse:
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
