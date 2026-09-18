"""RAG chat: retrieve context from the current variant's collection, then
complete against the OpenAI-compatible endpoint in `settings.chat`.
"""

from __future__ import annotations

from tauri_assistant.chat.retrieval import NotIngestedError, Passage, retrieve

__all__ = ["NotIngestedError", "Passage", "retrieve"]
