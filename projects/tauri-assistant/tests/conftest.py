from __future__ import annotations

import pytest

from tauri_assistant.ingest.types import Document


class FakeCounter:
    """Word-count stand-in, so tests never load a model.

    Real token counts are model-specific; these tests are about *boundaries*,
    not sizes, so a deterministic counter keeps them fast and stable.
    """

    def __init__(self, budget: int = 50) -> None:
        self._budget = budget

    def count(self, text: str) -> int:
        return len(text.split())

    @property
    def budget(self) -> int:
        return self._budget


@pytest.fixture
def counter() -> FakeCounter:
    return FakeCounter()


@pytest.fixture
def document() -> Document:
    return Document(
        id="test:doc",
        text="intro\n\n## Alpha\n\nalpha body\n\n## Beta\n\nbeta body",
        breadcrumb=("Docs", "Test"),
        metadata={"source": "test", "path": "doc.md"},
    )
