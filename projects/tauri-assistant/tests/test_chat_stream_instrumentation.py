"""stream_chat threads its `span` parameter into condense/retrieve/generate
without relying on ambient OpenTelemetry context (see telemetry.py's module
docstring for why that matters for a sync SSE generator). These tests drive
it with fakes, so they need no running Langfuse, Ollama, or Chroma."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tauri_assistant.config import Settings
from tauri_assistant.rag.chat import stream_chat


class RecordingSpan:
    """A minimal stand-in for a LangfuseSpan that records every child it is
    asked to create, so tests can assert on the shape of the span tree
    without a real Langfuse client."""

    def __init__(self, name: str = "root", trace_id: str = "trace", span_id: str = "root-id") -> None:
        self.name = name
        self.trace_id = trace_id
        self.id = span_id
        self.children: list[RecordingSpan] = []
        self.ended = False
        self.updates: list[dict[str, Any]] = []
        self._next_child_id = 0

    def start_observation(self, *, name: str, as_type: str, **kwargs: Any) -> RecordingSpan:
        self._next_child_id += 1
        child = RecordingSpan(name=name, trace_id=self.trace_id, span_id=f"{self.id}.{self._next_child_id}")
        self.children.append(child)
        return child

    def update(self, **kwargs: Any) -> RecordingSpan:
        self.updates.append(kwargs)
        return self

    def update_trace(self, **kwargs: Any) -> RecordingSpan:
        return self

    def end(self, **kwargs: Any) -> None:
        self.ended = True

    def child_named(self, name: str) -> RecordingSpan | None:
        return next((c for c in self.children if c.name == name), None)


@dataclass
class FakeDelta:
    content: str | None = None


@dataclass
class FakeChoice:
    delta: FakeDelta


@dataclass
class FakeChunk:
    choices: list[FakeChoice]


class FakeCompletions:
    """Fakes `client.chat.completions.create`. Non-streaming calls (used by
    condense_query) return a canned rewritten question; streaming calls
    (used by the final generation) yield canned token chunks."""

    def __init__(self, condensed: str = "standalone question", tokens: list[str] | None = None) -> None:
        self.condensed = condensed
        self.tokens = tokens if tokens is not None else ["Hello", " world"]
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(FakeChunk(choices=[FakeChoice(delta=FakeDelta(content=t))]) for t in self.tokens)
        message = type("Message", (), {"content": self.condensed})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


@dataclass
class FakeClient:
    completions: FakeCompletions = field(default_factory=FakeCompletions)

    def __post_init__(self) -> None:
        self.chat = FakeChat(self.completions)


class FakeStore:
    def query(self, embedding: list[float], top_k: int, where: dict[str, Any] | None = None) -> list[dict]:
        return [
            {
                "text": "system tray docs",
                "metadata": {
                    "heading_path": "learn/system-tray",
                    "url": "https://tauri.app/tray",
                    "source": "guide",
                },
                "distance": 0.1,
            }
        ]


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tauri_assistant.rag.retriever.embed_query", lambda text, settings: [0.1, 0.2, 0.3])


def _settings() -> Settings:
    return Settings(chat_stream_usage=False)  # type: ignore[call-arg]


def test_single_turn_has_no_condense_span_and_marks_metadata_correctly() -> None:
    root = RecordingSpan()
    client = FakeClient()
    messages = [{"role": "user", "content": "How do I create a system tray icon?"}]

    events = list(stream_chat(messages, _settings(), FakeStore(), client=client, span=root))

    assert root.child_named("condense_query") is None
    assert [e.type for e in events] == ["sources", "token", "token", "done"]
    assert "".join(e.text for e in events if e.type == "token") == "Hello world"


def test_multi_turn_creates_condense_span_nested_under_root() -> None:
    root = RecordingSpan()
    client = FakeClient()
    messages = [
        {"role": "user", "content": "How do I create a system tray icon?"},
        {"role": "assistant", "content": "Use the tray API..."},
        {"role": "user", "content": "does that work on mobile?"},
    ]

    list(stream_chat(messages, _settings(), FakeStore(), client=client, span=root))

    condense = root.child_named("condense_query")
    assert condense is not None
    assert condense.ended is True
    assert condense.updates[-1]["output"] == "standalone question"


def test_retrieve_span_nests_embed_and_chroma_children_under_root() -> None:
    root = RecordingSpan()
    client = FakeClient()
    messages = [{"role": "user", "content": "How do I create a system tray icon?"}]

    list(stream_chat(messages, _settings(), FakeStore(), client=client, span=root))

    retrieve_span = root.child_named("retrieve")
    assert retrieve_span is not None
    assert retrieve_span.ended is True
    assert retrieve_span.child_named("embed_query") is not None
    assert retrieve_span.child_named("chroma.query") is not None


def test_generation_kwargs_carry_trace_and_parent_ids_to_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    # generation_kwargs() only splices trace_id/parent_observation_id/name
    # in when telemetry is active (see telemetry.py) -- that's what makes it
    # safe against a vanilla OpenAI client, which has no **kwargs. Simulate
    # "active" so this test exercises that branch.
    from tauri_assistant import telemetry

    monkeypatch.setattr(telemetry, "_client", object())

    root = RecordingSpan(trace_id="trace-xyz", span_id="root-id")
    client = FakeClient()
    messages = [{"role": "user", "content": "How do I create a system tray icon?"}]

    list(stream_chat(messages, _settings(), FakeStore(), client=client, span=root))

    stream_call = next(c for c in client.completions.calls if c.get("stream"))
    assert stream_call["trace_id"] == "trace-xyz"
    assert stream_call["parent_observation_id"] == "root-id"
    assert stream_call["name"] == "generate_answer"


def test_no_span_means_no_generation_kwargs_and_no_errors() -> None:
    client = FakeClient()
    messages = [{"role": "user", "content": "How do I create a system tray icon?"}]

    events = list(stream_chat(messages, _settings(), FakeStore(), client=client, span=None))

    assert [e.type for e in events] == ["sources", "token", "token", "done"]
    stream_call = next(c for c in client.completions.calls if c.get("stream"))
    assert "trace_id" not in stream_call


def test_condense_query_error_marks_span_as_error_and_still_ends_it() -> None:
    root = RecordingSpan()

    class RaisingCompletions(FakeCompletions):
        def create(self, **kwargs: Any) -> Any:
            if not kwargs.get("stream"):
                raise RuntimeError("model unavailable")
            return super().create(**kwargs)

    client = FakeClient(completions=RaisingCompletions())
    messages = [
        {"role": "user", "content": "How do I create a system tray icon?"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "does that work on mobile?"},
    ]

    with pytest.raises(RuntimeError, match="model unavailable"):
        list(stream_chat(messages, _settings(), FakeStore(), client=client, span=root))

    condense = root.child_named("condense_query")
    assert condense is not None
    assert condense.ended is True
    assert condense.updates[-1]["level"] == "ERROR"
