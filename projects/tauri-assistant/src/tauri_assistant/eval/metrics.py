"""Retrieval + cost metrics for the variant matrix.

This is a search/QA workload (one standalone question, answered from
whichever chunks come back), which is exactly the case the eval literature
scores with Hit Rate@k and MRR -- not NDCG, which suits graded ranking, and
not Recall@k, which under single-relevance ground truth is identical to Hit
Rate and adds a column without adding information. Precision@k is tracked
too, but its ceiling is `1/k` here (one relevant document per question), so
it's a *relative* signal across variants, never an absolute one.
"""

from __future__ import annotations

import tiktoken

from tauri_assistant.chat.retrieval import Passage
from tauri_assistant.eval.dataset import QuestionItem

_ENCODING = tiktoken.get_encoding("cl100k_base")


def is_relevant(passage: Passage, item: QuestionItem) -> bool:
    document_id = str(passage.metadata.get("document_id", ""))
    if item.expected_document_ids and document_id in item.expected_document_ids:
        return True
    heading_path = str(passage.metadata.get("heading_path", "")).lower()
    return item.expected_heading_path.lower() in heading_path


def hit_rate(passages: list[Passage], item: QuestionItem) -> float:
    return 1.0 if any(is_relevant(p, item) for p in passages) else 0.0


def mrr(passages: list[Passage], item: QuestionItem) -> float:
    for rank, passage in enumerate(passages, start=1):
        if is_relevant(passage, item):
            return 1.0 / rank
    return 0.0


def precision_at_k(passages: list[Passage], item: QuestionItem) -> float:
    if not passages:
        return 0.0
    relevant = sum(1 for p in passages if is_relevant(p, item))
    return relevant / len(passages)


def context_tokens(system_prompt: str) -> int:
    """Model-independent token count (tiktoken `cl100k_base`, not the
    embedding model's own tokenizer) so this number stays comparable across
    variants even when the embedding model changes underneath."""
    return len(_ENCODING.encode(system_prompt))
