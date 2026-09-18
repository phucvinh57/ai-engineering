"""System prompt assembly for RAG chat."""

from __future__ import annotations

from tauri_assistant.chat.retrieval import Passage

SYSTEM_PREAMBLE = (
    "You are the Tauri assistant, an expert on the Tauri app framework. "
    "Answer only using the numbered context below, citing sources inline as "
    "[1], [2], etc. If the context doesn't answer the question, say so instead "
    "of guessing."
)


def _label(passage: Passage) -> str:
    return str(passage.metadata.get("heading_path") or passage.metadata.get("document_id", ""))


def build_system_prompt(passages: list[Passage]) -> str:
    if not passages:
        return SYSTEM_PREAMBLE
    blocks = [f"[{i}] {_label(p)}\n{p.text}" for i, p in enumerate(passages, start=1)]
    return f"{SYSTEM_PREAMBLE}\n\nContext:\n\n" + "\n\n---\n\n".join(blocks)
