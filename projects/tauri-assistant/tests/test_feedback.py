from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tauri_assistant import telemetry
from tauri_assistant.api.main import app

VALID_TRACE_ID = "a" * 32


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_thumbs_up_maps_to_boolean_score(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(telemetry, "record_score", lambda **kwargs: calls.append(kwargs) or True)

    resp = client.post("/api/feedback", json={"trace_id": VALID_TRACE_ID, "value": 1})

    assert resp.status_code == 202
    assert resp.json() == {"ok": True, "recorded": True}
    assert calls == [
        {
            "trace_id": VALID_TRACE_ID,
            "name": "user_feedback",
            "value": 1.0,
            "data_type": "BOOLEAN",
            "comment": None,
        }
    ]


def test_thumbs_down_with_comment(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(telemetry, "record_score", lambda **kwargs: calls.append(kwargs) or True)

    resp = client.post(
        "/api/feedback", json={"trace_id": VALID_TRACE_ID, "value": 0, "comment": "wrong permission cited"}
    )

    assert resp.status_code == 202
    assert calls[0]["value"] == 0.0
    assert calls[0]["comment"] == "wrong permission cited"


def test_malformed_trace_id_is_rejected(client: TestClient) -> None:
    resp = client.post("/api/feedback", json={"trace_id": "not-a-valid-id", "value": 1})
    assert resp.status_code == 422


def test_raising_backend_still_returns_202_with_recorded_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(**_kwargs: Any) -> bool:
        raise RuntimeError("langfuse down")

    # record_score itself never raises in production (it wraps its own body
    # in try/except) -- this simulates that contract still holding even if
    # something upstream misbehaves, by exercising the real function against
    # a client that raises.
    monkeypatch.setattr(telemetry, "_client", type("Raising", (), {"create_score": _raise})())

    resp = client.post("/api/feedback", json={"trace_id": VALID_TRACE_ID, "value": 1})

    assert resp.status_code == 202
    assert resp.json() == {"ok": True, "recorded": False}
