"""Retrieval + generation metrics for RAG evaluation.

Retrieval: this is a search/QA workload (one standalone question per turn,
answered from whichever chunks come back), which is exactly the case the
eval literature scores with Hit Rate@k and MRR -- not NDCG, which suits
graded recommendation ranking, and not Precision/Recall as the headline
metric, which mainly earn their keep when a false positive or false negative
is individually costly (medical, legal). Precision@k is still tracked as a
secondary signal, since a noisy top-k context is the main lever on
generation faithfulness for a small local model.

Generation: Faithfulness (does the answer stick to the retrieved context, or
invent APIs/permissions/behavior) and Answer Relevancy (does the answer
address the question at all) are judged by an LLM. The judge model is
configured separately from the model under test (`eval_judge_model` vs.
`chat_model`) so the system never grades its own homework, and each judge
prompt asks for reasoning before a score (chain-of-thought), per eval best
practice.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from tauri_assistant.config import Settings
from tauri_assistant.rag.retriever import RetrievedChunk


def is_relevant(chunk: RetrievedChunk, expected_matches: tuple[str, ...]) -> bool:
    haystack = f"{chunk.heading_path} {chunk.url}".lower()
    return any(match.lower() in haystack for match in expected_matches)


def hit_rate(chunks: list[RetrievedChunk], expected_matches: tuple[str, ...]) -> float:
    return 1.0 if any(is_relevant(c, expected_matches) for c in chunks) else 0.0


def mrr(chunks: list[RetrievedChunk], expected_matches: tuple[str, ...]) -> float:
    for rank, chunk in enumerate(chunks, start=1):
        if is_relevant(chunk, expected_matches):
            return 1.0 / rank
    return 0.0


def precision_at_k(chunks: list[RetrievedChunk], expected_matches: tuple[str, ...]) -> float:
    if not chunks:
        return 0.0
    relevant = sum(1 for c in chunks if is_relevant(c, expected_matches))
    return relevant / len(chunks)


FAITHFULNESS_JUDGE_PROMPT = """You are grading whether an AI assistant's answer is faithful to the \
provided context, i.e. every factual claim in the answer (API names, permission identifiers, \
behavior) is actually supported by the context, with nothing hallucinated.

Question: {question}

Context:
{context}

Answer:
{answer}

In one short sentence, note which claims are or are not supported, then respond with ONLY a JSON \
object of the form {{"reasoning": "...", "score": <integer 1-5>}}, where 5 means every claim is \
supported and 1 means the answer is largely unsupported or contradicts the context. Put "score" \
before "reasoning" in the JSON so it survives if your response is cut off."""

RELEVANCY_JUDGE_PROMPT = """You are grading whether an AI assistant's answer actually addresses the \
user's question, regardless of whether the answer is factually correct.

Question: {question}

Answer:
{answer}

In one short sentence, say why, then respond with ONLY a JSON object of the form {{"reasoning": \
"...", "score": <integer 1-5>}}, where 5 means the answer directly and completely addresses the \
question and 1 means it is off-topic or non-responsive. Put "score" before "reasoning" in the JSON \
so it survives if your response is cut off."""


@dataclass
class JudgeResult:
    score: int
    reasoning: str


def _judge(prompt: str, settings: Settings, client: OpenAI) -> JudgeResult:
    resp = client.chat.completions.create(
        model=settings.eval_judge_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    content = (resp.choices[0].message.content or "").strip()
    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(content)
        return JudgeResult(score=int(data["score"]), reasoning=str(data.get("reasoning", "")))
    except json.JSONDecodeError, KeyError, ValueError:
        pass

    # The judge's own output can get cut off mid-string on a small local model;
    # fall back to pulling the score out with a regex rather than losing the
    # whole verdict to one truncated field.
    match = re.search(r'"score"\s*:\s*(\d)', content)
    if match:
        return JudgeResult(score=int(match.group(1)), reasoning=f"(truncated judge response) {content[:200]}")
    return JudgeResult(score=0, reasoning=f"unparseable judge response: {content[:200]}")


def judge_faithfulness(
    question: str, context: str, answer: str, settings: Settings, client: OpenAI
) -> JudgeResult:
    prompt = FAITHFULNESS_JUDGE_PROMPT.format(question=question, context=context, answer=answer)
    return _judge(prompt, settings, client)


def judge_answer_relevancy(question: str, answer: str, settings: Settings, client: OpenAI) -> JudgeResult:
    prompt = RELEVANCY_JUDGE_PROMPT.format(question=question, answer=answer)
    return _judge(prompt, settings, client)
