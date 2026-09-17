"""Chroma metadata rules, which reject more than the docs suggest."""

from __future__ import annotations

import chromadb
import pytest

from tauri_assistant.ingest.types import Chunk
from tauri_assistant.repository.chroma_sqlite import _to_metadata as to_metadata


def chunk(**overrides) -> Chunk:
    base = {
        "document_id": "src:page.md",
        "text": "body",
        "breadcrumb": ("Docs", "Page", "Section"),
        "metadata": {"source": "src", "path": "page.md", "kind": "guide", "doc_hash": "abc"},
    }
    return Chunk(**(base | overrides))


def test_parent_id_is_omitted_when_absent():
    """chromadb raises TypeError on a None metadata value rather than storing null.

    Every top-level chunk has `parent_id=None`, so writing the key through
    would fail the entire batch.
    """
    assert "parent_id" not in to_metadata(chunk(parent_id=None))


def test_parent_id_is_written_when_present():
    assert to_metadata(chunk(parent_id="p1"))["parent_id"] == "p1"


def test_no_metadata_value_is_ever_none():
    metadata = to_metadata(chunk(parent_id=None, metadata={"source": "s"}))
    assert all(value is not None for value in metadata.values())


def test_breadcrumb_is_flattened_to_a_string():
    # Tuples are not valid metadata, and a string stays filterable.
    assert to_metadata(chunk())["heading_path"] == "Docs > Page > Section"


def test_metadata_is_accepted_by_chroma():
    """The real assertion: chromadb takes what we produce."""
    client = chromadb.EphemeralClient()
    collection = client.create_collection("md_test", metadata={"hnsw:space": "cosine"})
    entries = [chunk(parent_id=None), chunk(parent_id="p1", text="other")]
    collection.add(
        ids=[c.id for c in entries],
        documents=[c.text for c in entries],
        embeddings=[[0.1, 0.2, 0.3]] * len(entries),
        metadatas=[to_metadata(c) for c in entries],
    )
    assert collection.count() == 2


def test_none_metadata_would_indeed_fail():
    """Guards the reason the omission above exists."""
    client = chromadb.EphemeralClient()
    collection = client.create_collection("none_test")
    with pytest.raises((TypeError, ValueError)):
        collection.add(ids=["a"], documents=["x"], embeddings=[[0.1, 0.2, 0.3]], metadatas=[{"k": None}])
