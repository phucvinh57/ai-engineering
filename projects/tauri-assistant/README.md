# tauri-assistant

A retrieve-then-generate RAG chatbot over Tauri app framework documentation:
the guide/concept docs (tauri.app), the `@tauri-apps/api` JS/TS reference,
the `tauri` crate's Rust API (docs.rs), and every official plugin's
permissions/capabilities schema.

Uses a local LLM via [Ollama](https://ollama.com)'s OpenAI-compatible API
(`llama3.2` by default) for chat, a local `sentence-transformers`
model (`all-MiniLM-L6-v2`) for embeddings, Chroma as an embedded vector
store, FastAPI for the backend, and a Vite + React frontend.

## Setup

Pull the local chat model with Ollama (make sure `ollama serve` is running):

```bash
ollama pull llama3.2
```

From the repo root:

```bash
uv sync
cp projects/tauri-assistant/.env.example projects/tauri-assistant/.env
```

## Usage

```bash
# Clone doc/API/plugin repos + parse guide/JS-API/permissions (tier 1); tier 2 adds a docs.rs crawl
uv run --package tauri-assistant tauri-assistant fetch --tier 1

# Chunk, embed, and store into Chroma
uv run --package tauri-assistant tauri-assistant ingest --tier 1

# Chunk/doc counts by source
uv run --package tauri-assistant tauri-assistant stats

# Pure retrieval, no LLM
uv run --package tauri-assistant tauri-assistant search "how do I grant a plugin permission to a window"

# API server
uv run --package tauri-assistant tauri-assistant serve
```

Frontend:

```bash
cd projects/tauri-assistant/web
npm install
npm run dev
```

The Vite dev server proxies `/api` to `localhost:8000`.

Run the test suite:

```bash
uv run --package tauri-assistant pytest projects/tauri-assistant/tests
```

## Telemetry (optional)

`/api/chat` and `/api/search` can trace every real query -- condensed
question, retrieved chunks + scores, the generated answer, latency, and
user thumbs up/down -- to [Langfuse](https://langfuse.com), turning live
traffic into evaluation data (see [Evaluation](#evaluation) below). It's
fully optional: with no keys configured, telemetry is a complete no-op --
zero warnings, zero network calls.

```bash
# From the repo root. Self-hosted (Docker; see infra/langfuse/README.md),
# or use Langfuse Cloud instead -- see that README for the trade-off.
docker compose -f infra/langfuse/docker-compose.yml up -d
```

Then set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` in
`.env` (see `.env.example`) and restart `serve`. Every assistant reply in
the web UI gets a 👍/👎 that scores the corresponding trace.

## Architecture

```mermaid
flowchart TD
    subgraph Sources
        A1[tauri-docs repo\nMDX guide pages]
        A2[tauri repo\npackages/api/src TS + JSDoc]
        A3[docs.rs\nrustdoc HTML pages]
        A4[plugins-workspace repo\npermissions/*.toml per plugin]
    end

    subgraph Ingest pipeline
        B1[repos.sync_repos\nclone/pull tauri-docs, tauri, plugins-workspace]
        B2[guide.list_guide_pages\nstrip MDX frontmatter/imports/JSX]
        B3[js_api.parse_api_file\none JsApiSymbol per top-level export]
        B4[rust_api.fetch_rust_api_pages\nHTML to markdown, threaded]
        B5[permissions.parse_plugin_permissions\none record per permission/default/set]
        B6[manifest\ncontent-hash cache, data/raw + data/manifest.jsonl]
        C1[chunker.chunk_markdown /\nchunk_js_symbol / chunk_permission\nheading- or symbol-aware, token-bounded]
        D1[embedder.embed_texts\nlocal sentence-transformers]
        E1[(ChromaStore\ndata/chroma, upsert by content_hash)]
    end

    A1 --> B1 --> B2
    A2 --> B1 --> B3
    A4 --> B1 --> B5
    A3 --> B4
    B2 --> B6
    B3 --> B6
    B4 --> B6
    B5 --> B6
    B2 --> C1
    B3 --> C1
    B4 --> C1
    B5 --> C1
    C1 --> D1 --> E1

    subgraph Query pipeline
        F1[retriever.condense_query\nfold chat history into standalone question]
        F2[embedder.embed_query]
        F3[ChromaStore.query\ncosine top_k, optional source filter]
        F4[retriever.assemble_context\nnumbered context blocks]
        F5[chat.stream_chat\nlocal LLM via Ollama, streamed + cited]
    end

    E1 --> F3
    F1 --> F2 --> F3 --> F4 --> F5

    subgraph Interfaces
        G1[cli.py\nfetch / ingest / search / stats / eval / serve]
        G2["api/routes.py\nFastAPI: /api/chat (SSE), /search, /feedback, /stats, /health"]
        G3[web\nVite + React: Chat.tsx (+ 👍/👎), Search.tsx]
    end

    G1 -.-> B1
    G1 -.-> C1
    G1 -.-> F3
    G2 --> F5
    G2 --> F3
    G3 --> G2

    subgraph Telemetry [Telemetry -- optional]
        H1[(Langfuse\ntraces, sessions, scores)]
        H2["eval/harvest.py\ntraces -> GoldenItem candidates"]
    end

    F1 -.-> H1
    F3 -.-> H1
    F5 -.-> H1
    G2 -. "👍/👎" .-> H1
    H1 -. "eval harvest" .-> H2
```

**Ingest** (`tauri-assistant fetch` / `ingest`, orchestrated by `ingest/pipeline.py`):

1. **Fetch** — `sources/repos.py` shallow-clones/pulls `tauri-docs`, `tauri`, and `plugins-workspace`. `sources/guide.py` reads the MDX/Markdown guide pages straight from the `tauri-docs` clone (stripping frontmatter/imports/JSX). `sources/js_api.py` reads `packages/api/src/*.ts` from the `tauri` clone and segments each file into one record per top-level exported symbol, using its leading JSDoc comment. `sources/permissions.py` reads each plugin's `permissions/*.toml` from `plugins-workspace` into one record per `[[permission]]`, `[default]`, or `[[set]]` entry. `sources/rust_api.py` is the one HTTP-fetched source: it scrapes the `tauri` crate's docs.rs pages (retried via `tenacity`, fetched concurrently), cached as markdown under `data/raw/rust-api/`. Every fetched/parsed unit is recorded in `data/manifest.jsonl` (`sources/manifest.py`) keyed by a content hash.
2. **Chunk** — `ingest/chunker.py` turns each guide/Rust-API markdown page into one chunk per leaf heading section, and each JS API symbol / plugin permission into one chunk. Oversized chunks are token-window-split with overlap. Every chunk gets a breadcrumb prefix (e.g. `@tauri-apps/api > event > listen`, or `fs plugin > permissions > allow-read-file`) so it reads standalone out of context.
3. **Embed + store** — `ingest/embedder.py` batches chunk text through a local `sentence-transformers` model (no API calls); `ingest/store.py` upserts vectors + text + metadata into a persistent Chroma collection (`data/chroma/`), keyed by content hash for idempotent re-ingestion.

**Query** (`tauri-assistant search`, or `/api/chat` / `/api/search`):

1. `rag/retriever.py` condenses the latest question against chat history into a standalone query (skipped on the first turn), embeds it, and queries Chroma for the top-k nearest chunks (optionally filtered by `source`: `guide` / `js-api` / `rust-api` / `permissions`).
2. Retrieved chunks are deduplicated and assembled into numbered context blocks (`rag/prompts.py`).
3. `rag/chat.py` streams a completion from the local LLM (via Ollama's OpenAI-compatible API) grounded in that context via `SYSTEM_PROMPT`, which enforces inline `[n]` citations, calls out required permissions/capabilities, and asks a clarifying question when the desktop/mobile target or Tauri major version is ambiguous. `search`/`/api/search` stop after step 2 (retrieval only, no LLM call).

**Serving**: `api/main.py` wires CORS + a `lifespan` (warms the embedding model, inits/flushes telemetry) + `api/routes.py` (FastAPI) on top of the same `ChromaStore`/`stream_chat` used by the CLI; `/api/chat` streams via Server-Sent Events (`sources` → `token`* → `done`, the last carrying a trace id). The `web/` (Vite + React) `Chat.tsx` and `Search.tsx` components consume these endpoints directly; `Chat.tsx` also posts a rating to `/api/feedback` when you click 👍/👎 on a reply.

## Tiers

- **Tier 1**: guide/concept docs, the JS/TS API reference, and every plugin's
  permissions schema. Covers everyday app and plugin development.
- **Tier 2**: adds the `tauri` crate's Rust API docs (a ~200-page docs.rs
  crawl) for backend/plugin authors working in Rust.

## Evaluation

```bash
# Score the hand-written golden set (retrieval hit_rate/mrr/precision@k +
# LLM-judged faithfulness/answer_relevancy); saves a report under data/eval_runs/
uv run --package tauri-assistant tauri-assistant eval

# Pull real chat traces out of Langfuse and print pasteable GoldenItem candidates
# (requires telemetry to be configured -- see above)
uv run --package tauri-assistant tauri-assistant eval harvest --feedback down --days 7
```

`eval/dataset.py`'s `GOLDEN_SET` is hand-verified against the live corpus,
so `eval harvest` never auto-appends to it -- promotion stays a human edit.
The intended loop: harvest `--feedback down` traces (the ones a real user
rated unhelpful), use `tauri-assistant search` to find the heading_path that
should have won, fill in `expected_matches`, and paste the result into
`GOLDEN_SET` as a regression case. `eval` and the live chat path share the
same `rag/chat.py:prepare_turn` helper (condense + retrieve + prompt
assembly), so a harvested multi-turn conversation replays exactly as it
happened live.
