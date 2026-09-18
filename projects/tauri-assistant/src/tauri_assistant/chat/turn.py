"""One shared turn-preparation step for both the live `/chat` route and the
offline eval runner.

Before this module existed, the live path assembled its prompt inline in
`api/routes.py` and an eval runner would have had to reimplement that
assembly to score anything -- and would have silently drifted from it the
next time the route changed. `prepare_turn()` is now the single place that
turns `(messages, variant)` into a system prompt and a retrieval record, so
both paths exercise byte-identical prompts.
"""

from __future__ import annotations

from dataclasses import dataclass

from tauri_assistant.chat.prompts import build_system_prompt
from tauri_assistant.chat.retrieval import Passage, RetrievalTiming, retrieve_with_timing
from tauri_assistant.ingest.variant import Variant


@dataclass(frozen=True, slots=True)
class PreparedTurn:
    passages: list[Passage]
    system_prompt: str
    chat_messages: list[dict[str, str]]
    timing: RetrievalTiming


def prepare_turn(
    messages: list[dict[str, str]],
    k: int = 6,
    variant: Variant | None = None,
) -> PreparedTurn:
    """`messages` is prior turns plus the final user turn, oldest first
    (same shape `ChatRequest.messages` arrives in). Retrieval always keys off
    the *last* message, matching `api/routes.py`'s `chat()` handler."""
    query = messages[-1]["content"]
    passages, timing = retrieve_with_timing(query, k=k, variant=variant)
    system_prompt = build_system_prompt(passages)
    chat_messages = [{"role": "system", "content": system_prompt}, *messages]
    return PreparedTurn(
        passages=passages, system_prompt=system_prompt, chat_messages=chat_messages, timing=timing
    )
