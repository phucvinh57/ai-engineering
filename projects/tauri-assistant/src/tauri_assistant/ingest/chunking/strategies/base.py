from abc import ABC, abstractmethod
from collections.abc import Iterable

from tauri_assistant.ingest.types import Chunk, Document


class Chunker(ABC):
    name: str

    @abstractmethod
    def split(self, doc: Document) -> Iterable[Chunk]: ...
