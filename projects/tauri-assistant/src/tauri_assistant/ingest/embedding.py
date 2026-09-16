"""Embedding model access, with a content-addressed cache in front of it.

A full pass over the corpus is minutes of CPU, and a sweep re-embeds mostly
the same text: record-shaped sources (permissions, JS symbols, Rust items)
are untouched by prose chunking parameters, and after a repo update almost
every chunk is unchanged. Caching on `(model, sha256(text))` makes those
repeats near-free, which is what makes comparing variants practical.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger

from tauri_assistant.ingest import catalog
from tauri_assistant.ingest.types import content_hash
from tauri_assistant.settings import settings


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str | None = None) -> Embeddings:
    name = model_name or settings.embedding.model
    logger.info(f"Loading embedding model: {name}")
    return HuggingFaceEmbeddings(
        model_name=name,
        encode_kwargs={
            "batch_size": settings.embedding.batch_size,
            "normalize_embeddings": settings.embedding.normalize,
        },
    )


class CachedEmbedder:
    """Embeds only what the catalog has not seen before."""

    def __init__(self, model_name: str | None = None, use_cache: bool = True) -> None:
        self.model_name = model_name or settings.embedding.model
        self._use_cache = use_cache
        self._model: Embeddings | None = None
        self.hits = 0
        self.misses = 0

    @property
    def model(self) -> Embeddings:
        # Deferred so a fully cached run never pays to load the model.
        if self._model is None:
            self._model = get_embedding_model(self.model_name)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        hashes = [content_hash(text) for text in texts]
        cached = catalog.cached_vectors(self.model_name, hashes) if self._use_cache else {}

        missing = [h for h in dict.fromkeys(hashes) if h not in cached]
        if missing:
            wanted = {h: t for h, t in zip(hashes, texts, strict=True) if h in set(missing)}
            order = list(wanted)
            fresh = self.model.embed_documents([wanted[h] for h in order])
            computed = dict(zip(order, fresh, strict=True))
            if self._use_cache:
                catalog.store_vectors(self.model_name, computed)
            cached |= computed

        self.hits += len(hashes) - len(missing)
        self.misses += len(missing)
        return [cached[h] for h in hashes]

    def embed_query(self, text: str) -> list[float]:
        # Never cached: queries are one-shot and would only bloat the table.
        return self.model.embed_query(text)
