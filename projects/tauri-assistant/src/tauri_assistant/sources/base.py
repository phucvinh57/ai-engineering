"""The `Source` base class: anything that yields normalized `Document`s."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from tauri_assistant.ingest.types import Document
from tauri_assistant.settings import settings


class Source(ABC):
    name: str
    repo: str
    strategy: str

    @abstractmethod
    def iter_documents(self) -> Iterator[Document]: ...

    @property
    def path(self) -> Path:
        return settings.paths.repos_dir / self.repo

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self.path).as_posix()
