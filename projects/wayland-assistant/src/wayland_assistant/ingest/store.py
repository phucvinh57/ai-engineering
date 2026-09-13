"""Chroma collection wrapper: persistent store, upsert keyed by content_hash."""

from __future__ import annotations

from typing import Any

import chromadb

from wayland_assistant.config import Settings
from wayland_assistant.ingest.chunker import Chunk


class ChromaStore:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[c.content_hash for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[_metadata(c) for c in chunks],
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        return [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(documents, metadatas, distances, strict=True)
        ]

    def count(self) -> int:
        return self._collection.count()

    def stats_by_source(self) -> dict[str, int]:
        result = self._collection.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in result["metadatas"]:
            source = meta.get("source", "unknown")
            counts[source] = counts.get(source, 0) + 1
        return counts


def _metadata(chunk: Chunk) -> dict[str, Any]:
    return {
        "source": chunk.source,
        "protocol_name": chunk.protocol_name,
        "interface_name": chunk.interface_name,
        "version": chunk.version,
        "heading_path": chunk.heading_path,
        "url": chunk.url,
        "chunk_index": chunk.chunk_index,
    }
