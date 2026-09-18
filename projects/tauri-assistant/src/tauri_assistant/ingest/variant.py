"""Variant identity: the fingerprint that decides which collection we write to.

The index content is a pure function of (corpus, chunking config, embedding
config). Hashing those inputs means:

- changing the chunker or embedding model lands in a *different* collection,
  so two experiments can never contaminate each other;
- a source's git sha moving lands in a *different* collection too, so a repo
  update is a fresh build rather than a patch to one that's already live;
- leaving everything alone resolves to the *same* collection, so re-running
  ingest against an unchanged corpus and config is a cheap no-op;
- every measurement can be keyed back to the exact config and corpus state
  that produced it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tauri_assistant.settings import ChunkingSettings, Settings, settings

_FINGERPRINT_LEN = 10

# Chroma requires 3-512 chars of [a-zA-Z0-9._-], starting and ending
# alphanumeric. Model ids like "BAAI/bge-m3" violate that.
_ILLEGAL = re.compile(r"[^a-zA-Z0-9._-]+")


def slug(value: str) -> str:
    return _ILLEGAL.sub("-", value).strip("-._") or "x"


@dataclass(frozen=True)
class Variant:
    """Everything that changes the stored vectors -- and nothing that doesn't.

    Batch size, device and log level are deliberately absent: including them
    would orphan a perfectly good index every time an unrelated knob moved.
    """

    embedding_model: str
    chunking: Mapping[str, Any]
    sources: Mapping[str, Any]
    source_shas: Mapping[str, str]
    """`source name -> git sha`, as of this build. Part of the fingerprint: a
    source moving to a new sha is a corpus change, not something to patch a
    live collection in place for."""

    @classmethod
    def from_settings(cls, source_shas: Mapping[str, str], cfg: Settings | None = None) -> Variant:
        cfg = cfg or settings
        return cls(
            embedding_model=cfg.embedding.model,
            chunking={
                "strategy": cfg.chunking.strategy,
                "max_tokens": cfg.chunking.max_tokens,
                "min_tokens": cfg.chunking.min_tokens,
                "overlap_tokens": cfg.chunking.overlap_tokens,
            },
            sources={
                "include_translations": cfg.chunking.include_translations,
                "exclude_globs": sorted(cfg.chunking.exclude_globs),
            },
            source_shas=dict(sorted(source_shas.items())),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Variant:
        """Reconstruct a past variant from its stored `as_dict()`, e.g. to drop its collection."""
        return cls(
            embedding_model=data["embedding_model"],
            chunking=data["chunking"],
            sources=data["sources"],
            source_shas=data["source_shas"],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "embedding_model": self.embedding_model,
            "chunking": dict(self.chunking),
            "sources": dict(self.sources),
            "source_shas": dict(self.source_shas),
        }

    def chunking_settings(self) -> ChunkingSettings:
        """Reconstruct the `ChunkingSettings` this variant was built with.
        Pass this (and `self.embedding_model`) into `get_token_counter` /
        `build_chunker` / `Source.iter_documents` instead of the
        process-global `settings.chunking` -- otherwise `ingest()` would
        chunk every variant identically regardless of what it was asked to
        build.

        Falls back to `ChunkingSettings`'s own field defaults for any key a
        hand-built `Variant` (tests, or an older stored `config_json`)
        doesn't carry, rather than raising -- `as_dict()`/`fingerprint`
        already tolerate a partial `chunking`/`sources` mapping, so this
        should too."""
        defaults = ChunkingSettings()
        return ChunkingSettings(
            strategy=self.chunking.get("strategy", defaults.strategy),
            max_tokens=self.chunking.get("max_tokens", defaults.max_tokens),
            min_tokens=self.chunking.get("min_tokens", defaults.min_tokens),
            overlap_tokens=self.chunking.get("overlap_tokens", defaults.overlap_tokens),
            include_translations=self.sources.get("include_translations", defaults.include_translations),
            exclude_globs=list(self.sources.get("exclude_globs", defaults.exclude_globs)),
        )

    @property
    def fingerprint(self) -> str:
        # sort_keys makes the hash independent of dict insertion order.
        canonical = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:_FINGERPRINT_LEN]

    @property
    def collection_name(self) -> str:
        strategy = slug(str(self.chunking.get("strategy", "unknown")))
        name = f"tauri-{slug(self.embedding_model)}-{strategy}-{self.fingerprint}"
        if len(name) > 512:
            # The fingerprint alone still disambiguates; trim the readable part.
            name = f"{name[: 512 - _FINGERPRINT_LEN - 1]}-{self.fingerprint}"
        return name

    def describe(self) -> str:
        return f"{self.embedding_model} / {self.chunking.get('strategy')} ({self.fingerprint})"
