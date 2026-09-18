"""CLI for the variant matrix + golden-question-set + eval-runner pipeline.

    uv run python -m tauri_assistant.eval matrix-ingest [--only LABEL] [--force]
    uv run python -m tauri_assistant.eval generate [--count 250]
    uv run python -m tauri_assistant.eval verify
    uv run python -m tauri_assistant.eval run [--fingerprint FP]

Typical first run: `fetch` (via the API or `sources.fetch.sync_repos`) once,
then `matrix-ingest`, `generate`, `verify`, `run`, in that order -- `verify`
needs the matrix already ingested (see `eval/generate.py`'s module
docstring on the retrievability filter).
"""

from __future__ import annotations

import argparse
import sys

from loguru import logger

from tauri_assistant import telemetry
from tauri_assistant.eval import dataset as ds
from tauri_assistant.eval import generate as gen
from tauri_assistant.eval import matrix as mx
from tauri_assistant.eval import runner
from tauri_assistant.ingest.pipeline import ingest
from tauri_assistant.settings import settings
from tauri_assistant.sources import get_sources


def _resolve_source_shas() -> dict[str, str]:
    return {s.name: s.git_sha for s in get_sources()}


def cmd_matrix_ingest(args: argparse.Namespace) -> None:
    source_shas = _resolve_source_shas()
    entries = mx.MATRIX
    if args.only:
        entries = tuple(e for e in entries if e.label == args.only)
        if not entries:
            labels = ", ".join(e.label for e in mx.MATRIX)
            print(f"No matrix entry named {args.only!r}. Available: {labels}", file=sys.stderr)
            raise SystemExit(1)

    for entry in entries:
        variant = mx.build_variant(entry, source_shas)
        logger.info(f"--- {entry.label}: {variant.describe()} ---")
        report = ingest(variant=variant, force=args.force)
        if report.stats.chunks_written == 0 and not args.force:
            logger.info(f"{entry.label}: already built, skipped")
        else:
            logger.info(f"{entry.label}: {report.stats.chunks_written} chunks written")


def cmd_generate(args: argparse.Namespace) -> None:
    source_shas = _resolve_source_shas()
    baseline = mx.build_variant(mx.MATRIX[0], source_shas)

    quota = gen.DEFAULT_QUOTA
    if args.count and args.count != sum(gen.DEFAULT_QUOTA.values()):
        total = sum(gen.DEFAULT_QUOTA.values())
        quota = {k: max(1, round(v * args.count / total)) for k, v in gen.DEFAULT_QUOTA.items()}

    items, counts = gen.generate_dataset(baseline, quota=quota)
    merged = ds.merge_seed(items)
    ds.save(merged)
    logger.info(f"generate: {counts}, {len(merged)} item(s) total (incl. {len(ds.SEED_ITEMS)} seed) "
                f"written to {ds.DEFAULT_PATH}")


def cmd_verify(args: argparse.Namespace) -> None:
    items = ds.load()
    if not items:
        print(f"No questions at {ds.DEFAULT_PATH} -- run `generate` first.", file=sys.stderr)
        raise SystemExit(1)

    source_shas = _resolve_source_shas()
    variants = mx.all_variants(source_shas)
    kept, dropped = gen.filter_retrievable(items, variants, k=args.k)
    ds.save(kept)

    by_source_kept = {src: len(v) for src, v in ds.by_source(kept).items()}
    logger.info(f"verify: kept {len(kept)}, dropped {len(dropped)} (unretrievable at k={args.k})")
    logger.info(f"kept by source: {by_source_kept}")
    if dropped:
        logger.info("dropped ids: " + ", ".join(item.id for item in dropped[:20]))


def cmd_run(args: argparse.Namespace) -> None:
    telemetry.init(settings)
    if not telemetry.is_active():
        print(
            "Langfuse is not active -- set LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY "
            "(see infra/langfuse/README.md) before running the eval.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    items = ds.load()
    if not items:
        print(f"No questions at {ds.DEFAULT_PATH} -- run `generate` (and `verify`) first.", file=sys.stderr)
        raise SystemExit(1)

    dataset_name = runner.ensure_dataset(items)

    source_shas = _resolve_source_shas()
    variants = mx.all_variants(source_shas)
    if args.fingerprint:
        variants = [v for v in variants if v.fingerprint == args.fingerprint]
        if not variants:
            print(f"No matrix variant with fingerprint {args.fingerprint!r}.", file=sys.stderr)
            raise SystemExit(1)

    try:
        results = runner.run_all(variants, dataset_name)
        runner.print_summary(results)
    finally:
        telemetry.shutdown()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tauri_assistant.eval")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("matrix-ingest", help="Ingest every variant in the matrix.")
    p_ingest.add_argument("--only", help="Ingest only the matrix entry with this label.")
    p_ingest.add_argument("--force", action="store_true", help="Rebuild even if already ingested.")
    p_ingest.set_defaults(func=cmd_matrix_ingest)

    p_generate = sub.add_parser("generate", help="Generate + filter golden questions from the baseline.")
    p_generate.add_argument("--count", type=int, default=settings.eval.question_count)
    p_generate.set_defaults(func=cmd_generate)

    p_verify = sub.add_parser("verify", help="Drop questions no matrix variant can retrieve.")
    p_verify.add_argument("--k", type=int, default=20)
    p_verify.set_defaults(func=cmd_verify)

    p_run = sub.add_parser("run", help="Upload the dataset and run one Langfuse experiment per variant.")
    p_run.add_argument("--fingerprint", help="Run only the variant with this fingerprint.")
    p_run.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
