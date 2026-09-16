"""Post-processors that wrap *any* chunker.

This is what makes a strategy swap a one-line change. Size bounds, breadcrumb
prefixing and parent linkage are invariants the storage and retrieval layers
rely on; implementing them once here rather than inside each strategy means a
new strategy only has to decide *where* to cut, and automatically inherits
everything downstream expects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tauri_assistant.ingest.chunking.base import Chunker
from tauri_assistant.ingest.chunking.textsplit import pack_to_budget
from tauri_assistant.ingest.chunking.tokens import TokenCounter
from tauri_assistant.ingest.types import Chunk, Document


@dataclass
class ChunkResult:
    chunks: list[Chunk] = field(default_factory=list)
    parents: dict[str, str] = field(default_factory=dict)
    """`parent_id` -> full section text, for small-to-big expansion."""


class Postprocessor:
    def apply(self, doc: Document, result: ChunkResult) -> ChunkResult:
        raise NotImplementedError


class MergeUndersized(Postprocessor):
    """Fold stub chunks into the next sibling sharing a parent heading.

    27% of tauri-docs heading sections are under 50 words -- a heading plus a
    one-line pointer. Embedded alone they are nearly contentless and crowd out
    real answers. Merging is restricted to siblings so an unrelated section
    from elsewhere in the page never gets glued on.
    """

    def __init__(self, counter: TokenCounter, min_tokens: int) -> None:
        self._counter = counter
        self._min_tokens = min_tokens

    def apply(self, doc: Document, result: ChunkResult) -> ChunkResult:
        if self._min_tokens <= 0:
            return result

        merged: list[Chunk] = []
        for chunk in result.chunks:
            if not merged:
                merged.append(chunk)
                continue

            previous = merged[-1]
            undersized = self._counter.count(previous.text) < self._min_tokens
            siblings = previous.breadcrumb[:-1] == chunk.breadcrumb[:-1]
            combined = f"{previous.text}\n\n{chunk.text}"
            fits = self._counter.count(combined) <= self._counter.budget

            if undersized and siblings and fits:
                # Both headings survive inside the body, so the shared
                # ancestor trail is the honest label for the merged chunk.
                merged[-1] = Chunk(
                    document_id=previous.document_id,
                    text=combined,
                    breadcrumb=previous.breadcrumb[:-1] or previous.breadcrumb,
                    parent_id=previous.parent_id,
                    metadata=previous.metadata,
                )
            else:
                merged.append(chunk)

        result.chunks = merged
        return result


class AttachParent(Postprocessor):
    """Record each chunk as its own parent section, before any further cutting.

    Must run *before* `EnforceBudget`: the parent is the whole section, so its
    identity has to be captured while the chunk still holds the whole section.
    Parent text goes to the catalog rather than into chunk metadata, where it
    would be duplicated into every child and inflate the collection by roughly
    the size of the corpus again.
    """

    def apply(self, doc: Document, result: ChunkResult) -> ChunkResult:
        out: list[Chunk] = []
        for chunk in result.chunks:
            parent_id = chunk.parent_id or chunk.id
            result.parents[parent_id] = chunk.text
            out.append(
                Chunk(
                    document_id=chunk.document_id,
                    text=chunk.text,
                    breadcrumb=chunk.breadcrumb,
                    parent_id=parent_id,
                    metadata=chunk.metadata,
                )
            )
        result.chunks = out
        return result


class EnforceBudget(Postprocessor):
    """Prefix the breadcrumb and guarantee every chunk fits the model.

    Prefixing and splitting are one step because they interact: the breadcrumb
    costs tokens, so deciding the split against the bare body would let the
    prefixed result overrun the budget and be silently truncated at embed
    time. The trail is charged against the budget up front, and repeated on
    every part so each one still reads standalone.
    """

    def __init__(self, counter: TokenCounter, prefix_breadcrumb: bool = True) -> None:
        self._counter = counter
        self._prefix = prefix_breadcrumb

    def apply(self, doc: Document, result: ChunkResult) -> ChunkResult:
        out: list[Chunk] = []
        for chunk in result.chunks:
            trail = chunk.heading_path if self._prefix else ""
            reserve = self._counter.count(f"{trail}\n\n") if trail else 0
            if reserve > self._counter.budget // 2:
                # A deeply nested Rust path can cost more than the body is
                # worth; dropping it beats overflowing the model's limit.
                trail, reserve = "", 0
            body_budget = self._counter.budget - reserve

            parts = (
                [chunk.text]
                if self._counter.count(chunk.text) <= body_budget
                else pack_to_budget(chunk.text, self._counter, body_budget)
            )

            for offset, part in enumerate(parts):
                text = f"{trail}\n\n{part}" if trail else part
                metadata = dict(chunk.metadata)
                if len(parts) > 1:
                    metadata |= {"part": offset, "part_count": len(parts)}
                out.append(
                    Chunk(
                        document_id=chunk.document_id,
                        text=text,
                        breadcrumb=chunk.breadcrumb,
                        parent_id=chunk.parent_id,
                        metadata=metadata,
                    )
                )
        result.chunks = out
        return result


class Pipeline:
    """A chunker plus the post-processors every strategy shares."""

    def __init__(self, chunker: Chunker, steps: Sequence[Postprocessor], counter: TokenCounter) -> None:
        self._chunker = chunker
        self._steps = list(steps)
        self._counter = counter

    @property
    def name(self) -> str:
        return self._chunker.name

    def process(self, doc: Document) -> ChunkResult:
        result = ChunkResult(chunks=list(self._chunker.split(doc)))
        for step in self._steps:
            result = step.apply(doc, result)

        # chunk_index is assigned last so it numbers what is actually stored,
        # after merges and splits have changed the count.
        result.chunks = [
            Chunk(
                document_id=c.document_id,
                text=c.text,
                breadcrumb=c.breadcrumb,
                parent_id=c.parent_id,
                metadata={
                    **c.metadata,
                    "chunk_index": i,
                    "doc_hash": doc.hash,
                    "strategy": self._chunker.name,
                    "token_count": self._counter.count(c.text),
                },
            )
            for i, c in enumerate(result.chunks)
        ]
        return result

    def split(self, doc: Document) -> list[Chunk]:
        return self.process(doc).chunks
