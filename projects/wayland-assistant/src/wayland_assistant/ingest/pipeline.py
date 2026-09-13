"""Orchestrate sources -> chunks -> embed -> upsert."""

from __future__ import annotations

from dataclasses import dataclass

from wayland_assistant.config import Settings
from wayland_assistant.ingest.chunker import Chunk, chunk_interface, chunk_markdown
from wayland_assistant.ingest.embedder import embed_texts
from wayland_assistant.ingest.store import ChromaStore
from wayland_assistant.sources import repos
from wayland_assistant.sources.book import fetch_book_pages
from wayland_assistant.sources.doxygen import fetch_doxygen_pages
from wayland_assistant.sources.manifest import append_manifest_entries, make_entry
from wayland_assistant.sources.protocol_xml import parse_protocol_file


@dataclass
class FetchResult:
    protocol_files: int
    book_pages: int
    doxygen_pages: int


def run_fetch(settings: Settings, tier: int = 1) -> FetchResult:
    repos.sync_repos(settings)
    protocol_files = repos.list_protocol_files(settings, tier=tier)

    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    book_dir = settings.raw_dir / "book"
    book_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    for pf in protocol_files:
        docs = parse_protocol_file(pf, settings)
        for doc in docs:
            manifest_entries.append(
                make_entry("protocol", f"{doc.protocol_name}/{doc.interface_name}", doc.render_text())
            )

    book_pages = fetch_book_pages(tier=tier)
    for page in book_pages:
        (book_dir / f"{page.page}.md").write_text(page.markdown)
        manifest_entries.append(make_entry("book", page.page, page.markdown))

    doxygen_pages = []
    if tier >= 2:
        doxygen_dir = settings.raw_dir / "doxygen"
        doxygen_dir.mkdir(parents=True, exist_ok=True)
        doxygen_pages = fetch_doxygen_pages()
        for page in doxygen_pages:
            flat_name = page.header.replace("/", "__")
            (doxygen_dir / f"{flat_name}.md").write_text(page.markdown)
            manifest_entries.append(make_entry("doxygen", page.header, page.markdown))

    append_manifest_entries(settings, manifest_entries)

    return FetchResult(
        protocol_files=len(protocol_files),
        book_pages=len(book_pages),
        doxygen_pages=len(doxygen_pages),
    )


def _protocol_chunks(settings: Settings, tier: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for pf in repos.list_protocol_files(settings, tier=tier):
        for doc in parse_protocol_file(pf, settings):
            chunks.extend(chunk_interface(doc, settings))
    return chunks


def _book_chunks(settings: Settings, tier: int) -> list[Chunk]:
    from wayland_assistant.sources.book import PAGES

    chunks: list[Chunk] = []
    book_dir = settings.raw_dir / "book"
    for page, _title, page_tier in PAGES:
        if page_tier > tier:
            continue
        cache_path = book_dir / f"{page}.md"
        if not cache_path.exists():
            continue
        markdown = cache_path.read_text()
        url = f"https://wayland.freedesktop.org/docs/html/{page}"
        chunks.extend(chunk_markdown("Wayland Book", url, "book", markdown, settings))
    return chunks


def _doxygen_chunks(settings: Settings) -> list[Chunk]:
    from wayland_assistant.sources.doxygen import BASE_URL

    chunks: list[Chunk] = []
    doxygen_dir = settings.raw_dir / "doxygen"
    if not doxygen_dir.exists():
        return chunks
    for cache_path in sorted(doxygen_dir.glob("*.md")):
        header = cache_path.stem.replace("__", "/")
        markdown = cache_path.read_text()
        url = BASE_URL + header + ".html"
        chunks.extend(chunk_markdown("wlroots API docs", url, "doxygen", markdown, settings))
    return chunks


def run_ingest(settings: Settings, tier: int = 1) -> int:
    chunks = _protocol_chunks(settings, tier)
    chunks += _book_chunks(settings, tier)
    if tier >= 2:
        chunks += _doxygen_chunks(settings)

    if not chunks:
        return 0

    embeddings = embed_texts([c.text for c in chunks], settings)
    store = ChromaStore(settings)
    store.upsert(chunks, embeddings)
    return len(chunks)
