"""Generate and verify golden questions from the ingested corpus.

Three verification filters, applied in this order:

1. **Leakage** (deterministic, `has_leakage`) -- reject a question that
   shares a normalized 5-gram with its source chunk. Cheap, and it kills the
   dominant failure mode where the generator copies a rare identifier
   straight out of the text and every retriever trivially wins.
2. **Answerability** (LLM, `judge_answerability`) -- drop questions a Tauri
   expert could answer with no docs at all, and self-referential ones ("what
   does this section say").
3. **Retrievability** (deterministic, `filter_retrievable`) -- run this
   *after* the variant matrix is ingested (`eval matrix-ingest`), not here.
   Keep an item only if *at least one* matrix variant surfaces its
   `document_id` within top-20. Checking only the generating variant would
   bake that variant's advantage into the dataset.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass

from loguru import logger
from openai import OpenAI

from tauri_assistant.chat.retrieval import NotIngestedError, Passage, retrieve
from tauri_assistant.eval.dataset import QuestionItem
from tauri_assistant.eval.metrics import hit_rate
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository import get_repository
from tauri_assistant.repository.base import StoredChunk
from tauri_assistant.settings import settings

# ---- 1. Sampling ------------------------------------------------------

# Target counts per source, floored so the small sources (js-api,
# plugin-permissions) aren't drowned out by rust-api's much larger chunk
# count. Roughly proportional to source size otherwise.
DEFAULT_QUOTA: dict[str, int] = {
    "tauri-docs": 90,
    "rust-api": 90,
    "js-api": 40,
    "plugin-permissions": 30,
}

# Below this, a chunk is likely a stub (the corpus's own token p50 is 84)
# and produces an unanswerably thin question.
MIN_CHUNK_TOKENS = 120

_SAMPLE_SEED = 0  # deterministic sampling -- reruns pick the same chunks


def sample_chunks(variant: Variant, quota: dict[str, int] | None = None) -> list[StoredChunk]:
    quota = quota if quota is not None else DEFAULT_QUOTA
    store = get_repository().embedding(variant)
    rng = random.Random(_SAMPLE_SEED)

    sampled: list[StoredChunk] = []
    for source, count in quota.items():
        chunks = store.sample(where={"source": source}, limit=5000)
        eligible = [c for c in chunks if int(c.metadata.get("token_count", 0) or 0) >= MIN_CHUNK_TOKENS]
        rng.shuffle(eligible)
        chosen = eligible[:count]
        logger.info(f"{source}: sampled {len(chosen)}/{len(eligible)} eligible chunks (quota {count})")
        sampled.extend(chosen)
    return sampled


# ---- 2. Generation ------------------------------------------------------

GENERATE_PROMPT = """You are creating a realistic developer question that the passage below would answer.

Passage (from Tauri's documentation/source, heading: "{heading_path}"):
{text}

Write ONE realistic question a developer using the Tauri app framework might ask, which this exact \
passage answers. Rules:
- Ask about the concept, API, or behavior in your own words.
- Do NOT quote any rare identifier, function name, or distinctive phrase verbatim from the passage -- \
paraphrase or describe it instead.
- Do NOT reference "this passage", "this section", or "the above" -- ask a natural, standalone question.
- One sentence, ending in a question mark.

Respond with ONLY the question text, nothing else."""


def generate_question(chunk: StoredChunk, client: OpenAI, model: str) -> str | None:
    prompt = GENERATE_PROMPT.format(
        heading_path=chunk.metadata.get("heading_path", ""),
        text=chunk.text[:3000],
    )
    resp = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}], temperature=0
    )
    text = (resp.choices[0].message.content or "").strip().strip('"').strip()
    if not text or not text.endswith("?"):
        return None
    return text


# ---- 3. Leakage filter ------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9_]+")


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = _WORD_RE.findall(text.lower())
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def has_leakage(question: str, chunk_text: str, n: int = 5) -> bool:
    """True if `question` shares a normalized n-gram with `chunk_text` --
    the generator likely copied a distinctive phrase verbatim rather than
    paraphrasing, which would make the question trivial for every variant."""
    question_grams = _ngrams(question, n)
    if not question_grams:
        return False
    return bool(question_grams & _ngrams(chunk_text, n))


# ---- 4. Answerability filter (LLM) ------------------------------------

ANSWERABILITY_PROMPT = """You are screening a candidate question for an evaluation set that tests a \
documentation search system for the Tauri app framework.

Question: {question}

Reject it if ANY of these apply:
- A developer already familiar with Tauri could confidently answer it from general knowledge, without \
needing to consult Tauri's own docs, API reference, or source (too generic / not Tauri-specific).
- It refers to "this section", "this passage", "the above", or similar -- it must stand alone.
- It is not actually a question, or is not about the Tauri app framework.

In one short sentence, say why, then respond with ONLY a JSON object of the form \
{{"keep": true or false, "reason": "..."}}. Put "keep" first so it survives if your response is cut off."""


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    keep: bool
    reason: str


def judge_answerability(question: str, client: OpenAI, model: str) -> JudgeVerdict:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": ANSWERABILITY_PROMPT.format(question=question)}],
        temperature=0,
    )
    content = (resp.choices[0].message.content or "").strip()
    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(content)
        return JudgeVerdict(keep=bool(data["keep"]), reason=str(data.get("reason", "")))
    except json.JSONDecodeError, KeyError, ValueError:
        pass

    # Small local judges can truncate mid-JSON -- fall back to a regex
    # rather than losing the whole verdict to one truncated field.
    match = re.search(r'"keep"\s*:\s*(true|false)', content)
    if match:
        keep = match.group(1) == "true"
        return JudgeVerdict(keep=keep, reason=f"(truncated judge response) {content[:200]}")
    # Fail closed: an unparseable verdict should not let a question into the
    # dataset unexamined.
    return JudgeVerdict(keep=False, reason=f"unparseable judge response: {content[:200]}")


# ---- 5. Retrievability filter (run after matrix ingestion) ------------


def filter_retrievable(
    items: list[QuestionItem], variants: list[Variant], k: int = 20
) -> tuple[list[QuestionItem], list[QuestionItem]]:
    """Keep an item only if at least one variant's collection surfaces its
    document_id/heading_path within top-`k`. Seed items are never dropped.
    Must run after `eval matrix-ingest` -- variants with no collection yet
    are skipped for that item rather than counted as a miss."""
    kept: list[QuestionItem] = []
    dropped: list[QuestionItem] = []
    for item in items:
        if item.seed:
            kept.append(item)
            continue
        if _any_variant_retrieves(item, variants, k):
            kept.append(item)
        else:
            dropped.append(item)
    return kept, dropped


def _any_variant_retrieves(item: QuestionItem, variants: list[Variant], k: int) -> bool:
    for variant in variants:
        try:
            passages: list[Passage] = retrieve(item.question, k=k, variant=variant)
        except NotIngestedError:
            continue
        if hit_rate(passages, item) > 0:
            return True
    return False


# ---- Orchestration ------------------------------------------------------


def _make_item(chunk: StoredChunk, question: str, index: int) -> QuestionItem:
    source = str(chunk.metadata.get("source", ""))
    return QuestionItem(
        id=f"gen-{source}-{index:04d}",
        question=question,
        source=source,
        kind=str(chunk.metadata.get("kind", "")),
        expected_document_ids=(str(chunk.metadata.get("document_id", "")),),
        expected_heading_path=str(chunk.metadata.get("heading_path", "")),
        origin_chunk_id=chunk.id,
    )


def generate_dataset(
    variant: Variant,
    quota: dict[str, int] | None = None,
    client: OpenAI | None = None,
) -> tuple[list[QuestionItem], dict[str, int]]:
    """Sample, generate, and leakage+answerability-filter questions from
    `variant`'s collection. Does NOT apply the retrievability filter or
    merge seeds -- callers do that once the matrix is ingested (see
    `eval/__main__.py`).

    Returns `(items, drop_counts)` where `drop_counts` has keys
    `sampled`, `generation_failed`, `leakage`, `answerability`, `kept`.
    """
    client = client or OpenAI(base_url=settings.chat.base_url, api_key=settings.chat.api_key)
    generator_model = settings.eval.generator_model

    chunks = sample_chunks(variant, quota)
    counts = {"sampled": len(chunks), "generation_failed": 0, "leakage": 0, "answerability": 0, "kept": 0}
    items: list[QuestionItem] = []

    for i, chunk in enumerate(chunks):
        question = generate_question(chunk, client, generator_model)
        if question is None:
            counts["generation_failed"] += 1
            continue

        if has_leakage(question, chunk.text):
            counts["leakage"] += 1
            continue

        verdict = judge_answerability(question, client, settings.eval.judge_model)
        if not verdict.keep:
            counts["answerability"] += 1
            continue

        items.append(_make_item(chunk, question, i))
        counts["kept"] += 1

    logger.info(f"generate_dataset: {counts}")
    return items, counts
