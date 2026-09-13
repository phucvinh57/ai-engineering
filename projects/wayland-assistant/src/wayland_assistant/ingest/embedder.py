"""Batched OpenAI embeddings for chunk text."""

from __future__ import annotations

import tenacity
from openai import OpenAI

from wayland_assistant.config import Settings

BATCH_SIZE = 100


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
    stop=tenacity.stop_after_attempt(5),
)
def _embed_batch(client: OpenAI, model: str, batch: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=model, input=batch)
    return [item.embedding for item in resp.data]


def embed_texts(texts: list[str], settings: Settings, client: OpenAI | None = None) -> list[list[float]]:
    client = client or OpenAI(api_key=settings.openai_api_key)
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        embeddings.extend(_embed_batch(client, settings.embedding_model, batch))
    return embeddings


def embed_query(text: str, settings: Settings, client: OpenAI | None = None) -> list[float]:
    client = client or OpenAI(api_key=settings.openai_api_key)
    return _embed_batch(client, settings.embedding_model, [text])[0]
