import typer

from wayland_assistant.config import get_settings

app = typer.Typer(help="Wayland protocol & compositor RAG assistant.")


@app.command()
def fetch(tier: int = typer.Option(1, help="1 = core+stable+staging+wlr+book preface; 2 = adds unstable/experimental/doxygen")) -> None:
    """Clone protocol repos and fetch Book/Doxygen pages for the given tier."""
    from wayland_assistant.ingest.pipeline import run_fetch

    settings = get_settings()
    result = run_fetch(settings, tier=tier)
    typer.echo(
        f"Fetched {result.protocol_files} protocol XML files, "
        f"{result.book_pages} Book pages, {result.doxygen_pages} Doxygen pages."
    )


@app.command()
def ingest(tier: int = typer.Option(1, help="Tier to ingest; run `fetch` for this tier first.")) -> None:
    """Chunk, embed, and store all fetched sources for the given tier."""
    from wayland_assistant.ingest.pipeline import run_ingest

    settings = get_settings()
    n = run_ingest(settings, tier=tier)
    typer.echo(f"Ingested {n} chunks.")


@app.command()
def search(query: str, top_k: int = 8, source: str | None = None) -> None:
    """Pure retrieval, no LLM: print ranked chunks."""
    from wayland_assistant.ingest.store import ChromaStore
    from wayland_assistant.rag.retriever import retrieve

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
    from wayland_assistant.ingest.store import ChromaStore
    from wayland_assistant.sources.manifest import load_manifest

    settings = get_settings()
    store = ChromaStore(settings)
    manifest = load_manifest(settings)

    typer.echo(f"Total chunks: {store.count()}")
    for source, count in sorted(store.stats_by_source().items()):
        typer.echo(f"  {source}: {count}")

    last_fetch_at = max((e.fetched_at for e in manifest.values()), default=None)
    typer.echo(f"Last fetch: {last_fetch_at or 'never'}")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run("wayland_assistant.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
