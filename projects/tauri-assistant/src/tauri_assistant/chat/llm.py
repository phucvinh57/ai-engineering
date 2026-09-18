"""Chat completions against `settings.chat`'s OpenAI-compatible endpoint (Ollama by default)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

from tauri_assistant import telemetry
from tauri_assistant.settings import settings


@lru_cache(maxsize=1)
def get_chat_client() -> OpenAI:
    # Langfuse-wrapped when telemetry is active, vanilla otherwise -- see
    # `telemetry.make_openai_client`. Safe to cache: telemetry.init() runs
    # once at lifespan startup, before the first request can reach here.
    return telemetry.make_openai_client(settings)


def stream_completion(
    messages: Iterable[ChatCompletionMessageParam],
    *,
    parent: Any = None,
) -> Iterator[ChatCompletionChunk]:
    # Some Ollama builds 400 on stream_options -- CHAT_STREAM_USAGE lets that be
    # disabled without touching code.
    stream_options = {"include_usage": True} if settings.chat.stream_usage else None
    return get_chat_client().chat.completions.create(
        model=settings.chat.model,
        messages=list(messages),
        stream=True,
        stream_options=stream_options,
        # {} when telemetry is inactive or `parent` is None/no-op -- a vanilla
        # OpenAI client's create() has no **kwargs and would TypeError on an
        # unrecognized keyword, so this must never add keys in that case.
        **telemetry.generation_kwargs(parent, name="chat"),
    )
