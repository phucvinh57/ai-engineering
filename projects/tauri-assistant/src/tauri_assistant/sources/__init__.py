"""Source registry: name -> normalizer."""

from __future__ import annotations

from tauri_assistant.sources.base import Source
from tauri_assistant.sources.plugins_workspace import PluginPermissionsSource
from tauri_assistant.sources.tauri_docs import TauriDocsSource
from tauri_assistant.sources.tauri_js_api import TauriJsApiSource
from tauri_assistant.sources.tauri_rust import TauriRustSource

SOURCES: dict[str, type[Source]] = {
    TauriDocsSource.name: TauriDocsSource,
    PluginPermissionsSource.name: PluginPermissionsSource,
    TauriJsApiSource.name: TauriJsApiSource,
    TauriRustSource.name: TauriRustSource,
}


def get_sources(names: list[str]) -> list[Source]:
    return [SOURCES[n]() for n in names]


__all__ = ["SOURCES", "Source", "get_sources"]
