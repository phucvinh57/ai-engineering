"""Run the golden set end-to-end (retrieve + generate + judge) and score it."""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI

from tauri_assistant.config import Settings
from tauri_assistant.eval.dataset import GOLDEN_SET, GoldenItem
from tauri_assistant.eval.metrics import (
    hit_rate,
    judge_answer_relevancy,
    judge_faithfulness,
    mrr,
    precision_at_k,
)
from tauri_assistant.ingest.store import ChromaStore
from tauri_assistant.rag.chat import prepare_turn


@dataclass
class ItemResult:
    id: str
    question: str
    source: str
    hit_rate: float
    mrr: float
    precision_at_k: float
    faithfulness: int
    faithfulness_reasoning: str
    answer_relevancy: int
    answer_relevancy_reasoning: str
    answer: str
    retrieved_urls: list[str]


@dataclass
class EvalReport:
    run_at: str
    top_k: int
    generation_model: str
    judge_model: str
    items: list[ItemResult]
    avg_hit_rate: float
    avg_mrr: float
    avg_precision_at_k: float
    avg_faithfulness: float
    avg_answer_relevancy: float


def _generate_answer(chat_messages: list[dict[str, str]], settings: Settings, client: OpenAI) -> str:
    resp = client.chat.completions.create(model=settings.chat_model, messages=chat_messages, temperature=0)
    return (resp.choices[0].message.content or "").strip()


def run_eval(
    settings: Settings,
    top_k: int | None = None,
    dataset: list[GoldenItem] | None = None,
) -> EvalReport:
    dataset = dataset if dataset is not None else GOLDEN_SET
    top_k = top_k or settings.retrieval_top_k
    store = ChromaStore(settings)
    # A vanilla OpenAI client -- eval never calls telemetry.init(), so this
    # never emits a trace even if Langfuse keys happen to be configured in
    # the environment (scope: chat + search request paths only).
    client = OpenAI(base_url=settings.chat_base_url, api_key=settings.chat_api_key)

    results: list[ItemResult] = []
    for item in dataset:
        # `prepare_turn` (rag/chat.py) is the same helper the live chat path
        # uses -- condense (when item.history is non-empty), retrieve,
        # assemble the prompt -- so eval and production score identical
        # pipelines.
        messages = [{"role": role, "content": content} for role, content in item.history]
        messages.append({"role": "user", "content": item.question})
        prepared = prepare_turn(messages, settings, store, client, top_k=top_k)
        answer = _generate_answer(prepared.chat_messages, settings, client)

        faithfulness = judge_faithfulness(item.question, prepared.context, answer, settings, client)
        relevancy = judge_answer_relevancy(item.question, answer, settings, client)

        results.append(
            ItemResult(
                id=item.id,
                question=item.question,
                source=item.source,
                hit_rate=hit_rate(prepared.chunks, item.expected_matches),
                mrr=mrr(prepared.chunks, item.expected_matches),
                precision_at_k=precision_at_k(prepared.chunks, item.expected_matches),
                faithfulness=faithfulness.score,
                faithfulness_reasoning=faithfulness.reasoning,
                answer_relevancy=relevancy.score,
                answer_relevancy_reasoning=relevancy.reasoning,
                answer=answer,
                retrieved_urls=[c.url for c in prepared.chunks],
            )
        )

    def avg(values: list[float]) -> float:
        return statistics.fmean(values) if values else 0.0

    return EvalReport(
        run_at=datetime.now(UTC).isoformat(),
        top_k=top_k,
        generation_model=settings.chat_model,
        judge_model=settings.eval_judge_model,
        items=results,
        avg_hit_rate=avg([r.hit_rate for r in results]),
        avg_mrr=avg([r.mrr for r in results]),
        avg_precision_at_k=avg([r.precision_at_k for r in results]),
        avg_faithfulness=avg([r.faithfulness for r in results]),
        avg_answer_relevancy=avg([r.answer_relevancy for r in results]),
    )


def render_markdown(report: EvalReport) -> str:
    lines = [
        f"# Eval Report — {report.run_at}",
        "",
        f"- **Top K:** {report.top_k}",
        f"- **Generation model:** {report.generation_model}",
        f"- **Judge model:** {report.judge_model}",
        "",
        "## Summary",
        "",
        "| Metric | Avg |",
        "| --- | --- |",
        f"| Hit Rate | {report.avg_hit_rate:.2f} |",
        f"| MRR | {report.avg_mrr:.2f} |",
        f"| Precision@K | {report.avg_precision_at_k:.2f} |",
        f"| Faithfulness | {report.avg_faithfulness:.2f}/5 |",
        f"| Answer Relevancy | {report.avg_answer_relevancy:.2f}/5 |",
        "",
        "## Items",
        "",
        "| ID | Source | Hit | MRR | Prec@K | Faith | Relevancy |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.items:
        lines.append(
            f"| {item.id} | {item.source} | {item.hit_rate:.0f} | {item.mrr:.2f} | "
            f"{item.precision_at_k:.2f} | {item.faithfulness}/5 | {item.answer_relevancy}/5 |"
        )
    lines.append("")

    for item in report.items:
        lines.extend(
            [
                f"### {item.id}",
                "",
                f"**Question:** {item.question}",
                "",
                f"**Source:** {item.source}",
                "",
                (
                    f"**Retrieval:** hit_rate={item.hit_rate:.0f}, mrr={item.mrr:.2f}, "
                    f"precision@k={item.precision_at_k:.2f}"
                ),
                "",
                f"**Faithfulness:** {item.faithfulness}/5 — {item.faithfulness_reasoning}",
                "",
                f"**Answer Relevancy:** {item.answer_relevancy}/5 — {item.answer_relevancy_reasoning}",
                "",
                "**Answer:**",
                "",
                f"> {item.answer.replace(chr(10), chr(10) + '> ')}",
                "",
                "**Retrieved URLs:**",
                "",
                *[f"- {url}" for url in item.retrieved_urls],
                "",
            ]
        )

    return "\n".join(lines)


def save_report(report: EvalReport, settings: Settings) -> tuple[Path, Path]:
    out_dir = settings.data_dir / "eval_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = report.run_at.replace(":", "-")

    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(asdict(report), indent=2))

    md_path = out_dir / f"{stem}.md"
    md_path.write_text(render_markdown(report))

    return json_path, md_path
