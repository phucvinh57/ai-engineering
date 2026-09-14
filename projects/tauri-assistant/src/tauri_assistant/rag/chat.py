"""Streaming retrieve-then-generate chat, with source citations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from openai import OpenAI

from tauri_assistant import telemetry
from tauri_assistant.config import Settings
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.rag.prompts import build_system_prompt
from tauri_assistant.rag.retriever import (
    RetrievedChunk,
    assemble_context,
    condense_query,
    retrieve,
)


@dataclass
class ChatEvent:
    type: Literal["sources", "thinking", "token", "done"]
    sources: list[RetrievedChunk] | None = None
    text: str | None = None


@dataclass
class PreparedTurn:
    standalone_query: str
    chunks: list[RetrievedChunk]
    context: str
    chat_messages: list[dict[str, str]]


def prepare_turn(
    messages: list[dict[str, str]],
    settings: Settings,
    store: ChromaStore,
    client: OpenAI,
    where: dict[str, Any] | None = None,
    top_k: int | None = None,
    *,
    parent: Any = None,
) -> PreparedTurn:
    """Condense the follow-up into a standalone query, retrieve, and build
    the final message list. Shared by the live chat path below and the
    offline eval harness (eval/runner.py) so both exercise byte-identical
    prompts -- see rag/prompts.py:build_system_prompt for why that matters."""
    *history, last = messages
    question = last["content"]
    standalone_query = condense_query(history, question, settings, client, parent=parent)
    chunks = retrieve(standalone_query, settings, store, top_k=top_k, where=where, parent=parent)
    context = assemble_context(chunks)
    chat_messages = [{"role": "system", "content": build_system_prompt(context)}, *history, last]
    return PreparedTurn(standalone_query, chunks, context, chat_messages)


def stream_chat(
    messages: list[dict[str, str]],
    settings: Settings,
    store: ChromaStore,
    client: OpenAI | None = None,
    where: dict[str, Any] | None = None,
    *,
    span: Any = None,
) -> Iterator[ChatEvent]:
    """`span`, if given, is the root Langfuse observation for this turn (see
    telemetry.py). It is a plain object, not ambient context, so it is safe
    to hold across the `yield`s below -- there is no ordering/detach hazard
    the way there would be with a `with start_as_current_span():` block."""
    client = client or telemetry.make_openai_client(settings)

    prepared = prepare_turn(messages, settings, store, client, where=where, parent=span)
    yield ChatEvent(type="sources", sources=prepared.chunks)

    stream = client.chat.completions.create(
        model=settings.chat_model,
        messages=prepared.chat_messages,
        stream=True,
        **({"stream_options": {"include_usage": True}} if settings.chat_stream_usage else {}),
        **telemetry.generation_kwargs(span, name="generate_answer"),
    )
    for event in stream:
        if not event.choices:
            # The final chunk of a stream requested with
            # stream_options={"include_usage": True} carries usage only and
            # has an empty choices list.
            continue
        delta = event.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning:
            yield ChatEvent(type="thinking", text=reasoning)
        if delta.content:
            yield ChatEvent(type="token", text=delta.content)

    yield ChatEvent(type="done")
