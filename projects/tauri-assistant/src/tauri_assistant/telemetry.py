"""Langfuse telemetry. This is the only module that imports `langfuse` --
business logic stays vendor-ignorant and every call site below degrades to a
no-op for free when telemetry is inactive (no keys configured).

Spans are created and ended *explicitly*, by threading the parent span
object through plain function parameters -- never via OpenTelemetry ambient
context (`start_as_current_observation` / contextvars). That sidesteps a
real hazard in this codebase: `POST /chat` streams its response through a
*sync* generator that Starlette iterates one item at a time via
`anyio.to_thread.run_sync` (see api/routes.py), and anyio copies the
contextvar Context on *every single call*. A `with start_as_current_...():`
that spans a `yield` would attach in one context copy and detach against a
different one -- children would orphan into their own traces, and OTel would
log "Failed to detach context" on every request.

Passing a plain Python span object across a generator boundary has none of
that risk -- it works exactly like passing any other object. This is also
why `generation_kwargs()` exists: rather than relying on ambient context to
tell the Langfuse OpenAI wrapper which trace/span it belongs to, we pass
`trace_id` / `parent_observation_id` explicitly as extra kwargs to
`client.chat.completions.create(...)`, which the wrapper reads directly
(see `langfuse/openai.py: _get_langfuse_data_from_kwargs`).

One more contextvar user worth flagging: `start_root()` below opens
`langfuse.propagate_attributes(...)` (the SDK's replacement for the older
`span.update_trace(...)`) only long enough to create the root span, then
exits it immediately -- never around a `yield`. That's the one place in this
module ambient context is touched at all, and it's synchronous and bounded
by construction.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal

from openai import OpenAI as VanillaOpenAI

if TYPE_CHECKING:
    from langfuse import Langfuse

    from tauri_assistant.settings import Settings

logger = logging.getLogger(__name__)

_client: Langfuse | None = None

ScoreDataType = Literal["NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT"]
ObservationType = Literal["span", "generation", "embedding", "retriever", "event", "agent", "tool", "chain"]


class _NullSpan:
    """No-op stand-in for a Langfuse span/generation, returned whenever
    telemetry is inactive so call sites never need an `if is_active():`."""

    trace_id: str | None = None
    id: str | None = None

    def update(self, **_kwargs: Any) -> _NullSpan:
        return self

    def start_observation(self, **_kwargs: Any) -> _NullSpan:
        return self

    def end(self, **_kwargs: Any) -> None:
        return None


_NULL_SPAN = _NullSpan()


def init(settings: Settings) -> None:
    """Idempotent. Call once from the FastAPI lifespan (or a CLI command
    that wants telemetry, e.g. `eval run`). No-ops when keys are absent."""
    global _client
    if _client is not None or not settings.langfuse.active:
        return

    from langfuse import Langfuse

    _client = Langfuse(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key,
        host=settings.langfuse.base_url,
        environment=settings.langfuse.environment,
        release=settings.langfuse.release,
        sample_rate=settings.langfuse.sample_rate,
        timeout=settings.langfuse.timeout_seconds,
        debug=settings.langfuse.debug,
    )

    if settings.langfuse.debug:
        # A blocking round trip -- only do this in debug mode, never on the
        # hot startup path, so a down Langfuse can't stall server boot.
        try:
            ok = _client.auth_check()
            logger.info("Langfuse auth_check: %s", "ok" if ok else "failed")
        except Exception:
            logger.exception("Langfuse auth_check raised")


def shutdown() -> None:
    """Flush pending events and release the client. Call from lifespan
    teardown. Bounded by `langfuse.timeout_seconds` -- a hung Langfuse must
    not hang Ctrl-C."""
    global _client
    if _client is None:
        return
    try:
        _client.flush()
        _client.shutdown()
    except Exception:
        logger.exception("Langfuse shutdown failed")
    finally:
        _client = None


def is_active() -> bool:
    return _client is not None


def raw_client() -> Langfuse | None:
    """The underlying Langfuse SDK client, for callers that need its wider
    surface (e.g. `eval/runner.py` creating datasets and running
    experiments). Everything in this module that only *writes*
    spans/scores should prefer the higher-level helpers above instead."""
    return _client


def new_trace_id() -> str | None:
    """A 32-char lowercase-hex OTel trace id, or None when inactive. Use
    this -- never `uuid4()` -- Langfuse rejects a dashed UUID."""
    if _client is None:
        return None
    from langfuse import Langfuse

    return Langfuse.create_trace_id()


def start_root(
    name: str,
    *,
    trace_id: str | None,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
) -> Any:
    """Create the root observation of a trace pre-minted via `new_trace_id`.
    Not a context manager -- must be ended with `.end()` (see module
    docstring). Safe to create in one function and end in another (e.g. a
    generator's `finally` block), since it carries no ambient context."""
    if _client is None or trace_id is None:
        return _NULL_SPAN

    from langfuse import propagate_attributes

    # Only wraps span *creation* -- propagate_attributes is itself
    # contextvar-based, so this must never span a `yield` either. It's
    # entered and exited synchronously, right here.
    with propagate_attributes(session_id=session_id, user_id=user_id, tags=tags):
        span = _client.start_observation(
            trace_context={"trace_id": trace_id}, name=name, as_type="span", input=input, metadata=metadata
        )
    return span


def child(
    parent: Any,
    name: str,
    *,
    as_type: ObservationType = "span",
    input: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Create a child observation under `parent`. Also not a context manager
    -- end it explicitly with `.end()`. A no-op parent (or None) yields a
    no-op child, so instrumentation composes without branching."""
    if parent is None or parent is _NULL_SPAN:
        return _NULL_SPAN
    return parent.start_observation(name=name, as_type=as_type, input=input, metadata=metadata)


@contextmanager
def observe(
    parent: Any,
    name: str,
    *,
    as_type: ObservationType = "span",
    input: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """`child()` as a context manager: creates the span, yields it, and
    always ends it -- marking it as an error first if the block raises.
    Safe to use as a `with` block here (unlike the per-turn root span in
    api/routes.py) because condense_query/retrieve are plain synchronous
    functions with no `yield` of their own to worry about."""
    span = child(parent, name, as_type=as_type, input=input, metadata=metadata)
    try:
        yield span
    except Exception as exc:
        span.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        span.end()


def make_openai_client(settings: Settings) -> Any:
    """A Langfuse-wrapped OpenAI client when telemetry is active, a vanilla
    one otherwise. This is what structurally confines auto-tracing to the
    live request paths: the eval runner never calls `init()`, so it always
    gets a vanilla client and never emits generation spans on its own --
    scope is enforced by construction, not by discipline at call sites."""
    if _client is None:
        return VanillaOpenAI(base_url=settings.chat.base_url, api_key=settings.chat.api_key)
    from langfuse.openai import OpenAI as LangfuseOpenAI

    return LangfuseOpenAI(base_url=settings.chat.base_url, api_key=settings.chat.api_key)


def generation_kwargs(parent: Any, *, name: str) -> dict[str, Any]:
    """Extra kwargs to splice into `client.chat.completions.create(...)` so
    the Langfuse OpenAI wrapper attaches its auto-traced generation under
    `parent`. Empty when inactive/no parent -- also correct for a *vanilla*
    OpenAI client, whose `create()` has no `**kwargs` and would raise
    TypeError on an unrecognized keyword (a real risk here: `stream_chat`/
    the eval runner accept an injected client, and the eval runner injects a
    vanilla one)."""
    if _client is None or parent is None or parent is _NULL_SPAN:
        return {}
    return {"trace_id": parent.trace_id, "parent_observation_id": parent.id, "name": name}


def record_score(
    *,
    trace_id: str,
    name: str,
    value: float,
    data_type: ScoreDataType = "NUMERIC",
    comment: str | None = None,
) -> bool:
    """Fire-and-forget: never raises into a request handler. Langfuse
    accepts a score for a trace that hasn't finished ingesting yet, so no
    flush is needed here."""
    if _client is None:
        return False
    try:
        _client.create_score(trace_id=trace_id, name=name, value=value, data_type=data_type, comment=comment)
        return True
    except Exception:
        logger.exception("Langfuse record_score failed")
        return False
