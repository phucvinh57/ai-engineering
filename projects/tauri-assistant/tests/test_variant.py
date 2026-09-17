"""Variant fingerprinting: what must change the index, and what must not."""

from __future__ import annotations

import re

from tauri_assistant.ingest.variant import Variant, slug


def make(**overrides) -> Variant:
    base = {
        "embedding_model": "BAAI/bge-m3",
        "chunking": {"strategy": "heading", "max_tokens": 1024, "min_tokens": 64},
        "sources": {"include_translations": False, "exclude_globs": ["blog/**"]},
        "source_shas": {"tauri-docs": "abc123"},
    }
    return Variant(**(base | overrides))


def test_fingerprint_is_stable_across_key_order():
    a = make(chunking={"strategy": "heading", "max_tokens": 1024, "min_tokens": 64})
    b = make(chunking={"min_tokens": 64, "max_tokens": 1024, "strategy": "heading"})
    assert a.fingerprint == b.fingerprint


def test_changing_the_chunker_changes_the_collection():
    a, b = make(), make(chunking={"strategy": "fixed", "max_tokens": 1024, "min_tokens": 64})
    assert a.fingerprint != b.fingerprint
    assert a.collection_name != b.collection_name


def test_changing_the_embedding_model_changes_the_collection():
    # Not cosmetic: MiniLM is 384-dim and bge-m3 is 1024, so sharing a
    # collection would be rejected by Chroma outright.
    assert make().fingerprint != make(embedding_model="sentence-transformers/all-MiniLM-L6-v2").fingerprint


class TestCollectionName:
    """Chroma accepts only [a-zA-Z0-9._-], 3-512 chars, alphanumeric ends."""

    PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,510}[a-zA-Z0-9]$")

    def test_model_ids_with_slashes_are_slugged(self):
        # "BAAI/bge-m3" would be rejected verbatim.
        assert self.PATTERN.match(make().collection_name)

    def test_long_model_ids_stay_within_the_limit(self):
        name = make(embedding_model="x" * 900).collection_name
        assert len(name) <= 512
        assert self.PATTERN.match(name)

    def test_slug_never_returns_empty(self):
        assert slug("///") and slug("")

    def test_fingerprint_survives_slug_collisions(self):
        # Two model ids that slug identically must still not collide.
        a = make(embedding_model="org/model").collection_name
        b = make(embedding_model="org:model").collection_name
        assert a != b


def test_from_settings_round_trips(monkeypatch):
    variant = Variant.from_settings({"tauri-docs": "abc123"})
    assert variant.as_dict()["embedding_model"] == variant.embedding_model
    assert Variant(**variant.as_dict()).fingerprint == variant.fingerprint
