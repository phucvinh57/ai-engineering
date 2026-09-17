"""Ingest against a real Chroma collection in a temp directory.

These are the tests worth having end-to-end rather than mocked: the whole
point of the design is that an unchanged source's git sha skips it entirely,
a changed source is fully rebuilt with no orphans left behind, and neither
property is visible from unit tests of the parts.
"""

from __future__ import annotations

import pytest

from tauri_assistant import db
from tauri_assistant.ingest import catalog, pipeline
from tauri_assistant.ingest.types import Document
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.settings import settings


class FakeEmbedder:
    """Deterministic vectors, so no model is ever loaded."""

    def __init__(self, model_name=None, use_cache=True) -> None:
        self.model_name = model_name or "fake"
        self.hits = 0
        self.misses = 0
        self.calls = 0

    def embed_documents(self, texts):
        self.calls += len(texts)
        self.misses += len(texts)
        return [[float(len(t) % 7), 0.5, 0.25] for t in texts]

    def embed_query(self, text):
        return [float(len(text) % 7), 0.5, 0.25]


class FakeSource:
    name = "fake"
    repo = "fake"
    strategy = "heading"
    documents: list[Document] = []
    git_sha = "sha-1"

    def iter_documents(self):
        yield from self.documents


def make_doc(doc_id: str, body: str) -> Document:
    return Document(
        id=f"fake:{doc_id}",
        text=f"## {doc_id}\n\n{body}",
        breadcrumb=("Fake", doc_id),
        metadata={"source": "fake", "path": f"{doc_id}.md", "kind": "test"},
    )


def document_ids(variant: Variant) -> set[str]:
    metadatas = db.get_collection(variant).get(include=["metadatas"])["metadatas"]
    return {m["document_id"] for m in metadatas}


@pytest.fixture
def isolated(tmp_path, monkeypatch, counter):
    monkeypatch.setattr(settings.paths, "data_dir", tmp_path)
    monkeypatch.setattr(pipeline, "get_token_counter", lambda *a, **k: counter)
    monkeypatch.setattr(pipeline, "CachedEmbedder", FakeEmbedder)
    monkeypatch.setitem(
        __import__("tauri_assistant.sources", fromlist=["SOURCES"]).SOURCES, "fake", FakeSource
    )
    db.get_client.cache_clear()
    FakeSource.documents = []
    FakeSource.git_sha = "sha-1"
    yield tmp_path
    db.get_client.cache_clear()


@pytest.fixture
def variant() -> Variant:
    return Variant(
        embedding_model="fake",
        chunking={"strategy": "heading", "max_tokens": 50, "min_tokens": 0},
        sources={},
    )


def run(variant, **kwargs):
    return pipeline.ingest(sources=["fake"], variant=variant, **kwargs)


class TestSourceVersioning:
    def test_first_run_reindexes_the_source(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        report = run(variant)
        assert report.stats.sources_reindexed == 1
        assert report.stats.docs_total == 2
        assert report.stats.chunks_written > 0

    def test_unchanged_git_sha_skips_the_source_entirely(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        run(variant)
        report = run(variant)
        assert report.stats.sources_reindexed == 0
        assert report.stats.docs_total == 0
        assert report.stats.chunks_written == 0
        assert document_ids(variant) == {"fake:a", "fake:b"}

    def test_a_new_git_sha_reindexes_the_whole_source(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        run(variant)
        FakeSource.documents = [make_doc("a", "alpha EDITED"), make_doc("b", "beta")]
        FakeSource.git_sha = "sha-2"
        report = run(variant)
        assert report.stats.sources_reindexed == 1
        assert report.stats.docs_total == 2

    def test_editing_leaves_no_orphan_chunks(self, isolated, variant):
        """Re-chunking can yield fewer chunks; content-addressed ids mean an
        upsert alone would leave the extras answering queries forever."""
        big = make_doc("a", " ".join(f"word{i}" for i in range(200)))
        FakeSource.documents = [big]
        run(variant)
        many = db.collection_stats(variant).chunks
        assert many > 1, "the fixture must actually split, or this proves nothing"

        FakeSource.documents = [make_doc("a", "short")]
        FakeSource.git_sha = "sha-2"
        run(variant)

        expected = len(pipeline.chunk_documents(FakeSource.documents)[0])
        stats = db.collection_stats(variant)
        assert stats.chunks == expected < many, "stale chunks were left behind"

    def test_removed_documents_disappear_on_the_next_git_sha(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        run(variant)
        FakeSource.documents = [make_doc("a", "alpha")]
        FakeSource.git_sha = "sha-2"
        run(variant)
        assert document_ids(variant) == {"fake:a"}

    def test_full_rebuild_reindexes_even_an_unchanged_sha(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha")]
        run(variant)
        report = run(variant, full=True)
        assert report.stats.sources_reindexed == 1


class TestVariantIsolation:
    def test_two_variants_do_not_share_a_collection(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha beta gamma delta")]
        run(variant)
        other = Variant(
            embedding_model="fake",
            chunking={"strategy": "whole", "max_tokens": 50, "min_tokens": 0},
            sources={},
        )
        run(other)

        assert variant.collection_name != other.collection_name
        assert db.collection_stats(variant).chunks > 0
        assert db.collection_stats(other).chunks > 0

    def test_ingesting_one_variant_leaves_the_other_untouched(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        run(variant)
        before = db.collection_stats(variant).chunks

        other = Variant(
            embedding_model="fake",
            chunking={"strategy": "whole", "max_tokens": 50, "min_tokens": 0},
            sources={},
        )
        FakeSource.documents = [make_doc("a", "totally different")]
        run(other)

        assert db.collection_stats(variant).chunks == before


class TestCatalog:
    def test_parents_round_trip(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha beta")]
        run(variant)
        collection = db.get_collection(variant)
        metadatas = collection.get(include=["metadatas"])["metadatas"]
        parent_ids = [m["parent_id"] for m in metadatas if m.get("parent_id")]
        parents = catalog.get_parents(variant.fingerprint, parent_ids)
        assert parents, "small-to-big expansion needs the parent text stored"

    def test_run_is_recorded(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha")]
        run(variant)
        rows = catalog.latest_runs(5)
        assert rows and rows[0]["status"] == "ok"

    def test_source_sha_is_recorded_after_a_successful_reindex(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha")]
        run(variant)
        assert catalog.get_source_shas(variant.fingerprint) == {"fake": "sha-1"}

    def test_embedding_cache_round_trips(self, isolated):
        catalog.store_vectors("m", {"h": [0.5, 0.25]})
        assert catalog.cached_vectors("m", ["h"])["h"] == pytest.approx([0.5, 0.25])

    def test_cache_is_keyed_by_model(self, isolated):
        catalog.store_vectors("m1", {"h": [0.5]})
        assert catalog.cached_vectors("m2", ["h"]) == {}
