"""eval/harvest.py joins traces + retrieve-observation output + user_feedback
scores into GoldenItem candidates. The one behavior that matters: only a
thumbs-up trace gets suggested expected_matches -- seeding them from a
thumbs-down trace would bake the very failure the rating flags in as the
"expected" behavior."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from tauri_assistant import telemetry
from tauri_assistant.config import Settings
from tauri_assistant.eval.harvest import HarvestError, harvest


@dataclass
class FakeTrace:
    id: str
    session_id: str | None
    timestamp: datetime
    input: Any
    output: Any


@dataclass
class FakeScore:
    trace_id: str
    value: float
    comment: str | None


@dataclass
class FakeObservation:
    output: Any


@dataclass
class _Listing:
    data: list[Any]


class FakeTraceAPI:
    def __init__(self, traces: list[FakeTrace]) -> None:
        self._by_id = {t.id: t for t in traces}

    def list(self, **_kwargs: Any) -> _Listing:
        return _Listing(list(self._by_id.values()))

    def get(self, trace_id: str) -> FakeTrace:
        return self._by_id[trace_id]


class FakeScoreV2API:
    def __init__(self, scores: list[FakeScore]) -> None:
        self._scores = scores

    def get(self, **_kwargs: Any) -> _Listing:
        return _Listing(list(self._scores))


class FakeObservationsAPI:
    def __init__(self, by_trace_and_name: dict[tuple[str, str], list[FakeObservation]]) -> None:
        self._map = by_trace_and_name

    def get_many(self, *, trace_id: str, name: str, **_kwargs: Any) -> _Listing:
        return _Listing(self._map.get((trace_id, name), []))


@dataclass
class FakeAPI:
    trace: FakeTraceAPI
    score_v_2: FakeScoreV2API
    observations: FakeObservationsAPI


@dataclass
class FakeLangfuseClient:
    api: FakeAPI


@pytest.fixture(autouse=True)
def _reset_telemetry_client() -> Iterator[None]:
    previous = telemetry._client
    telemetry._client = None
    yield
    telemetry._client = previous


def _settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def _install_fake_client(
    traces: list[FakeTrace],
    scores: list[FakeScore],
    observations: dict[tuple[str, str], list[FakeObservation]],
) -> None:
    telemetry._client = FakeLangfuseClient(
        api=FakeAPI(
            trace=FakeTraceAPI(traces),
            score_v_2=FakeScoreV2API(scores),
            observations=FakeObservationsAPI(observations),
        )
    )


def test_thumbs_up_trace_gets_suggested_expected_matches() -> None:
    _install_fake_client(
        traces=[
            FakeTrace(
                id="up1",
                session_id="s1",
                timestamp=datetime.now(UTC),
                input={"question": "How do I create a system tray icon?"},
                output="Use the tray API like this...",
            )
        ],
        scores=[FakeScore(trace_id="up1", value=1, comment=None)],
        observations={
            ("up1", "retrieve"): [
                FakeObservation(
                    output=[
                        {
                            "url": "https://tauri.app/tray",
                            "heading_path": "learn/system-tray",
                            "source": "guide",
                        }
                    ]
                )
            ],
            ("up1", "condense_query"): [],
        },
    )

    items = harvest(_settings(), feedback="up")

    assert len(items) == 1
    item = items[0]
    assert item.feedback == 1
    assert item.needs_review is False
    assert item.suggested_source == "guide"
    assert item.suggested_expected_matches == ["learn/system-tray"]


def test_thumbs_down_trace_leaves_expected_matches_empty_and_flags_review() -> None:
    _install_fake_client(
        traces=[
            FakeTrace(
                id="down1",
                session_id="s1",
                timestamp=datetime.now(UTC),
                input={"question": "How do I disable autostart?"},
                output="I'm not sure, try looking at the config plugin.",
            )
        ],
        scores=[FakeScore(trace_id="down1", value=0, comment="cited the wrong plugin")],
        observations={
            ("down1", "retrieve"): [
                FakeObservation(
                    output=[
                        {
                            "url": "https://tauri.app/config",
                            "heading_path": "plugin/config",
                            "source": "guide",
                        }
                    ]
                )
            ],
            ("down1", "condense_query"): [],
        },
    )

    items = harvest(_settings(), feedback="down")

    assert len(items) == 1
    item = items[0]
    assert item.feedback == 0
    assert item.comment == "cited the wrong plugin"
    assert item.needs_review is True
    assert item.suggested_source is None
    assert item.suggested_expected_matches == []


def test_feedback_any_uses_trace_list_and_joins_scores_when_present() -> None:
    _install_fake_client(
        traces=[
            FakeTrace(
                id="t1", session_id=None, timestamp=datetime.now(UTC), input={"question": "q"}, output="a"
            )
        ],
        scores=[],
        observations={("t1", "retrieve"): [], ("t1", "condense_query"): []},
    )

    items = harvest(_settings(), feedback="any")

    assert len(items) == 1
    assert items[0].feedback is None
    assert items[0].needs_review is True  # no thumbs-up rating -> not auto-suggested


def test_harvest_without_configured_telemetry_raises() -> None:
    with pytest.raises(HarvestError):
        harvest(_settings(), feedback="any")
