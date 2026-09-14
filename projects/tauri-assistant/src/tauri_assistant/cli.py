import typer

from tauri_assistant.config import get_settings

app = typer.Typer(help="Tauri app framework RAG assistant.")
eval_app = typer.Typer(help="Score the golden Q&A set, or harvest real traces into new candidates.")
app.add_typer(eval_app, name="eval")


@app.command()
def fetch(
    tier: int = typer.Option(
        1,
        help="1 = guide docs + JS API + plugin permissions; 2 = adds the Rust API (docs.rs) crawl",
    ),
) -> None:
    """Clone doc/API/plugin repos and fetch Rust API pages for the given tier."""
    from tauri_assistant.ingest.pipeline import run_fetch

    settings = get_settings()
    result = run_fetch(settings, tier=tier)
    typer.echo(
        f"Fetched {result.guide_pages} guide pages, {result.js_api_symbols} JS API symbols, "
        f"{result.plugin_permissions} plugin permissions, {result.rust_api_pages} Rust API pages."
    )


@app.command()
def ingest(
    tier: int = typer.Option(1, help="Tier to ingest; run `fetch` for this tier first."),
) -> None:
    """Chunk, embed, and store all fetched sources for the given tier."""
    from tauri_assistant.ingest.pipeline import run_ingest

    settings = get_settings()
    n = run_ingest(settings, tier=tier)
    typer.echo(f"Ingested {n} chunks.")


@app.command()
def search(query: str, top_k: int = 8, source: str | None = None) -> None:
    """Pure retrieval, no LLM: print ranked chunks."""
    from tauri_assistant.ingest.store import ChromaStore
    from tauri_assistant.rag.retriever import retrieve

    settings = get_settings()
    store = ChromaStore(settings)
    where = {"source": source} if source else None
    chunks = retrieve(query, settings, store, top_k=top_k, where=where)
    for i, chunk in enumerate(chunks, start=1):
        typer.echo(f"[{i}] ({chunk.score:.3f}) {chunk.heading_path}")
        typer.echo(f"    {chunk.url}")
        snippet = chunk.text[:300].replace("\n", " ")
        typer.echo(f"    {snippet}...")
        typer.echo("")


@app.command()
def stats() -> None:
    """Print chunk/document counts by source and last fetch time."""
    from tauri_assistant.ingest.store import ChromaStore
    from tauri_assistant.sources.manifest import load_manifest

    settings = get_settings()
    store = ChromaStore(settings)
    manifest = load_manifest(settings)

    typer.echo(f"Total chunks: {store.count()}")
    for source, count in sorted(store.stats_by_source().items()):
        typer.echo(f"  {source}: {count}")

    last_fetch_at = max((e.fetched_at for e in manifest.values()), default=None)
    typer.echo(f"Last fetch: {last_fetch_at or 'never'}")


@eval_app.callback(invoke_without_command=True)
def eval_cmd(
    ctx: typer.Context,
    top_k: int = typer.Option(None, help="Override retrieval_top_k for this run."),
    save: bool = typer.Option(True, help="Persist the report as JSON and Markdown under data/eval_runs/."),
) -> None:
    """Run the golden Q&A set through retrieval + generation and score it.

    `tauri-assistant eval` on its own runs this; `tauri-assistant eval harvest`
    pulls real production traces into new candidates instead (see below).
    """
    if ctx.invoked_subcommand is not None:
        return

    from tauri_assistant.eval.runner import run_eval, save_report

    settings = get_settings()
    report = run_eval(settings, top_k=top_k)

    for item in report.items:
        typer.echo(
            f"[{item.id}] hit={item.hit_rate:.0f} mrr={item.mrr:.2f} prec@k={item.precision_at_k:.2f} "
            f"faithfulness={item.faithfulness}/5 relevancy={item.answer_relevancy}/5"
        )

    typer.echo("")
    typer.echo(
        f"Retrieval  -- hit_rate: {report.avg_hit_rate:.2f}  mrr: {report.avg_mrr:.2f}  "
        f"precision@k: {report.avg_precision_at_k:.2f}"
    )
    typer.echo(
        f"Generation -- faithfulness: {report.avg_faithfulness:.2f}/5  "
        f"answer_relevancy: {report.avg_answer_relevancy:.2f}/5"
    )

    if save:
        json_path, md_path = save_report(report, settings)
        typer.echo(f"\nSaved report to {json_path} and {md_path}")


@eval_app.command("harvest")
def eval_harvest_cmd(
    days: int = typer.Option(7, help="Look back this many days."),
    feedback: str = typer.Option(
        "any", help="Filter by user rating: 'up', 'down', or 'any'.", case_sensitive=False
    ),
    limit: int = typer.Option(200, help="Max traces to pull."),
    tag: str = typer.Option("chat", help="Langfuse tag to filter traces by."),
) -> None:
    """Pull real chat traces out of Langfuse and print pasteable GoldenItem
    candidates. Thumbs-down traces (`--feedback down`) are the ones worth
    turning into regression cases: harvest the question and its retrieved
    chunks, find the heading_path that should have won with
    `tauri-assistant search`, fill in expected_matches, and paste the result
    into eval/dataset.py's GOLDEN_SET by hand -- promotion stays a human
    edit, since that file promises every expected_matches was verified
    against the live corpus.
    """
    from tauri_assistant.eval.harvest import HarvestError, harvest, save_candidates

    if feedback not in ("up", "down", "any"):
        raise typer.BadParameter("must be 'up', 'down', or 'any'", param_hint="--feedback")

    settings = get_settings()
    try:
        items = harvest(settings, days=days, feedback=feedback, limit=limit, tag=tag)  # type: ignore[arg-type]
    except HarvestError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not items:
        typer.echo("No matching traces found.")
        return

    for item in items:
        flag = "needs review" if item.needs_review else "ready"
        typer.echo(f"# {item.trace_id}  feedback={item.feedback}  ({flag})")
        typer.echo(f"# {item.question}")
        if item.comment:
            typer.echo(f"# comment: {item.comment}")
        typer.echo(item.as_golden_item_snippet())
        typer.echo("")

    out_path = save_candidates(items, settings)
    typer.echo(f"Saved {len(items)} candidate(s) to {out_path}")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run("tauri_assistant.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
