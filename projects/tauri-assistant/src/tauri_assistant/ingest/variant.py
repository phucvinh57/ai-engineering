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

from tauri_assistant.settings import Settings, settings

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

    def as_dict(self) -> dict[str, Any]:
        return {
            "embedding_model": self.embedding_model,
            "chunking": dict(self.chunking),
            "sources": dict(self.sources),
            "source_shas": dict(self.source_shas),
        }

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
