"""Ingest: sources -> chunks -> embeddings -> Chroma, per variant.

Each source's git sha feeds into `variant.fingerprint`, so a sha or config
change resolves to a brand-new, empty collection rather than an existing one
that needs patching. That makes ingest a single decision -- build this exact
variant from scratch, or skip because it's already there -- with no
per-source diffing to get right.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from loguru import logger

from tauri_assistant.ingest.chunking import Pipeline, build_chunker, get_token_counter
from tauri_assistant.ingest.embedding import Embedder
from tauri_assistant.ingest.types import Chunk, Document
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository import RunStats, get_repository
from tauri_assistant.sources import get_sources

WRITE_BATCH = 256


@dataclass
class IngestReport:
    variant: Variant
    stats: RunStats = field(default_factory=RunStats)
    token_counts: list[int] = field(default_factory=list)

    def token_stats(self) -> dict[str, float]:
        if not self.token_counts:
            return {}
        ordered = sorted(self.token_counts)
        pick = lambda q: ordered[min(int(len(ordered) * q), len(ordered) - 1)]  # noqa: E731
        return {
            "count": len(ordered),
            "total": sum(ordered),
            "p50": pick(0.50),
            "p90": pick(0.90),
            "p95": pick(0.95),
            "max": ordered[-1],
        }


def dedupe_document_ids(documents: Iterable[Document]) -> list[Document]:
    """Guarantee unique document ids.

    Source parsers work from regexes over Rust and TypeScript, and a few
    genuinely ambiguous cases survive -- `cfg`-gated duplicates of the same
    function, for instance. Uniqueness is enforced here rather than chased in
    every parser: two documents sharing one id would collide when their
    chunks are written, since chunks are looked up by `document_id`.

    A colliding document whose text is byte-identical to one already kept
    under that id is dropped rather than disambiguated: `Chunk.id` hashes
    only breadcrumb + text, not document id, so suffixing the id would still
    yield a second chunk with the exact same content-addressed id -- which
    Chroma's `upsert` rejects as a duplicate within one call. This is common
    for `cfg`-gated items whose doc comment and signature don't actually
    differ across platforms.
    """
    kept_texts: dict[str, list[str]] = {}
    out: list[Document] = []
    duplicates = 0
    collisions = 0
    for doc in documents:
        texts = kept_texts.setdefault(doc.id, [])
        if doc.text in texts:
            duplicates += 1
            continue
        if texts:
            collisions += 1
            doc = Document(
                id=f"{doc.id}#{len(texts) + 1}",
                text=doc.text,
                breadcrumb=doc.breadcrumb,
                metadata=doc.metadata,
            )
        texts.append(doc.text)
        out.append(doc)
    if duplicates:
        logger.debug(f"Dropped {duplicates} byte-identical duplicate document(s)")
    if collisions:
        logger.debug(f"Disambiguated {collisions} colliding document id(s)")
    return out


def chunk_documents(
    documents: Sequence[Document], chunker: Pipeline | None = None
) -> tuple[list[Chunk], dict[str, tuple[str, str]]]:
    chunker = chunker or build_chunker()
    chunks: list[Chunk] = []
    parents: dict[str, tuple[str, str]] = {}
    for doc in documents:
        result = chunker.process(doc)
        chunks.extend(result.chunks)
        for parent_id, text in result.parents.items():
            parents[parent_id] = (doc.id, text)
    return chunks, parents


def ingest(
    source_names: list[str],
    variant: Variant | None = None,
    force: bool = False,
) -> IngestReport:
    db = get_repository()
    counter = get_token_counter()
    chunker = build_chunker(counter=counter)

    sources = get_sources(source_names)
    current_shas = {s.name: s.git_sha for s in sources}
    variant = variant or Variant.from_settings(current_shas)
    report = IngestReport(variant=variant)

    logger.info(f"Variant {variant.describe()} -> {variant.collection_name}")

    store = db.embedding(variant)
    if not force and store.exists():
        logger.info(f"{variant.collection_name} already built at this sha/config; skipping")
        return report

    db.variant.register(variant)
    run_id = db.ingest_run.start(variant.fingerprint, repo_shas=current_shas)

    embedder = Embedder(variant.embedding_model)
    docs_total = 0
    written = 0
    elapsed = 0.0

    for source in sources:
        documents = dedupe_document_ids(source.iter_documents())
        docs_total += len(documents)
        logger.info(f"{source.name}: {len(documents)} documents")

        if not documents:
            continue

        chunks, parents = chunk_documents(documents, chunker)
        db.parent_section.save(variant.fingerprint, parents)
        report.token_counts.extend(int(c.metadata.get("token_count", 0)) for c in chunks)

        oversized = [c for c in chunks if c.metadata.get("token_count", 0) > counter.budget]
        if oversized:
            # The post-processors are supposed to make this impossible; if it
            # happens, the embedding model would silently truncate instead.
            raise RuntimeError(
                f"{len(oversized)} chunk(s) exceed the {counter.budget}-token budget, "
                f"largest {max(c.metadata['token_count'] for c in oversized)}"
            )

        for start in range(0, len(chunks), WRITE_BATCH):
            batch = chunks[start : start + WRITE_BATCH]
            began = time.perf_counter()
            vectors = embedder.embed_documents([c.text for c in batch])
            elapsed += time.perf_counter() - began
            written += store.upsert_chunks(batch, vectors)
            logger.info(f"  embedded {min(start + WRITE_BATCH, len(chunks))}/{len(chunks)} chunks")

    report.stats = RunStats(
        docs_total=docs_total,
        sources_total=len(sources),
        chunks_written=written,
        embed_seconds=round(elapsed, 2),
    )
    db.ingest_run.finish(run_id, report.stats, report.token_stats())
    logger.info(f"Done: {written} chunks written, {elapsed:.1f}s embedding")
    return report
