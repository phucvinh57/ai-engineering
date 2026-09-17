"""Ingest against a real Chroma collection in a temp directory.

These are the tests worth having end-to-end rather than mocked: the whole
point of the design is that an unchanged (config, corpus-sha) variant is a
no-op, a changed one gets a fresh collection, and neither property is
visible from unit tests of the parts.
"""

from __future__ import annotations

import pytest

from tauri_assistant.ingest import pipeline
from tauri_assistant.ingest.types import Document
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository import get_repository
from tauri_assistant.settings import settings


class FakeEmbedder:
    """Deterministic vectors, so no model is ever loaded."""

    def __init__(self, model_name=None) -> None:
        self.model_name = model_name or "fake"
        self.calls = 0

    def embed_documents(self, texts):
        self.calls += len(texts)
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
    # Reaches past the interface into the concrete Chroma collection --
    # acceptable in a white-box test, never in application code.
    metadatas = get_repository()._collection(variant).get(include=["metadatas"])["metadatas"]
    return {m["document_id"] for m in metadatas}


@pytest.fixture
def isolated(tmp_path, monkeypatch, counter):
    monkeypatch.setattr(settings.paths, "data_dir", tmp_path)
    monkeypatch.setattr(pipeline, "get_token_counter", lambda *a, **k: counter)
    monkeypatch.setattr(pipeline, "Embedder", FakeEmbedder)
    monkeypatch.setattr(
        __import__("tauri_assistant.sources", fromlist=["SOURCES"]), "SOURCES", {"fake": FakeSource}
    )
    get_repository.cache_clear()
    FakeSource.documents = []
    FakeSource.git_sha = "sha-1"
    yield tmp_path
    get_repository.cache_clear()


@pytest.fixture
def variant() -> Variant:
    return Variant(
        embedding_model="fake",
        chunking={"strategy": "heading", "max_tokens": 50, "min_tokens": 0},
        sources={},
        source_shas={},
    )


def run(variant, **kwargs):
    return pipeline.ingest(variant=variant, **kwargs)


class TestVariantSkipping:
    def test_first_run_builds_the_collection(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        report = run(variant)
        assert report.stats.docs_total == 2
        assert report.stats.chunks_written > 0

    def test_rerunning_the_same_variant_is_a_no_op(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        run(variant)
        report = run(variant)
        assert report.stats.docs_total == 0
        assert report.stats.chunks_written == 0
        assert document_ids(variant) == {"fake:a", "fake:b"}

    def test_force_rebuilds_an_already_built_variant(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha")]
        run(variant)
        report = run(variant, force=True)
        assert report.stats.docs_total == 1
        assert report.stats.chunks_written > 0

    def test_a_new_source_sha_lands_in_a_different_collection(self, isolated):
        FakeSource.documents = [make_doc("a", "alpha")]
        first = pipeline.ingest()
        FakeSource.git_sha = "sha-2"
        second = pipeline.ingest()
        assert first.variant.collection_name != second.variant.collection_name
        assert document_ids(first.variant) == {"fake:a"}
        assert document_ids(second.variant) == {"fake:a"}


class TestVariantIsolation:
    def test_two_variants_do_not_share_a_collection(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha beta gamma delta")]
        run(variant)
        other = Variant(
            embedding_model="fake",
            chunking={"strategy": "whole", "max_tokens": 50, "min_tokens": 0},
            sources={},
            source_shas={},
        )
        run(other)

        assert variant.collection_name != other.collection_name
        assert get_repository().embedding(variant).stats().chunks > 0
        assert get_repository().embedding(other).stats().chunks > 0

    def test_ingesting_one_variant_leaves_the_other_untouched(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha"), make_doc("b", "beta")]
        run(variant)
        before = get_repository().embedding(variant).stats().chunks

        other = Variant(
            embedding_model="fake",
            chunking={"strategy": "whole", "max_tokens": 50, "min_tokens": 0},
            sources={},
            source_shas={},
        )
        FakeSource.documents = [make_doc("a", "totally different")]
        run(other)

        assert get_repository().embedding(variant).stats().chunks == before


class TestCatalog:
    def test_parents_round_trip(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha beta")]
        run(variant)
        collection = get_repository()._collection(variant)
        metadatas = collection.get(include=["metadatas"])["metadatas"]
        parent_ids = [m["parent_id"] for m in metadatas if m.get("parent_id")]
        parents = get_repository().parent_section.get(variant.fingerprint, parent_ids)
        assert parents, "small-to-big expansion needs the parent text stored"

    def test_run_is_recorded(self, isolated, variant):
        FakeSource.documents = [make_doc("a", "alpha")]
        run(variant)
        rows = get_repository().ingest_run.latest(5)
        assert rows and rows[0]["status"] == "ok"
