"""Query condensation + Chroma retrieval + context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from tauri_assistant.config import Settings
from tauri_assistant.ingest.embedder import embed_query
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.rag.prompts import CONDENSE_QUERY_PROMPT, build_context_block


@dataclass
class RetrievedChunk:
    text: str
    heading_path: str
    url: str
    source: str
    score: float


def condense_query(history: list[dict[str, str]], question: str, settings: Settings, client: OpenAI) -> str:
    if not history:
        return question

    transcript = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    prompt = CONDENSE_QUERY_PROMPT.format(history=transcript, question=question)
    resp = client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return (resp.choices[0].message.content or question).strip()


def retrieve(
    query: str,
    settings: Settings,
    store: ChromaStore,
    top_k: int | None = None,
    where: dict[str, Any] | None = None,
) -> list[RetrievedChunk]:
    embedding = embed_query(query, settings)
    results = store.query(embedding, top_k=top_k or settings.retrieval_top_k, where=where)

    seen_hashes: set[str] = set()
    chunks: list[RetrievedChunk] = []
    for row in results:
        text = row["text"]
        if text in seen_hashes:
            continue
        seen_hashes.add(text)
        meta = row["metadata"]
        chunks.append(
            RetrievedChunk(
                text=text,
                heading_path=meta.get("heading_path", ""),
                url=meta.get("url", ""),
                source=meta.get("source", ""),
                score=1 - row["distance"],
            )
        )
    return chunks


def assemble_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        build_context_block(i + 1, chunk.heading_path, chunk.text) for i, chunk in enumerate(chunks)
    )
