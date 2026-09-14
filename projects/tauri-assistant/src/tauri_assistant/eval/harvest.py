"""Pull real production traces out of Langfuse and turn them into eval
candidates -- the growth path for eval/dataset.py's hand-written GOLDEN_SET,
so it can grow from what users actually asked instead of what we guessed.

Unlike the request paths (api/routes.py, rag/chat.py), which degrade
silently to a no-op when Langfuse isn't configured, harvesting *requires*
it: reading back telemetry that was never captured is a user error, not
something to paper over.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from tauri_assistant import telemetry
from tauri_assistant.config import Settings

FeedbackFilter = Literal["up", "down", "any"]

# score_v_2.get pages in batches of this size.
_SCORE_PAGE_SIZE = 100


class HarvestError(RuntimeError):
    """Telemetry isn't configured, or a Langfuse API call failed."""


@dataclass
class CandidateItem:
    trace_id: str
    session_id: str | None
    timestamp: str
    question: str
    standalone_query: str | None
    answer: str
    feedback: int | None  # 1 / 0 / None (unrated)
    comment: str | None
    retrieved: list[dict[str, Any]]
    suggested_source: str | None
    suggested_expected_matches: list[str]
    needs_review: bool

    def as_golden_item_snippet(self) -> str:
        matches = ", ".join(repr(m) for m in self.suggested_expected_matches)
        if not matches:
            matches = '"TODO"'
        return (
            "GoldenItem(\n"
            f'    "{self.trace_id[:8]}",  # TODO: give this a real id\n'
            f"    {self.question!r},\n"
            f'    "{self.suggested_source or "TODO"}",\n'
            f"    ({matches},),\n"
            "),"
        )


def _require_client(settings: Settings) -> Any:
    telemetry.init(settings)
    client = telemetry.raw_client()
    if client is None:
        raise HarvestError(
            "Langfuse is not configured (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY). "
            "Harvesting reads real telemetry back out, so unlike the live chat path it "
            "can't silently no-op -- set the keys in .env, or run "
            "`docker compose -f infra/langfuse/docker-compose.yml up -d` first."
        )
    return client


def _fetch_feedback_scores(client: Any, *, since: datetime, limit: int) -> dict[str, tuple[int, str | None]]:
    """trace_id -> (value, comment) for every `user_feedback` score since
    `since`, fetched once up front so filtering by rating never needs a
    per-trace round trip."""
    scores: dict[str, tuple[int, str | None]] = {}
    page = 1
    while len(scores) < limit:
        resp = client.api.score_v_2.get(
            name="user_feedback", from_timestamp=since, limit=_SCORE_PAGE_SIZE, page=page
        )
        if not resp.data:
            break
        for s in resp.data:
            if s.trace_id:
                scores[s.trace_id] = (int(s.value), s.comment)
        if len(resp.data) < _SCORE_PAGE_SIZE:
            break
        page += 1
    return scores


def _observation_output(client: Any, trace_id: str, name: str) -> Any:
    result = client.api.observations.get_many(trace_id=trace_id, name=name)
    return result.data[0] if result.data else None


def _build_candidate(client: Any, trace: Any, rating: tuple[int, str | None] | None) -> CandidateItem:
    retrieve_obs = _observation_output(client, trace.id, "retrieve")
    condense_obs = _observation_output(client, trace.id, "condense_query")

    retrieved = retrieve_obs.output if retrieve_obs and isinstance(retrieve_obs.output, list) else []
    standalone_query = condense_obs.output if condense_obs else None
    value, comment = rating if rating else (None, None)
    question = trace.input.get("question") if isinstance(trace.input, dict) else trace.input
    timestamp = trace.timestamp.isoformat() if hasattr(trace.timestamp, "isoformat") else str(trace.timestamp)

    # The judgement call that matters: only suggest expected_matches from a
    # thumbs-up trace. Seeding them from a thumbs-down trace would bake the
    # very failure the rating flags in as the "expected" behavior, and the
    # eval score would rise while quality falls.
    suggest = value == 1
    suggested_source = retrieved[0]["source"] if suggest and retrieved else None
    suggested_expected_matches = [r["heading_path"] for r in retrieved[:1]] if suggest else []

    return CandidateItem(
        trace_id=trace.id,
        session_id=trace.session_id,
        timestamp=timestamp,
        question=question or "",
        standalone_query=standalone_query,
        answer=trace.output or "",
        feedback=value,
        comment=comment,
        retrieved=retrieved,
        suggested_source=suggested_source,
        suggested_expected_matches=suggested_expected_matches,
        needs_review=not suggest,
    )


def harvest(
    settings: Settings,
    *,
    days: int = 7,
    feedback: FeedbackFilter = "any",
    limit: int = 200,
    tag: str = "chat",
) -> list[CandidateItem]:
    client = _require_client(settings)
    since = datetime.now(UTC) - timedelta(days=days)
    feedback_scores = _fetch_feedback_scores(client, since=since, limit=limit)

    if feedback in ("up", "down"):
        # Score-first: only the traces matching the requested rating are
        # ever fetched in full.
        wanted = 1 if feedback == "up" else 0
        matching_ids = [tid for tid, (value, _) in feedback_scores.items() if value == wanted][:limit]
        traces = [client.api.trace.get(trace_id) for trace_id in matching_ids]
    else:
        # Trace-first: list recent chat traces directly (one call already
        # returns input/output/session_id), then join feedback if any exists.
        resp = client.api.trace.list(tags=[tag], from_timestamp=since, limit=limit)
        traces = list(resp.data)

    return [_build_candidate(client, t, feedback_scores.get(t.id)) for t in traces]


def save_candidates(items: list[CandidateItem], settings: Settings) -> Path:
    out_dir = settings.data_dir / "eval_candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat().replace(":", "-")
    out_path = out_dir / f"{stamp}.json"
    out_path.write_text(json.dumps([asdict(i) for i in items], indent=2))
    return out_path
