"""Query condensation + Chroma retrieval + context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from tauri_assistant import telemetry
from tauri_assistant.config import Settings
from tauri_assistant.ingest.embedder import embed_query
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.rag.prompts import CONDENSE_QUERY_PROMPT, build_context_block

# Chunk text is truncated to this length in retriever spans -- the full text
# is already visible on the generation's system message, and Langfuse
# silently drops oversized ingestion events (8 chunks x up to 800 tokens is
# well past that), which would otherwise look like traces randomly vanishing.
_SPAN_TEXT_PREVIEW_CHARS = 300


@dataclass
class RetrievedChunk:
    text: str
    heading_path: str
    url: str
    source: str
    score: float


def condense_query(
    history: list[dict[str, str]],
    question: str,
    settings: Settings,
    client: OpenAI,
    *,
    parent: Any = None,
) -> str:
    if not history:
        # No span here is deliberate: absence in the trace tree *is* the
        # "skipped" signal (the caller also records `condensed=False` on the
        # root span's metadata so it's filterable, not just visible).
        return question

    with telemetry.observe(
        parent, "condense_query", input={"history_turns": len(history), "question": question}
    ) as span:
        transcript = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
        prompt = CONDENSE_QUERY_PROMPT.format(history=transcript, question=question)
        resp = client.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            **telemetry.generation_kwargs(span, name="condense_query"),
        )
        standalone = (resp.choices[0].message.content or question).strip()
        span.update(output=standalone)
    return standalone


def retrieve(
    query: str,
    settings: Settings,
    store: ChromaStore,
    top_k: int | None = None,
    where: dict[str, Any] | None = None,
    *,
    parent: Any = None,
) -> list[RetrievedChunk]:
    resolved_top_k = top_k or settings.retrieval_top_k
    retrieve_input = {"query": query, "top_k": resolved_top_k, "where": where}
    with telemetry.observe(parent, "retrieve", as_type="retriever", input=retrieve_input) as span:
        with telemetry.observe(span, "embed_query", as_type="embedding", input={"text": query}) as embed_span:
            embedding = embed_query(query, settings)
            embed_span.update(metadata={"model": settings.embedding_model, "dim": len(embedding)})

        with telemetry.observe(
            span,
            "chroma.query",
            input={"collection": settings.chroma_collection, "top_k": resolved_top_k, "where": where},
        ) as chroma_span:
            results = store.query(embedding, top_k=resolved_top_k, where=where)
            chroma_span.update(
                output=[
                    {
                        "url": r["metadata"].get("url", ""),
                        "heading_path": r["metadata"].get("heading_path", ""),
                        "score": 1 - r["distance"],
                    }
                    for r in results
                ]
            )

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

        span.update(
            output=[
                {
                    "url": c.url,
                    "heading_path": c.heading_path,
                    "source": c.source,
                    "score": c.score,
                    "text": c.text[:_SPAN_TEXT_PREVIEW_CHARS],
                }
                for c in chunks
            ],
            metadata={"returned": len(chunks), "deduped": len(results) - len(chunks)},
        )
    return chunks


def assemble_context(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        build_context_block(i + 1, chunk.heading_path, chunk.text) for i, chunk in enumerate(chunks)
    )
