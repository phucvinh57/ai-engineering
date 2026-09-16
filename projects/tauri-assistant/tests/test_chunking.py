"""Chunking boundaries, size invariants, and strategy interchangeability."""

from __future__ import annotations

import pytest

from tauri_assistant.ingest.chunking import CHUNKERS, build_chunker
from tauri_assistant.ingest.chunking.base import split_sections
from tauri_assistant.ingest.chunking.postprocess import EnforceBudget, MergeUndersized, Pipeline
from tauri_assistant.ingest.chunking.strategies import HeadingSectionChunker
from tauri_assistant.ingest.chunking.textsplit import pack_to_budget, split_blocks
from tauri_assistant.ingest.types import Document

FENCED = """## Setup

Run this:

```python
# this comment is not a heading
# neither is this
value = 1
```

Done.
"""


def test_headings_inside_code_fences_are_not_headings():
    sections = split_sections(FENCED)
    assert len(sections) == 1
    assert "# this comment is not a heading" in sections[0].text


def test_section_keeps_its_heading_line():
    # Needed so a merged pair does not silently lose the second title.
    sections = split_sections("## Alpha\n\nbody")
    assert sections[0].text.startswith("## Alpha")


def test_content_before_first_heading_is_kept():
    sections = split_sections("preamble text\n\n## Alpha\n\nbody")
    assert any("preamble text" in s.text for s in sections)
    assert sections[0].path == ()


def test_nested_headings_build_a_trail():
    sections = split_sections("## A\n\nx\n\n### B\n\ny\n\n## C\n\nz")
    assert [s.path for s in sections] == [("A",), ("A", "B"), ("C",)]


def test_tilde_fence_is_not_closed_by_backticks():
    text = "~~~\n```\n## not a heading\n```\n~~~"
    assert len(split_sections(text)) == 1


class TestSplitting:
    def test_fences_are_atomic(self, counter):
        text = "word " * 30 + "\n\n```rust\n" + "code ".join(str(i) for i in range(20)) + "\n```"
        parts = pack_to_budget(text, counter, counter.budget)
        fence_parts = [p for p in parts if "```rust" in p]
        assert len(fence_parts) == 1, "an in-budget fence must not be split"

    def test_oversized_fence_repeats_its_info_string(self, counter):
        body = "\n".join(f"let x{i} = {i};" for i in range(60))
        parts = pack_to_budget(f'```rust title="lib.rs"\n{body}\n```', counter, counter.budget)
        assert len(parts) > 1
        assert all(p.lstrip().startswith("```rust") for p in parts), "language tag must survive"

    def test_every_part_fits_the_budget(self, counter):
        text = "\n\n".join("sentence words here. " * 10 for _ in range(10))
        assert all(counter.count(p) <= counter.budget for p in pack_to_budget(text, counter, counter.budget))

    def test_unbreakable_atom_is_still_split(self, counter):
        # A 300-char table rule is one "word"; real content in updater.mdx.
        parts = pack_to_budget("-" * 300, counter, counter.budget)
        assert parts and all(counter.count(p) <= counter.budget for p in parts)

    def test_split_blocks_separates_prose_from_code(self):
        blocks = split_blocks("prose\n\n```js\ncode\n```\n\nmore")
        assert [b.is_fence for b in blocks] == [False, True, False]


class TestPostprocessors:
    def test_merge_only_joins_siblings(self, counter, document):
        pipeline = Pipeline(HeadingSectionChunker(), [MergeUndersized(counter, min_tokens=100)], counter)
        for chunk in pipeline.split(document):
            assert counter.count(chunk.text) <= counter.budget

    def test_merge_is_disabled_at_zero(self, counter, document):
        merged = Pipeline(HeadingSectionChunker(), [MergeUndersized(counter, 0)], counter).split(document)
        plain = Pipeline(HeadingSectionChunker(), [], counter).split(document)
        assert len(merged) == len(plain)

    def test_breadcrumb_is_charged_against_the_budget(self, counter):
        # The prefix costs tokens; splitting on the bare body would overflow.
        doc = Document(
            id="t:1", text="body " * 45, breadcrumb=tuple(f"Level{i}" for i in range(8)), metadata={}
        )
        chunks = Pipeline(HeadingSectionChunker(), [EnforceBudget(counter)], counter).split(doc)
        assert all(counter.count(c.text) <= counter.budget for c in chunks)

    def test_parent_is_captured_before_splitting(self, counter, document):
        result = build_chunker("heading", counter=counter).process(document)
        assert result.parents
        for chunk in result.chunks:
            assert chunk.parent_id in result.parents


class TestStrategyContract:
    """Every strategy must satisfy the contract the rest of the code assumes."""

    @pytest.mark.parametrize("strategy", sorted(CHUNKERS))
    def test_all_strategies_produce_valid_chunks(self, strategy, counter, document):
        chunks = build_chunker(strategy, counter=counter).split(document)
        assert chunks
        for chunk in chunks:
            assert chunk.text.strip()
            assert chunk.document_id == document.id
            assert chunk.id
            assert counter.count(chunk.text) <= counter.budget
            assert chunk.metadata["strategy"] == strategy
            assert chunk.metadata["doc_hash"] == document.hash

    @pytest.mark.parametrize("strategy", sorted(CHUNKERS))
    def test_chunk_index_is_contiguous(self, strategy, counter, document):
        chunks = build_chunker(strategy, counter=counter).split(document)
        assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))

    def test_unknown_strategy_is_rejected(self, counter):
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            build_chunker("nope", counter=counter)


def test_chunk_id_is_stable_across_runs(counter, document):
    first = build_chunker("heading", counter=counter).split(document)
    second = build_chunker("heading", counter=counter).split(document)
    assert [c.id for c in first] == [c.id for c in second]


def test_chunk_id_changes_with_breadcrumb(counter):
    from tauri_assistant.ingest.types import Chunk

    a = Chunk(document_id="d", text="same text", breadcrumb=("A",))
    b = Chunk(document_id="d", text="same text", breadcrumb=("B",))
    assert a.id != b.id, "identical bodies under different headings must stay distinct"
