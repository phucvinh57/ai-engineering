"""Parse each plugin's permission TOML files from a local clone of
plugins-workspace into structured records.

Each `permissions/*.toml` file defines one of: a `[[permission]]` (an
identifier with allowed/denied commands), a `[default]` table (the
permission set enabled unless a capability overrides it), or a `[[set]]`
(a named bundle of other permission identifiers). No HTML to scrape --
this is already structured data, same spirit as the old protocol_xml.py.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PLUGINS_SUBDIR = "plugins"
BLOB_BASE = "https://github.com/tauri-apps/plugins-workspace/blob/v2"


@dataclass
class PluginPermission:
    plugin: str
    identifier: str
    kind: str  # "permission" | "default" | "set"
    description: str
    url: str
    commands_allow: list[str] = field(default_factory=list)
    commands_deny: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)  # referenced identifiers, for default/set

    def render_text(self) -> str:
        parts = [f"Plugin: {self.plugin}", f"Permission: {self.identifier} ({self.kind})"]
        if self.description:
            parts.append(self.description)
        if self.commands_allow:
            parts.append("Allowed commands: " + ", ".join(self.commands_allow))
        if self.commands_deny:
            parts.append("Denied commands: " + ", ".join(self.commands_deny))
        if self.includes:
            parts.append("Includes permissions: " + ", ".join(self.includes))
        return "\n\n".join(parts)


def _parse_toml_file(path: Path, plugin: str, url: str) -> list[PluginPermission]:
    data = tomllib.loads(path.read_text())
    records: list[PluginPermission] = []

    for perm in data.get("permission", []):
        commands = perm.get("commands", {})
        records.append(
            PluginPermission(
                plugin=plugin,
                identifier=perm.get("identifier", path.stem),
                kind="permission",
                description=perm.get("description", ""),
                url=url,
                commands_allow=commands.get("allow", []),
                commands_deny=commands.get("deny", []),
            )
        )

    if "default" in data:
        default = data["default"]
        records.append(
            PluginPermission(
                plugin=plugin,
                identifier="default",
                kind="default",
                description=default.get("description", ""),
                url=url,
                includes=default.get("permissions", []),
            )
        )

    for perm_set in data.get("set", []):
        records.append(
            PluginPermission(
                plugin=plugin,
                identifier=perm_set.get("identifier", path.stem),
                kind="set",
                description=perm_set.get("description", ""),
                url=url,
                includes=perm_set.get("permissions", []),
            )
        )

    return records


def list_plugins(plugins_repo_dir: Path) -> list[str]:
    plugins_dir = plugins_repo_dir / PLUGINS_SUBDIR
    if not plugins_dir.exists():
        return []
    return sorted(p.name for p in plugins_dir.iterdir() if p.is_dir() and (p / "permissions").exists())


def parse_plugin_permissions(plugins_repo_dir: Path, plugin: str) -> list[PluginPermission]:
    plugin_dir = plugins_repo_dir / PLUGINS_SUBDIR / plugin
    perm_dir = plugin_dir / "permissions"

    records: list[PluginPermission] = []
    for toml_path in sorted(perm_dir.rglob("*.toml")):
        rel = toml_path.relative_to(plugin_dir)
        url = f"{BLOB_BASE}/plugins/{plugin}/{rel.as_posix()}"
        records.extend(_parse_toml_file(toml_path, plugin, url))
    return records
