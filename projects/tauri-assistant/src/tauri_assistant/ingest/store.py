"""Chroma vector store wrapper, via LangChain's Chroma integration: persistent
store, upsert keyed by content_hash."""

from __future__ import annotations

from typing import Any

from langchain_chroma import Chroma

from tauri_assistant.config import Settings
from tauri_assistant.ingest.chunker import Chunk
from tauri_assistant.ingest.embedder import get_embeddings


class ChromaStore:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.vectorstore = Chroma(
            collection_name=settings.chroma_collection,
            embedding_function=get_embeddings(settings.embedding_model),
            persist_directory=str(settings.chroma_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )
        self._collection = self.vectorstore._collection

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        # Different pages can render down to identical chunk text (e.g. a
        # near-empty docs.rs page); Chroma rejects a batch with duplicate IDs.
        deduped: dict[str, tuple[Chunk, list[float]]] = {}
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            deduped.setdefault(chunk.content_hash, (chunk, embedding))

        self._collection.upsert(
            ids=list(deduped.keys()),
            embeddings=[e for _, e in deduped.values()],
            documents=[c.text for c, _ in deduped.values()],
            metadatas=[_metadata(c) for c, _ in deduped.values()],
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results = self.vectorstore.similarity_search_by_vector_with_relevance_scores(
            query_embedding, k=top_k, filter=where
        )
        return [{"text": doc.page_content, "metadata": doc.metadata, "distance": distance} for doc, distance in results]

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
        "heading_path": chunk.heading_path,
        "url": chunk.url,
        "chunk_index": chunk.chunk_index,
    }
