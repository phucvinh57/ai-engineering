from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger

from tauri_assistant.ingest.types import Chunk
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.settings import settings

# Chroma metadata rejects None outright, so optional fields must be omitted.
_OPTIONAL = ("parent_id", "url", "plugin", "module", "crate")


@dataclass(frozen=True, slots=True)
class Stats:
    collection: str
    fingerprint: str
    chunks: int
    documents: int
    tokens: int

    @property
    def mean_tokens(self) -> float:
        return self.tokens / self.chunks if self.chunks else 0.0


@lru_cache(maxsize=1)
def get_client() -> ClientAPI:
    path = settings.paths.chroma_dir
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def get_collection(variant: Variant, create: bool = True) -> Collection:
    client = get_client()
    if not create:
        return client.get_collection(variant.collection_name)
    return client.get_or_create_collection(
        name=variant.collection_name,
        # Cosine has to be set at creation -- the default is l2, and changing
        # it later means rebuilding the whole index.
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": variant.embedding_model,
            "strategy": str(variant.chunking.get("strategy", "")),
            "fingerprint": variant.fingerprint,
        },
    )


def to_metadata(chunk: Chunk) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "document_id": chunk.document_id,
        "heading_path": chunk.heading_path,
        "source": str(chunk.metadata.get("source", "")),
        "path": str(chunk.metadata.get("path", "")),
        "kind": str(chunk.metadata.get("kind", "")),
        "chunk_index": int(chunk.metadata.get("chunk_index", 0)),
        "token_count": int(chunk.metadata.get("token_count", 0)),
        "strategy": str(chunk.metadata.get("strategy", "")),
    }
    # Writing None here raises TypeError from chromadb rather than storing a
    # null, so absent values are left out entirely.
    for key in _OPTIONAL:
        value = getattr(chunk, key, None) if key == "parent_id" else chunk.metadata.get(key)
        if value:
            metadata[key] = str(value)
    return metadata


def upsert_chunks(variant: Variant, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> int:
    if not chunks:
        return 0
    collection = get_collection(variant)
    collection.upsert(
        ids=[chunk.id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=[list(v) for v in vectors],
        metadatas=[to_metadata(chunk) for chunk in chunks],
    )
    return len(chunks)


def delete_source(variant: Variant, source_name: str) -> int:
    """Remove every chunk belonging to a source, ahead of a full reindex.

    A source is reindexed as a whole -- there is no per-document diff to
    tell an edited page from a removed one -- so the simplest correct move
    is to clear everything the source previously wrote before re-chunking
    its current documents.
    """
    collection = get_collection(variant)
    removed = 0
    while True:
        batch = collection.get(where={"source": source_name}, limit=5_000, include=[])
        ids = batch.get("ids") or []
        if not ids:
            break
        collection.delete(ids=ids)
        removed += len(ids)
    return removed


def collection_stats(variant: Variant) -> Stats:
    try:
        collection = get_collection(variant, create=False)
    except Exception:
        return Stats(variant.collection_name, variant.fingerprint, 0, 0, 0)

    documents: set[str] = set()
    tokens = 0
    offset, page = 0, 5_000
    while True:
        batch = collection.get(limit=page, offset=offset, include=["metadatas"])
        metadatas = batch.get("metadatas") or []
        if not metadatas:
            break
        for metadata in metadatas:
            documents.add(str(metadata.get("document_id", "")))
            tokens += int(metadata.get("token_count", 0) or 0)
        offset += page

    return Stats(
        collection=variant.collection_name,
        fingerprint=variant.fingerprint,
        chunks=collection.count(),
        documents=len(documents),
        tokens=tokens,
    )


def query(
    variant: Variant,
    embedding: Sequence[float],
    k: int = 5,
    where: dict | None = None,
) -> list[dict[str, Any]]:
    collection = get_collection(variant, create=False)
    result = collection.query(
        query_embeddings=[list(embedding)],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    for doc, metadata, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
    ):
        hits.append({"text": doc, "metadata": metadata, "score": 1.0 - float(distance)})
    return hits


def list_collections() -> list[dict[str, Any]]:
    out = []
    for collection in get_client().list_collections():
        metadata = collection.metadata or {}
        out.append(
            {
                "name": collection.name,
                "count": collection.count(),
                "embedding_model": metadata.get("embedding_model", "?"),
                "strategy": metadata.get("strategy", "?"),
                "fingerprint": metadata.get("fingerprint", "?"),
            }
        )
    return out


def drop(variant: Variant) -> None:
    try:
        get_client().delete_collection(variant.collection_name)
        logger.info(f"Dropped collection {variant.collection_name}")
    except Exception as exc:
        logger.warning(f"Could not drop {variant.collection_name}: {exc}")
