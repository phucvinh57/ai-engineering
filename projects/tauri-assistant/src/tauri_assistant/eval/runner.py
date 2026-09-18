"""Upload the golden set to Langfuse once, then run one experiment per
variant so they can be compared side by side in the Langfuse UI (Datasets ->
`settings.eval.dataset_name` -> Experiments).

Variants are run grouped by embedding model (see `run_all`) because
`get_embedding_model` is `lru_cache(maxsize=2)` -- interleaving two
different models would thrash that cache and reload a multi-hundred-MB
model repeatedly.

Scope: retrieval + cost only (`EVALUATORS` below) -- Hit Rate/MRR/Precision@k,
per-stage latency, context tokens. The chat model is constant across every
matrix entry, so it's not where the matrix's variance is; generation-quality
metrics (Faithfulness, Answer Relevancy, LLM-judged by a model other than
`settings.chat.model` so the system never grades its own homework) are a
natural second pass on top of the same `make_task`/dataset once retrieval
numbers are in hand -- add a non-streaming, temperature=0 completion call to
`chat/llm.py`, then two more evaluators here.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from typing import Any

from langfuse import Evaluation
from loguru import logger

from tauri_assistant import telemetry
from tauri_assistant.chat.retrieval import Passage
from tauri_assistant.chat.turn import prepare_turn
from tauri_assistant.eval.dataset import QuestionItem
from tauri_assistant.eval.metrics import context_tokens, hit_rate, mrr, precision_at_k
from tauri_assistant.ingest.variant import Variant
from tauri_assistant.repository import get_repository
from tauri_assistant.settings import settings

# ---- Dataset upload -----------------------------------------------------


def _dataset_item_id(dataset_name: str, item: QuestionItem) -> str:
    # Langfuse dataset item ids must be globally unique across the whole
    # project, not just this dataset -- scope by dataset name so bumping
    # `settings.eval.dataset_name` (e.g. after a question-set change) never
    # collides with the old dataset's ids.
    return f"{dataset_name}:{item.id}"


def ensure_dataset(items: list[QuestionItem], dataset_name: str | None = None) -> str:
    """Idempotent: `create_dataset` is best-effort (the name may already
    exist), and `create_dataset_item` upserts by id, so re-running this
    against an unchanged question set is a no-op."""
    client = telemetry.raw_client()
    if client is None:
        raise RuntimeError("Langfuse is not active -- set LANGFUSE_PUBLIC_KEY/SECRET_KEY to run the eval.")

    dataset_name = dataset_name or settings.eval.dataset_name
    try:
        client.create_dataset(name=dataset_name)
    except Exception as exc:
        logger.debug(f"create_dataset({dataset_name!r}): {exc} (likely already exists, continuing)")

    for item in items:
        expected_output = {
            "document_ids": list(item.expected_document_ids),
            "heading_path": item.expected_heading_path,
        }
        metadata = {"source": item.source, "kind": item.kind, "seed": item.seed, "local_id": item.id}
        client.create_dataset_item(
            id=_dataset_item_id(dataset_name, item),
            dataset_name=dataset_name,
            input={"question": item.question},
            expected_output=expected_output,
            metadata=metadata,
        )
    logger.info(f"Uploaded {len(items)} item(s) to dataset {dataset_name!r}")
    return dataset_name


# ---- Task: retrieve + time it, for one variant --------------------------


def _passage_record(passage: Passage) -> dict[str, Any]:
    return {
        "document_id": passage.metadata.get("document_id", ""),
        "heading_path": passage.metadata.get("heading_path", ""),
        "score": passage.score,
        "text": passage.text[:300],
    }


def make_task(variant: Variant):
    def task(*, item, **_kwargs) -> dict[str, Any]:
        question = item.input["question"]
        messages = [{"role": "user", "content": question}]
        started = time.perf_counter()
        prepared = prepare_turn(messages, k=settings.eval.top_k, variant=variant)
        total_ms = (time.perf_counter() - started) * 1000
        return {
            "passages": [_passage_record(p) for p in prepared.passages],
            "embed_ms": prepared.timing.embed_ms,
            "query_ms": prepared.timing.query_ms,
            "expand_ms": prepared.timing.expand_ms,
            "total_ms": total_ms,
            "context_tokens": context_tokens(prepared.system_prompt),
        }

    return task


# ---- Evaluators -----------------------------------------------------


def _question_item(input: Any, expected_output: Any, metadata: Any) -> QuestionItem:
    expected_output = expected_output or {}
    metadata = metadata or {}
    return QuestionItem(
        id=str(metadata.get("local_id", "")),
        question=str((input or {}).get("question", "")),
        source=str(metadata.get("source", "")),
        kind=str(metadata.get("kind", "")),
        expected_document_ids=tuple(expected_output.get("document_ids") or ()),
        expected_heading_path=str(expected_output.get("heading_path", "")),
    )


def _passages_from_output(output: dict[str, Any]) -> list[Passage]:
    return [
        Passage(
            text=p.get("text", ""),
            metadata={"document_id": p.get("document_id", ""), "heading_path": p.get("heading_path", "")},
            score=float(p.get("score", 0.0)),
        )
        for p in output.get("passages", [])
    ]


def hit_rate_evaluator(*, input, output, expected_output=None, metadata=None, **_kwargs):
    item = _question_item(input, expected_output, metadata)
    return Evaluation(name="hit_rate", value=hit_rate(_passages_from_output(output), item))


def mrr_evaluator(*, input, output, expected_output=None, metadata=None, **_kwargs):
    item = _question_item(input, expected_output, metadata)
    return Evaluation(name="mrr", value=mrr(_passages_from_output(output), item))


def precision_evaluator(*, input, output, expected_output=None, metadata=None, **_kwargs):
    item = _question_item(input, expected_output, metadata)
    return Evaluation(name="precision_at_k", value=precision_at_k(_passages_from_output(output), item))


def latency_evaluator(*, output, **_kwargs):
    return [
        Evaluation(name="embed_ms", value=output["embed_ms"]),
        Evaluation(name="query_ms", value=output["query_ms"]),
        Evaluation(name="expand_ms", value=output["expand_ms"]),
        Evaluation(name="total_ms", value=output["total_ms"]),
    ]


def context_tokens_evaluator(*, output, **_kwargs):
    return Evaluation(name="context_tokens", value=output["context_tokens"])


EVALUATORS = [
    hit_rate_evaluator,
    mrr_evaluator,
    precision_evaluator,
    latency_evaluator,
    context_tokens_evaluator,
]

_MEAN_METRICS = (
    "hit_rate",
    "mrr",
    "precision_at_k",
    "embed_ms",
    "query_ms",
    "expand_ms",
    "total_ms",
    "context_tokens",
)


def _mean_of(metric_name: str):
    def run_evaluator(*, item_results, **_kwargs):
        values = [
            e.value
            for r in item_results
            for e in r.evaluations
            if e.name == metric_name and isinstance(e.value, int | float)
        ]
        avg = statistics.fmean(values) if values else 0.0
        return Evaluation(name=f"mean_{metric_name}", value=avg)

    run_evaluator.__name__ = f"mean_{metric_name}"
    return run_evaluator


RUN_EVALUATORS = [_mean_of(name) for name in _MEAN_METRICS]


# ---- Orchestration -----------------------------------------------------


def run_variant(variant: Variant, dataset_name: str | None = None) -> Any:
    client = telemetry.raw_client()
    if client is None:
        raise RuntimeError("Langfuse is not active -- set LANGFUSE_PUBLIC_KEY/SECRET_KEY to run the eval.")

    dataset_name = dataset_name or settings.eval.dataset_name
    dataset = client.get_dataset(dataset_name)

    build = get_repository().ingest_run.for_variant(variant.fingerprint, limit=1)
    metadata: dict[str, Any] = variant.as_dict() | {"fingerprint": variant.fingerprint}
    if build:
        metadata["build"] = {
            k: build[0][k] for k in ("chunks_written", "embed_seconds", "docs_total") if k in build[0]
        }

    result = dataset.run_experiment(
        name=f"variant-{variant.fingerprint}",
        run_name=f"{variant.describe()} @ {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        task=make_task(variant),
        evaluators=EVALUATORS,
        run_evaluators=RUN_EVALUATORS,
        metadata=metadata,
        # The embedding model and Ollama are both local and effectively
        # single-threaded already -- concurrency here would only make the
        # per-item latency numbers meaningless.
        max_concurrency=1,
    )
    logger.info(result.format())
    return result


def run_all(variants: list[Variant], dataset_name: str | None = None) -> dict[str, Any]:
    """Runs grouped by embedding model -- see module docstring."""
    by_model: dict[str, list[Variant]] = defaultdict(list)
    for variant in variants:
        by_model[variant.embedding_model].append(variant)

    results: dict[str, Any] = {}
    for model, group in by_model.items():
        logger.info(f"--- embedding model: {model} ({len(group)} variant(s)) ---")
        for variant in group:
            results[variant.fingerprint] = run_variant(variant, dataset_name)
    return results


def print_summary(results: dict[str, Any]) -> None:
    """A variant x metric table from each run's `run_evaluations` (the
    `mean_*` scores `RUN_EVALUATORS` computed), plus a link to each run in
    the Langfuse UI. `result.format()` on each individual result (already
    logged in `run_variant`) has the full per-metric breakdown."""
    metric_names = [f"mean_{name}" for name in _MEAN_METRICS]
    header = ["fingerprint", *metric_names]
    print(" | ".join(header))
    for fingerprint, result in results.items():
        by_name = {e.name: e.value for e in result.run_evaluations}
        row = [fingerprint, *(f"{by_name.get(m, 0.0):.3f}" for m in metric_names)]
        print(" | ".join(row))
        if result.dataset_run_url:
            print(f"  -> {result.dataset_run_url}")
