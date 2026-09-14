"""Streaming retrieve-then-generate chat, with source citations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from openai import OpenAI

from wayland_assistant.config import Settings
from wayland_assistant.ingest.store import ChromaStore
from wayland_assistant.rag.prompts import SYSTEM_PROMPT
from wayland_assistant.rag.retriever import (
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


def stream_chat(
    messages: list[dict[str, str]],
    settings: Settings,
    store: ChromaStore,
    client: OpenAI | None = None,
    where: dict[str, Any] | None = None,
) -> Iterator[ChatEvent]:
    client = client or OpenAI(base_url=settings.chat_base_url, api_key=settings.chat_api_key)

    *history, last = messages
    question = last["content"]
    standalone_query = condense_query(history, question, settings, client)

    chunks = retrieve(standalone_query, settings, store, where=where)
    yield ChatEvent(type="sources", sources=chunks)

    context = assemble_context(chunks)
    system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context}" if context else SYSTEM_PROMPT

    chat_messages = [{"role": "system", "content": system_content}, *history, last]
    stream = client.chat.completions.create(
        model=settings.chat_model,
        messages=chat_messages,
        stream=True,
    )
    for event in stream:
        delta = event.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning:
            yield ChatEvent(type="thinking", text=reasoning)
        if delta.content:
            yield ChatEvent(type="token", text=delta.content)

    yield ChatEvent(type="done")
