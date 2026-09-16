"""SQLite catalog for everything Chroma should not hold.

Chroma stays the single source of truth for *what is indexed* -- the
`doc_hash` on each chunk makes the ingest manifest derivable from the
collection itself, so there is nothing to drift if a run dies halfway. This
catalog holds only the things that are not a duplicate of that: parent
section texts, run history, evaluation results, and the embedding cache.
"""

from __future__ import annotations

import array
import json
import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tauri_assistant.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS variant (
    fingerprint      TEXT PRIMARY KEY,
    config_json      TEXT NOT NULL,
    embedding_model  TEXT NOT NULL,
    strategy         TEXT NOT NULL,
    collection_name  TEXT NOT NULL,
    created_at       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_run (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint      TEXT NOT NULL,
    started_at       REAL NOT NULL,
    finished_at      REAL,
    repo_shas        TEXT,
    docs_total       INTEGER DEFAULT 0,
    docs_changed     INTEGER DEFAULT 0,
    docs_removed     INTEGER DEFAULT 0,
    chunks_written   INTEGER DEFAULT 0,
    chunks_deleted   INTEGER DEFAULT 0,
    embed_seconds    REAL DEFAULT 0,
    cache_hits       INTEGER DEFAULT 0,
    cache_misses     INTEGER DEFAULT 0,
    token_stats      TEXT,
    status           TEXT DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS parent_section (
    fingerprint  TEXT NOT NULL,
    parent_id    TEXT NOT NULL,
    document_id  TEXT NOT NULL,
    text         TEXT NOT NULL,
    PRIMARY KEY (fingerprint, parent_id)
);

CREATE TABLE IF NOT EXISTS eval_run (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint   TEXT NOT NULL,
    dataset       TEXT NOT NULL,
    created_at    REAL NOT NULL,
    metrics_json  TEXT NOT NULL
);

-- Keyed by model as well as text: the same chunk embedded by two models is
-- two different vectors, and a sweep changes models underneath us.
CREATE TABLE IF NOT EXISTS embedding_cache (
    model      TEXT NOT NULL,
    text_hash  TEXT NOT NULL,
    vector     BLOB NOT NULL,
    PRIMARY KEY (model, text_hash)
);

CREATE INDEX IF NOT EXISTS idx_parent_doc ON parent_section (fingerprint, document_id);
CREATE INDEX IF NOT EXISTS idx_run_variant ON ingest_run (fingerprint);
"""


@dataclass(frozen=True, slots=True)
class RunStats:
    docs_total: int = 0
    docs_changed: int = 0
    docs_removed: int = 0
    chunks_written: int = 0
    chunks_deleted: int = 0
    embed_seconds: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


def _path() -> Path:
    db = settings.paths.catalog_db
    db.parent.mkdir(parents=True, exist_ok=True)
    return db


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_path())
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def pack_vector(vector: Sequence[float]) -> bytes:
    return array.array("f", vector).tobytes()


def unpack_vector(blob: bytes) -> list[float]:
    values = array.array("f")
    values.frombytes(blob)
    return list(values)


def register_variant(variant, config: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO variant "
            "(fingerprint, config_json, embedding_model, strategy, collection_name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                variant.fingerprint,
                json.dumps(config, sort_keys=True),
                variant.embedding_model,
                str(variant.chunking.get("strategy", "")),
                variant.collection_name,
                time.time(),
            ),
        )


def start_run(fingerprint: str, repo_shas: dict[str, str]) -> int:
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO ingest_run (fingerprint, started_at, repo_shas) VALUES (?, ?, ?)",
            (fingerprint, time.time(), json.dumps(repo_shas, sort_keys=True)),
        )
        return int(cursor.lastrowid)


def finish_run(run_id: int, stats: RunStats, token_stats: dict, status: str = "ok") -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE ingest_run SET finished_at=?, docs_total=?, docs_changed=?, docs_removed=?, "
            "chunks_written=?, chunks_deleted=?, embed_seconds=?, cache_hits=?, cache_misses=?, "
            "token_stats=?, status=? WHERE id=?",
            (
                time.time(),
                stats.docs_total,
                stats.docs_changed,
                stats.docs_removed,
                stats.chunks_written,
                stats.chunks_deleted,
                stats.embed_seconds,
                stats.cache_hits,
                stats.cache_misses,
                json.dumps(token_stats, sort_keys=True),
                status,
                run_id,
            ),
        )


def save_parents(fingerprint: str, parents: dict[str, tuple[str, str]]) -> None:
    """`parent_id -> (document_id, text)`."""
    if not parents:
        return
    with connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO parent_section "
            "(fingerprint, parent_id, document_id, text) VALUES (?, ?, ?, ?)",
            [(fingerprint, pid, doc, text) for pid, (doc, text) in parents.items()],
        )


def get_parents(fingerprint: str, parent_ids: Sequence[str]) -> dict[str, str]:
    if not parent_ids:
        return {}
    placeholders = ",".join("?" * len(parent_ids))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT parent_id, text FROM parent_section "  # noqa: S608 - placeholders only
            f"WHERE fingerprint=? AND parent_id IN ({placeholders})",
            (fingerprint, *parent_ids),
        ).fetchall()
    return {row["parent_id"]: row["text"] for row in rows}


def drop_document_parents(fingerprint: str, document_ids: Sequence[str]) -> None:
    if not document_ids:
        return
    with connect() as conn:
        conn.executemany(
            "DELETE FROM parent_section WHERE fingerprint=? AND document_id=?",
            [(fingerprint, doc_id) for doc_id in document_ids],
        )


def cached_vectors(model: str, hashes: Sequence[str]) -> dict[str, list[float]]:
    if not hashes:
        return {}
    found: dict[str, list[float]] = {}
    with connect() as conn:
        # SQLite caps host parameters, so page through large batches.
        for start in range(0, len(hashes), 500):
            window = hashes[start : start + 500]
            placeholders = ",".join("?" * len(window))
            rows = conn.execute(
                f"SELECT text_hash, vector FROM embedding_cache "  # noqa: S608 - placeholders only
                f"WHERE model=? AND text_hash IN ({placeholders})",
                (model, *window),
            ).fetchall()
            found.update({row["text_hash"]: unpack_vector(row["vector"]) for row in rows})
    return found


def store_vectors(model: str, vectors: dict[str, Sequence[float]]) -> None:
    if not vectors:
        return
    with connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO embedding_cache (model, text_hash, vector) VALUES (?, ?, ?)",
            [(model, h, pack_vector(v)) for h, v in vectors.items()],
        )


def record_eval(fingerprint: str, dataset: str, metrics: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO eval_run (fingerprint, dataset, created_at, metrics_json) VALUES (?,?,?,?)",
            (fingerprint, dataset, time.time(), json.dumps(metrics, sort_keys=True)),
        )


def latest_runs(limit: int = 20) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT r.*, v.embedding_model, v.strategy FROM ingest_run r "
            "LEFT JOIN variant v ON v.fingerprint = r.fingerprint "
            "ORDER BY r.started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
