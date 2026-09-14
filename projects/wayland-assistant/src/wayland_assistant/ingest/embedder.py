"""Batched local embeddings for chunk text, via sentence-transformers."""

from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from wayland_assistant.config import Settings

BATCH_SIZE = 64


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    model = _load_model(settings.embedding_model)
    embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(text: str, settings: Settings) -> list[float]:
    return embed_texts([text], settings)[0]
