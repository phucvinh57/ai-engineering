from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from tauri_assistant.ingest.types import Chunk
from tauri_assistant.ingest.variant import Variant


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


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    name: str
    count: int
    embedding_model: str
    strategy: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class Hit:
    text: str
    metadata: Mapping[str, Any]
    score: float


@dataclass(frozen=True, slots=True)
class RunStats:
    docs_total: int = 0
    sources_total: int = 0
    chunks_written: int = 0
    embed_seconds: float = 0.0


class EmbeddingStore(ABC):
    """Vector operations scoped to one variant's collection, as returned by
    `Repository.embedding(variant)`.
    """

    @abstractmethod
    def upsert_chunks(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> int: ...

    @abstractmethod
    def query(self, embedding: Sequence[float], k: int = 5, where: dict | None = None) -> list[Hit]: ...

    @abstractmethod
    def exists(self) -> bool: ...

    @abstractmethod
    def stats(self) -> Stats: ...

    @abstractmethod
    def drop(self) -> None: ...


class EmbeddingNamespace(ABC):
    """`repo.embedding(variant)` opens one collection; `repo.embedding.list()` spans all of them."""

    @abstractmethod
    def __call__(self, variant: Variant) -> EmbeddingStore: ...

    @abstractmethod
    def list(self) -> list[CollectionInfo]: ...


class VariantCatalog(ABC):
    @abstractmethod
    def register(self, variant: Variant) -> None: ...


class IngestRunCatalog(ABC):
    @abstractmethod
    def start(self, fingerprint: str, repo_shas: dict[str, str]) -> int: ...

    @abstractmethod
    def finish(self, run_id: int, stats: RunStats, token_stats: dict, status: str = "ok") -> None: ...

    @abstractmethod
    def latest(self, limit: int = 20) -> list[Mapping[str, Any]]: ...


class ParentSectionCatalog(ABC):
    @abstractmethod
    def save(self, fingerprint: str, parents: dict[str, tuple[str, str]]) -> None: ...

    @abstractmethod
    def get(self, fingerprint: str, parent_ids: Sequence[str]) -> dict[str, str]: ...


class EvalRunCatalog(ABC):
    @abstractmethod
    def record(self, fingerprint: str, dataset: str, metrics: dict[str, Any]) -> None: ...


class Repository(ABC):
    """Everything the vector store (Chroma) and the catalog (SQLite) provide,
    presented as one unit of storage keyed by `Variant`.

    Concrete implementations set each of these in `__init__`:

    - `embedding(variant)` -- vectors for one variant's collection
    - `variant` -- the catalog record for a variant's config
    - `ingest_run` -- ingest run bookkeeping
    - `parent_section` -- small-to-big parent text for expansion
    - `eval_run` -- recorded evaluation results
    """

    embedding: EmbeddingNamespace
    variant: VariantCatalog
    ingest_run: IngestRunCatalog
    parent_section: ParentSectionCatalog
    eval_run: EvalRunCatalog
