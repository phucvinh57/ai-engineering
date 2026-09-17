"""The `Source` base class: anything that yields normalized `Document`s."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from git import Repo

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

    @property
    def git_sha(self) -> str:
        """The version key for this source's whole corpus.

        A source is versioned as a unit, not document-by-document: when the
        repo moves, the source is fully re-chunked and re-embedded rather
        than diffed page by page.
        """
        return Repo(self.path).head.commit.hexsha

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self.path).as_posix()
