"""Orchestrate sources -> chunks -> embed -> upsert."""

from __future__ import annotations

from dataclasses import dataclass

from tauri_assistant.config import Settings
from tauri_assistant.ingest.chunker import Chunk, chunk_js_symbol, chunk_markdown, chunk_permission
from tauri_assistant.ingest.embedder import embed_texts
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.sources import guide, js_api, permissions, repos, rust_api
from tauri_assistant.sources.js_api import JsApiSymbol
from tauri_assistant.sources.manifest import append_manifest_entries, make_entry
from tauri_assistant.sources.permissions import PluginPermission

JS_API_BLOB_BASE = "https://github.com/tauri-apps/tauri/blob/dev/packages/api/src"


@dataclass
class FetchResult:
    guide_pages: int
    js_api_symbols: int
    plugin_permissions: int
    rust_api_pages: int


def _all_js_symbols(settings: Settings) -> list[JsApiSymbol]:
    src_dir = settings.repos_dir / "tauri" / js_api.API_SRC_SUBDIR
    symbols: list[JsApiSymbol] = []
    for path in js_api.list_api_files(settings.repos_dir / "tauri"):
        symbols.extend(js_api.parse_api_file(path, src_dir))
    return symbols


def _all_permissions(settings: Settings) -> list[PluginPermission]:
    plugins_dir = settings.repos_dir / "plugins-workspace"
    records: list[PluginPermission] = []
    for plugin in permissions.list_plugins(plugins_dir):
        records.extend(permissions.parse_plugin_permissions(plugins_dir, plugin))
    return records


def run_fetch(settings: Settings, tier: int = 1) -> FetchResult:
    repos.sync_repos(settings, names=["tauri-docs", "tauri", "plugins-workspace"])

    guide_pages = guide.list_guide_pages(settings.repos_dir / "tauri-docs")
    js_symbols = _all_js_symbols(settings)
    plugin_permissions = _all_permissions(settings)

    manifest_entries = [make_entry("guide", p.rel_path, p.markdown) for p in guide_pages]
    manifest_entries += [make_entry("js-api", f"{s.module}.{s.name}", s.source) for s in js_symbols]
    manifest_entries += [
        make_entry("permissions", f"{p.plugin}/{p.identifier}", p.render_text()) for p in plugin_permissions
    ]

    rust_pages = []
    if tier >= 2:
        rust_dir = settings.raw_dir / "rust-api"
        rust_dir.mkdir(parents=True, exist_ok=True)
        rust_pages = rust_api.fetch_rust_api_pages()
        for page in rust_pages:
            (rust_dir / f"{page.item}.md").write_text(page.markdown)
            manifest_entries.append(make_entry("rust-api", page.item, page.markdown))

    append_manifest_entries(settings, manifest_entries)

    return FetchResult(
        guide_pages=len(guide_pages),
        js_api_symbols=len(js_symbols),
        plugin_permissions=len(plugin_permissions),
        rust_api_pages=len(rust_pages),
    )


def _guide_chunks(settings: Settings) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in guide.list_guide_pages(settings.repos_dir / "tauri-docs"):
        chunks.extend(chunk_markdown(page.title, page.url, "guide", page.markdown, settings))
    return chunks


def _js_api_chunks(settings: Settings) -> list[Chunk]:
    chunks: list[Chunk] = []
    for symbol in _all_js_symbols(settings):
        url = f"{JS_API_BLOB_BASE}/{symbol.module}.ts"
        chunks.extend(chunk_js_symbol(symbol, url, settings))
    return chunks


def _permission_chunks(settings: Settings) -> list[Chunk]:
    chunks: list[Chunk] = []
    for perm in _all_permissions(settings):
        chunks.extend(chunk_permission(perm, settings))
    return chunks


def _rust_api_chunks(settings: Settings) -> list[Chunk]:
    chunks: list[Chunk] = []
    rust_dir = settings.raw_dir / "rust-api"
    if not rust_dir.exists():
        return chunks
    for cache_path in sorted(rust_dir.glob("*.md")):
        item = cache_path.stem
        markdown = cache_path.read_text()
        url = rust_api.BASE_URL if item == "tauri" else rust_api.BASE_URL + item + ".html"
        chunks.extend(chunk_markdown("tauri crate docs", url, "rust-api", markdown, settings))
    return chunks


def run_ingest(settings: Settings, tier: int = 1) -> int:
    chunks = _guide_chunks(settings)
    chunks += _js_api_chunks(settings)
    chunks += _permission_chunks(settings)
    if tier >= 2:
        chunks += _rust_api_chunks(settings)

    if not chunks:
        return 0

    embeddings = embed_texts([c.text for c in chunks], settings)
    store = ChromaStore(settings)
    store.upsert(chunks, embeddings)
    return len(chunks)
