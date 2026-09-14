"""Batched local embeddings for chunk text, via LangChain's HuggingFace wrapper
(sentence-transformers under the hood)."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

from tauri_assistant.config import Settings

BATCH_SIZE = 64


@lru_cache(maxsize=4)
def get_embeddings(model_name: str) -> Embeddings:
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"batch_size": BATCH_SIZE},
    )


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    return get_embeddings(settings.embedding_model).embed_documents(texts)


def embed_query(text: str, settings: Settings) -> list[float]:
    return get_embeddings(settings.embedding_model).embed_query(text)
