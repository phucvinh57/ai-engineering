"""Plugin permissions, read from TOML rather than the rendered docs.

Each entry -- a permission, a set, or a plugin's default -- is already one
self-contained answer to "what does this let my app do", so these arrive as
atomic records and use the `record` strategy. The identifier is what users
actually paste into a capability file, so it leads the rendered text.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from loguru import logger

from tauri_assistant.ingest.types import Document
from tauri_assistant.sources.base import Source

PLUGINS_ROOT = "plugins"
SITE = "https://v2.tauri.app/plugin"


def _render_scope(scope: dict) -> list[str]:
    lines: list[str] = []
    for verb in ("allow", "deny"):
        entries = scope.get(verb) or []
        paths = [e.get("path", str(e)) if isinstance(e, dict) else str(e) for e in entries]
        if paths:
            lines.append(f"Scope {verb}: {', '.join(paths)}")
    return lines


def _render_permission(plugin: str, entry: dict) -> tuple[str, str]:
    identifier = entry.get("identifier", "")
    lines = [f"# {plugin}:{identifier}" if identifier else f"# {plugin} permission"]

    if description := entry.get("description"):
        lines.append(description.strip())

    commands = entry.get("commands") or {}
    for verb in ("allow", "deny"):
        if names := commands.get(verb):
            lines.append(f"Commands {verb}ed: {', '.join(names)}")

    if scope := entry.get("scope"):
        lines.extend(_render_scope(scope))

    if platforms := entry.get("platforms"):
        lines.append(f"Platforms: {', '.join(platforms)}")

    return identifier, "\n\n".join(lines)


def _render_set(plugin: str, entry: dict) -> tuple[str, str]:
    identifier = entry.get("identifier", "")
    lines = [f"# {plugin}:{identifier} (permission set)"]
    if description := entry.get("description"):
        lines.append(description.strip())
    if permissions := entry.get("permissions"):
        lines.append(f"This set includes: {', '.join(permissions)}")
    return identifier, "\n\n".join(lines)


def _render_default(plugin: str, entry: dict) -> tuple[str, str]:
    lines = [f"# {plugin}: default permission set"]
    if description := entry.get("description"):
        lines.append(description.strip())
    if permissions := entry.get("permissions"):
        lines.append(f"The default set includes: {', '.join(permissions)}")
    return "default", "\n\n".join(lines)


class PluginPermissionsSource(Source):
    name = "plugin-permissions"
    repo = "plugins-workspace"
    strategy = "record"

    def iter_documents(self) -> Iterator[Document]:
        root = self.path / PLUGINS_ROOT
        if not root.is_dir():
            logger.warning(f"{root} missing -- run `tauri-assistant sync` first")
            return

        # Walk through <repo>/plugins/*
        for plugin_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            yield from self._plugin_documents(plugin_dir)

    def _plugin_documents(self, plugin_dir: Path) -> Iterator[Document]:
        plugin = plugin_dir.name
        permissions_dir = plugin_dir / "permissions"
        if not permissions_dir.is_dir():
            return

        # Recursively iterate toml files
        for path in sorted(permissions_dir.rglob("*.toml")):
            if "schemas" in path.parts:
                continue

            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as exc:
                logger.warning(f"Skipping malformed {path}: {exc}")
                continue

            parts = path.relative_to(permissions_dir).parts
            if "commands" in parts:
                # One generated file per command, holding only its
                # allow/deny pair. Split per entry they would be hundreds of
                # near-identical two-line chunks differing by one word; kept
                # together they answer "what permission do I need to call
                # read_file" in a single retrievable record.
                if document := self._command_document(plugin, path, data):
                    yield document
                continue

            for kind, entries, render in (
                ("permission", data.get("permission") or [], _render_permission),
                ("set", data.get("set") or [], _render_set),
            ):
                for entry in entries:
                    identifier, text = render(plugin, entry)
                    if identifier:
                        yield self._document(plugin, path, identifier, text, kind)

            if default := data.get("default"):
                identifier, text = _render_default(plugin, default)
                yield self._document(plugin, path, identifier, text, "default")

    def _command_document(self, plugin: str, path: Path, data: dict) -> Document | None:
        entries = data.get("permission") or []
        if not entries:
            return None

        command = path.stem
        lines = [f"# {plugin} command: {command}"]
        for entry in entries:
            identifier = entry.get("identifier", "")
            description = (entry.get("description") or "").strip()
            lines.append(f"`{plugin}:{identifier}` -- {description}")

        return self._document(plugin, path, f"command-{command}", "\n\n".join(lines), "command")

    def _document(self, plugin: str, path: Path, identifier: str, text: str, kind: str) -> Document:
        return Document(
            id=f"{self.name}:{plugin}/{identifier}",
            text=text,
            breadcrumb=("Tauri Plugins", plugin, "Permissions", identifier),
            metadata={
                "source": self.name,
                "repo": self.repo,
                "path": self.relative_path(path),
                "url": f"{SITE}/{plugin}/#permissions",
                "kind": f"permission-{kind}",
                "plugin": plugin,
            },
        )
