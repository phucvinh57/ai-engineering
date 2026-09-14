"""Track what's been fetched, so re-running `fetch` is incremental."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import NamedTuple

from tauri_assistant.config import Settings


class ManifestEntry(NamedTuple):
    source: str
    identifier: str
    content_hash: str
    fetched_at: str


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manifest(settings: Settings) -> dict[str, ManifestEntry]:
    if not settings.manifest_path.exists():
        return {}
    entries: dict[str, ManifestEntry] = {}
    with settings.manifest_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            entry = ManifestEntry(**row)
            entries[f"{entry.source}:{entry.identifier}"] = entry
    return entries


def append_manifest_entries(settings: Settings, entries: list[ManifestEntry]) -> None:
    settings.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.manifest_path.open("a") as f:
        for entry in entries:
            f.write(json.dumps(entry._asdict()) + "\n")


def make_entry(source: str, identifier: str, text: str) -> ManifestEntry:
    return ManifestEntry(
        source=source,
        identifier=identifier,
        content_hash=content_hash(text),
        fetched_at=datetime.now(UTC).isoformat(),
    )
