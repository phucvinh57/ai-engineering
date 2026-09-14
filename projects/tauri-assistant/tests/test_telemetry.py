"""Telemetry must be fully inert with no keys configured: no warnings, no
network calls, and every call site gets a no-op handle rather than needing
to branch on `is_active()`."""

from collections.abc import Iterator

import pytest

from tauri_assistant import telemetry
from tauri_assistant.config import Settings


@pytest.fixture(autouse=True)
def _reset_client() -> Iterator[None]:
    previous = telemetry._client
    telemetry._client = None
    yield
    telemetry._client = previous


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


def test_init_is_a_noop_without_keys() -> None:
    telemetry.init(_settings(langfuse_public_key="", langfuse_secret_key=""))
    assert telemetry.is_active() is False
    assert telemetry.raw_client() is None


def test_init_is_a_noop_when_disabled_even_with_keys() -> None:
    telemetry.init(_settings(langfuse_enabled=False, langfuse_public_key="pk", langfuse_secret_key="sk"))
    assert telemetry.is_active() is False


def test_new_trace_id_is_none_when_inactive() -> None:
    assert telemetry.new_trace_id() is None


def test_start_root_returns_null_span_when_inactive() -> None:
    root = telemetry.start_root("chat_turn", trace_id=None, input="question")
    # Every method a call site might use must be a harmless no-op.
    root.update(output="answer", metadata={"a": 1})
    root.update_trace(session_id="s1")
    child = root.start_observation(name="child", as_type="span")
    child.end()
    root.end()


def test_child_of_null_parent_is_also_null() -> None:
    child = telemetry.child(None, "retrieve", as_type="retriever")
    child.update(output=[])
    child.end()


def test_generation_kwargs_empty_when_inactive() -> None:
    assert telemetry.generation_kwargs(None, name="generate_answer") == {}


def test_generation_kwargs_empty_for_null_parent_even_if_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "_client", object())  # pretend active
    assert telemetry.generation_kwargs(telemetry._NULL_SPAN, name="x") == {}


def test_record_score_returns_false_when_inactive() -> None:
    assert telemetry.record_score(trace_id="abc", name="user_feedback", value=1) is False


def test_record_score_returns_false_and_does_not_raise_when_client_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RaisingClient:
        def create_score(self, **_kwargs: object) -> None:
            raise RuntimeError("network down")

    monkeypatch.setattr(telemetry, "_client", _RaisingClient())
    assert telemetry.record_score(trace_id="abc", name="user_feedback", value=1) is False


def test_shutdown_without_init_is_a_noop() -> None:
    telemetry.shutdown()  # must not raise
    assert telemetry.is_active() is False
