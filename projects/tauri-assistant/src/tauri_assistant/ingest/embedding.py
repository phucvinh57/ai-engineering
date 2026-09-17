"""Embedding model access."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger

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


class Embedder:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding.model
        self._model: Embeddings | None = None

    @property
    def model(self) -> Embeddings:
        # Deferred so constructing an Embedder never pays to load the model.
        if self._model is None:
            self._model = get_embedding_model(self.model_name)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.model.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self.model.embed_query(text)
