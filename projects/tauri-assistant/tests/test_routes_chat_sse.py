"""POST /api/chat must surface the trace id both as a response header
(available before any token streams) and in the final "done" SSE event, and
must keep working -- with an empty trace id -- when telemetry is inactive."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tauri_assistant import telemetry
from tauri_assistant.api import routes
from tauri_assistant.api.main import app
from tauri_assistant.config import Settings, get_settings
from tauri_assistant.rag.chat import ChatEvent


class _FakeStore:
    pass


def _fake_stream_chat(messages, settings, store, client=None, where=None, *, span=None):
    yield ChatEvent(type="sources", sources=[])
    yield ChatEvent(type="token", text="Hello")
    yield ChatEvent(type="done")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(routes, "stream_chat", _fake_stream_chat)
    app.dependency_overrides[get_settings] = lambda: Settings()  # type: ignore[call-arg]
    app.dependency_overrides[routes.get_store] = lambda: _FakeStore()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _parse_sse(body: str) -> list[dict[str, Any]]:
    import json

    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.split("\n")
        data_line = next(line for line in lines if line.startswith("data:"))
        events.append(json.loads(data_line.removeprefix("data:").strip()))
    return events


def test_done_event_and_header_carry_the_same_trace_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(telemetry, "new_trace_id", lambda: "a" * 32)

    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert resp.status_code == 200
    assert resp.headers["X-Trace-Id"] == "a" * 32
    events = _parse_sse(resp.text)
    done = next(e for e in events if "trace_id" in e)
    assert done["trace_id"] == "a" * 32


def test_chat_works_with_no_trace_id_when_telemetry_is_inactive(client: TestClient) -> None:
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})

    assert resp.status_code == 200
    assert resp.headers["X-Trace-Id"] == ""
