"""Storage, behind one interface.

Callers depend on `Repository` and get an instance from `get_repository()` --
never on `ChromaSqliteRepository` or on chromadb/sqlite directly. That keeps
the vector store (Chroma) and the metadata store (SQLite) swappable together,
as a single unit, without touching ingest or the API.
"""

from __future__ import annotations

from functools import lru_cache

from tauri_assistant.repository.base import CollectionInfo, Hit, Repository, RunStats, Stats

__all__ = ["CollectionInfo", "Hit", "Repository", "RunStats", "Stats", "get_repository"]


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    from tauri_assistant.repository.chroma_sqlite import ChromaSqliteRepository

    return ChromaSqliteRepository()
