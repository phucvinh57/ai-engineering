"""The stable boundary between sources, chunking, and storage.

Sources produce `Document`s; chunkers turn each one into `Chunk`s; the store
writes `Chunk`s. Neither side names a chunking strategy, which is what lets a
strategy be swapped without touching anything around it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def content_hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")  # keep ("ab", "c") distinct from ("a", "bc")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class Document:
    """One normalized source unit: a docs page, a TS module, a Rust file."""

    id: str
    """Stable across runs, e.g. `tauri-docs:develop/calling-rust.mdx`."""

    text: str
    """Normalized markdown. MDX/JSX already stripped by the source."""

    breadcrumb: tuple[str, ...]
    """e.g. `("Tauri Docs", "Develop", "Calling Rust from the Frontend")`."""

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """`source`, `repo`, `path`, `url`, `kind`."""

    @property
    def hash(self) -> str:
        """Incremental-ingest key: unchanged hash means skip this document."""
        return content_hash(self.text)


@dataclass(frozen=True, slots=True)
class Chunk:
    """One embeddable unit."""

    document_id: str
    text: str
    breadcrumb: tuple[str, ...]
    parent_id: str | None = None
    """Set by `AttachParent` for small-to-big retrieval."""

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """`heading_path`, `chunk_index`, `token_count`, plus the document's own."""

    @property
    def id(self) -> str:
        """Content-addressed, so re-ingesting unchanged text is a no-op upsert.

        The breadcrumb is included so that two genuinely different sections
        that happen to share body text (common for short permission entries)
        stay distinct.
        """
        return content_hash(" > ".join(self.breadcrumb), self.text)

    @property
    def heading_path(self) -> str:
        return " > ".join(self.breadcrumb)
