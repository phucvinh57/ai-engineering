"""Chroma + SQLite `Repository`.

Ingest builds one Chroma collection per `variant.fingerprint`, which already
folds in each source's git sha -- a sha or config change lands in a new
collection rather than patching a live one, so there is nothing to track per
source. SQLite holds what Chroma cannot: parent section texts, run history,
and evaluation results.

Nothing here should be imported directly -- go through
`tauri_assistant.repository.get_repository()`, typed as the `Repository`
interface.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

import chromadb
import peewee as pw
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from loguru import logger
from playhouse.shortcuts import model_to_dict

from tauri_assistant.ingest.types import Chunk
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository.base import (
    CollectionInfo,
    EmbeddingNamespace,
    EmbeddingStore,
    EvalRunCatalog,
    Hit,
    IngestRunCatalog,
    ParentSectionCatalog,
    Repository,
    RunStats,
    Stats,
    StoredChunk,
    VariantCatalog,
)
from tauri_assistant.repository.models import (
    MODELS,
    EvalRun,
    IngestRun,
    ParentSection,
    VariantRecord,
    database_proxy,
)
from tauri_assistant.settings import settings

# Chroma metadata rejects None outright, so optional fields must be omitted.
_OPTIONAL = ("parent_id", "url", "plugin", "module", "crate")


def _to_metadata(chunk: Chunk) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "document_id": chunk.document_id,
        "heading_path": chunk.heading_path,
        "source": str(chunk.metadata.get("source", "")),
        "path": str(chunk.metadata.get("path", "")),
        "kind": str(chunk.metadata.get("kind", "")),
        "chunk_index": int(chunk.metadata.get("chunk_index", 0)),
        "token_count": int(chunk.metadata.get("token_count", 0)),
    }
    # Writing None here raises TypeError from chromadb rather than storing a
    # null, so absent values are left out entirely.
    for key in _OPTIONAL:
        value = getattr(chunk, key, None) if key == "parent_id" else chunk.metadata.get(key)
        if value:
            metadata[key] = str(value)
    return metadata


class ChromaSqliteRepository(Repository):
    def __init__(self) -> None:
        self._client: ClientAPI | None = None
        self._db: pw.SqliteDatabase | None = None
        self.embedding = _ChromaEmbeddingNamespace(self)
        self.variant = _SqliteVariantCatalog(self)
        self.ingest_run = _SqliteIngestRunCatalog(self)
        self.parent_section = _SqliteParentSectionCatalog(self)
        self.eval_run = _SqliteEvalRunCatalog(self)

    # -- Chroma plumbing ---------------------------------------------------

    @property
    def _chroma(self) -> ClientAPI:
        # Deferred so constructing a repository never pays to open a client.
        if self._client is None:
            path = settings.paths.chroma_dir
            path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(path))
        return self._client

    def _collection(self, variant: Variant, create: bool = True) -> Collection:
        if not create:
            return self._chroma.get_collection(variant.collection_name)
        return self._chroma.get_or_create_collection(
            name=variant.collection_name,
            # Cosine has to be set at creation -- the default is l2, and
            # changing it later means rebuilding the whole index.
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": variant.embedding_model,
                "strategy": str(variant.chunking.get("strategy", "")),
                "fingerprint": variant.fingerprint,
            },
        )

    # -- SQLite plumbing (peewee) ---------------------------------------------

    def _catalog(self) -> pw.SqliteDatabase:
        # Deferred, like `_chroma` -- and rebinds `database_proxy` so each
        # repository instance points its models at its own catalog file
        # (tests swap `settings.paths.data_dir` per-instance).
        if self._db is None:
            path = settings.paths.catalog_db
            path.parent.mkdir(parents=True, exist_ok=True)
            db = pw.SqliteDatabase(str(path))
            database_proxy.initialize(db)
            db.create_tables(MODELS, safe=True)
            self._db = db
        return self._db


class _ChromaEmbeddingStore(EmbeddingStore):
    """Vectors for one variant's collection, as returned by `repo.embedding(variant)`."""

    def __init__(self, repo: ChromaSqliteRepository, variant: Variant) -> None:
        self._repo = repo
        self._variant = variant

    def upsert_chunks(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> int:
        if not chunks:
            return 0
        collection = self._repo._collection(self._variant)
        collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=[list(v) for v in vectors],
            metadatas=[_to_metadata(chunk) for chunk in chunks],
        )
        return len(chunks)

    def query(self, embedding: Sequence[float], k: int = 5, where: dict | None = None) -> list[Hit]:
        collection = self._repo._collection(self._variant, create=False)
        result = collection.query(
            query_embeddings=[list(embedding)],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[Hit] = []
        for doc, metadata, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            hits.append(Hit(text=doc, metadata=metadata, score=1.0 - float(distance)))
        return hits

    def sample(self, where: dict | None = None, limit: int = 5000) -> list[StoredChunk]:
        collection = self._repo._collection(self._variant, create=False)
        batch = collection.get(where=where, limit=limit, include=["documents", "metadatas"])
        ids = batch.get("ids") or []
        documents = batch.get("documents") or []
        metadatas = batch.get("metadatas") or []
        return [
            StoredChunk(id=i, text=doc, metadata=meta)
            for i, doc, meta in zip(ids, documents, metadatas, strict=True)
        ]

    def exists(self) -> bool:
        """Whether this exact (config, corpus-sha) variant has already been built.

        Collection identity folds in every source's git sha, so an existing,
        non-empty collection means this precise corpus state was already
        ingested -- there's nothing to patch, only a decision to skip.
        """
        try:
            return self._repo._collection(self._variant, create=False).count() > 0
        except Exception:
            return False

    def stats(self) -> Stats:
        try:
            collection = self._repo._collection(self._variant, create=False)
        except Exception:
            return Stats(self._variant.collection_name, self._variant.fingerprint, 0, 0, 0)

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
            collection=self._variant.collection_name,
            fingerprint=self._variant.fingerprint,
            chunks=collection.count(),
            documents=len(documents),
            tokens=tokens,
        )

    def drop(self) -> None:
        try:
            self._repo._chroma.delete_collection(self._variant.collection_name)
            logger.info(f"Dropped collection {self._variant.collection_name}")
        except Exception as exc:
            logger.warning(f"Could not drop {self._variant.collection_name}: {exc}")


class _ChromaEmbeddingNamespace(EmbeddingNamespace):
    def __init__(self, repo: ChromaSqliteRepository) -> None:
        self._repo = repo

    def __call__(self, variant: Variant) -> EmbeddingStore:
        return _ChromaEmbeddingStore(self._repo, variant)

    def list(self) -> list[CollectionInfo]:
        out = []
        for collection in self._repo._chroma.list_collections():
            metadata = collection.metadata or {}
            out.append(
                CollectionInfo(
                    name=collection.name,
                    count=collection.count(),
                    embedding_model=metadata.get("embedding_model", "?"),
                    strategy=metadata.get("strategy", "?"),
                    fingerprint=metadata.get("fingerprint", "?"),
                )
            )
        return out


class _SqliteVariantCatalog(VariantCatalog):
    def __init__(self, repo: ChromaSqliteRepository) -> None:
        self._repo = repo

    def register(self, variant: Variant) -> None:
        self._repo._catalog()
        VariantRecord.insert(
            fingerprint=variant.fingerprint,
            config_json=json.dumps(variant.as_dict(), sort_keys=True),
            embedding_model=variant.embedding_model,
            strategy=str(variant.chunking.get("strategy", "")),
            collection_name=variant.collection_name,
            created_at=time.time(),
        ).on_conflict_ignore().execute()

    def list(self) -> list[Mapping[str, Any]]:
        self._repo._catalog()
        query = VariantRecord.select().order_by(VariantRecord.created_at.desc())
        return list(query.dicts())

    def get(self, fingerprint: str) -> Mapping[str, Any] | None:
        self._repo._catalog()
        row = VariantRecord.get_or_none(VariantRecord.fingerprint == fingerprint)
        return None if row is None else model_to_dict(row)


class _SqliteIngestRunCatalog(IngestRunCatalog):
    def __init__(self, repo: ChromaSqliteRepository) -> None:
        self._repo = repo

    def start(self, fingerprint: str, repo_shas: dict[str, str]) -> int:
        self._repo._catalog()
        run = IngestRun.create(
            fingerprint=fingerprint,
            started_at=time.time(),
            repo_shas=json.dumps(repo_shas, sort_keys=True),
        )
        return run.id

    def finish(self, run_id: int, stats: RunStats, token_stats: dict, status: str = "ok") -> None:
        self._repo._catalog()
        IngestRun.update(
            finished_at=time.time(),
            docs_total=stats.docs_total,
            sources_total=stats.sources_total,
            chunks_written=stats.chunks_written,
            embed_seconds=stats.embed_seconds,
            token_stats=json.dumps(token_stats, sort_keys=True),
            status=status,
        ).where(IngestRun.id == run_id).execute()

    def latest(self, limit: int = 20) -> list[Mapping[str, Any]]:
        self._repo._catalog()
        query = (
            IngestRun.select(IngestRun, VariantRecord.embedding_model, VariantRecord.strategy)
            .join(
                VariantRecord,
                pw.JOIN.LEFT_OUTER,
                on=(IngestRun.fingerprint == VariantRecord.fingerprint),
            )
            .order_by(IngestRun.started_at.desc())
            .limit(limit)
        )
        return list(query.dicts())

    def for_variant(self, fingerprint: str, limit: int = 20) -> list[Mapping[str, Any]]:
        self._repo._catalog()
        query = (
            IngestRun.select()
            .where(IngestRun.fingerprint == fingerprint)
            .order_by(IngestRun.started_at.desc())
            .limit(limit)
        )
        return list(query.dicts())


class _SqliteParentSectionCatalog(ParentSectionCatalog):
    def __init__(self, repo: ChromaSqliteRepository) -> None:
        self._repo = repo

    def save(self, fingerprint: str, parents: dict[str, tuple[str, str]]) -> None:
        """`parent_id -> (document_id, text)`."""
        if not parents:
            return
        self._repo._catalog()
        rows = [
            {"fingerprint": fingerprint, "parent_id": pid, "document_id": doc, "text": text}
            for pid, (doc, text) in parents.items()
        ]
        ParentSection.insert_many(rows).on_conflict_replace().execute()

    def get(self, fingerprint: str, parent_ids: Sequence[str]) -> dict[str, str]:
        if not parent_ids:
            return {}
        self._repo._catalog()
        query = ParentSection.select(ParentSection.parent_id, ParentSection.text).where(
            (ParentSection.fingerprint == fingerprint) & (ParentSection.parent_id.in_(parent_ids))
        )
        return {row.parent_id: row.text for row in query}


class _SqliteEvalRunCatalog(EvalRunCatalog):
    def __init__(self, repo: ChromaSqliteRepository) -> None:
        self._repo = repo

    def record(self, fingerprint: str, dataset: str, metrics: dict[str, Any]) -> None:
        self._repo._catalog()
        EvalRun.create(
            fingerprint=fingerprint,
            dataset=dataset,
            created_at=time.time(),
            metrics_json=json.dumps(metrics, sort_keys=True),
        )
