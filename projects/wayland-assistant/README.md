# wayland-assistant

A retrieve-then-generate RAG chatbot over Wayland protocol and compositor
documentation: core Wayland, every `wayland-protocols` extension (stable,
staging, unstable, experimental), the `wlr-protocols` compositor extensions
(sway/hyprland/river), the Wayland Book, and the wlroots API docs.

Uses the OpenAI SDK (`gpt-4o` + `text-embedding-3-small`), Chroma as an
embedded vector store, FastAPI for the backend, and a Vite + React frontend.

## Setup

From the repo root:

```bash
uv sync
cp projects/wayland-assistant/.env.example projects/wayland-assistant/.env
```

## Usage

```bash
# Clone protocol repos + fetch Book/Doxygen pages (tier 1 = core value; tier 2 adds long tail)
uv run --package wayland-assistant wl-assistant fetch --tier 1

# Chunk, embed, and store into Chroma
uv run --package wayland-assistant wl-assistant ingest --tier 1

# Chunk/doc counts by source
uv run --package wayland-assistant wl-assistant stats

# Pure retrieval, no LLM
uv run --package wayland-assistant wl-assistant search "how does xdg-shell handle window resizing"

# API server
uv run --package wayland-assistant wl-assistant serve
```

Frontend:

```bash
cd projects/wayland-assistant/frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `localhost:8000`.

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        A1[wayland/wayland-protocols/\nwlr-protocols repos]
        A2[Wayland Book\nHTML pages]
        A3[wlroots Doxygen\nHTML pages]
    end

    subgraph Ingest pipeline
        B1[repos.sync_repos\nclone/pull + list XML by tier]
        B2[protocol_xml.parse_protocol_file\none InterfaceDoc per interface]
        B3[book.fetch_book_pages\nHTML to markdown]
        B4[doxygen.fetch_doxygen_pages\nHTML to markdown, threaded]
        B5[manifest\ncontent-hash cache, data/raw + data/manifest.jsonl]
        C1[chunker.chunk_interface /\nchunk_markdown\nheading-aware, token-bounded]
        D1[embedder.embed_texts\nOpenAI text-embedding-3-small]
        E1[(ChromaStore\ndata/chroma, upsert by content_hash)]
    end

    A1 --> B1 --> B2
    A2 --> B3
    A3 --> B4
    B2 --> B5
    B3 --> B5
    B4 --> B5
    B2 --> C1
    B3 --> C1
    B4 --> C1
    C1 --> D1 --> E1

    subgraph Query pipeline
        F1[retriever.condense_query\nfold chat history into standalone question]
        F2[embedder.embed_query]
        F3[ChromaStore.query\ncosine top_k, optional source/maturity filter]
        F4[retriever.assemble_context\nnumbered context blocks]
        F5[chat.stream_chat\nGPT-4o, streamed + cited]
    end

    E1 --> F3
    F1 --> F2 --> F3 --> F4 --> F5

    subgraph Interfaces
        G1[cli.py\nfetch / ingest / search / stats / serve]
        G2[api/routes.py\nFastAPI: /api/chat (SSE), /search, /stats, /health]
        G3[frontend\nVite + React: Chat.tsx, Search.tsx]
    end

    G1 -.-> B1
    G1 -.-> C1
    G1 -.-> F3
    G2 --> F5
    G2 --> F3
    G3 --> G2
```

**Ingest** (`wl-assistant fetch` / `ingest`, orchestrated by `ingest/pipeline.py`):

1. **Fetch** — `sources/repos.py` shallow-clones/pulls the three protocol git repos and lists their `*.xml` files by tier/maturity; `sources/book.py` and `sources/doxygen.py` fetch and convert the Book and wlroots HTML pages to markdown (retried via `tenacity`, Doxygen pages fetched concurrently). Raw markdown is cached under `data/raw/`, and every fetched unit is recorded in `data/manifest.jsonl` (`sources/manifest.py`) keyed by a content hash, so re-running `fetch` is incremental.
2. **Parse** — `sources/protocol_xml.py` walks each protocol XML file into one `InterfaceDoc` per `<interface>`, carrying its requests/events/enums as structured data (no HTML scraping needed — the protocol docs are already structured).
3. **Chunk** — `ingest/chunker.py` turns each `InterfaceDoc` into one chunk (or several, if it exceeds `chunk_max_tokens`), and each Book/Doxygen page into one chunk per leaf markdown heading. Oversized sections are token-window-split with overlap. Every chunk gets a breadcrumb prefix (e.g. `wayland-protocols/stable > xdg-shell > xdg_toplevel`) so it reads standalone out of context.
4. **Embed + store** — `ingest/embedder.py` batches chunk text through the OpenAI embeddings API; `ingest/store.py` upserts vectors + text + metadata into a persistent Chroma collection (`data/chroma/`), keyed by content hash for idempotent re-ingestion.

**Query** (`wl-assistant search`, or `/api/chat` / `/api/search`):

1. `rag/retriever.py` condenses the latest question against chat history into a standalone query (skipped on the first turn), embeds it, and queries Chroma for the top-k nearest chunks (optionally filtered by `source`/`maturity`).
2. Retrieved chunks are deduplicated and assembled into numbered context blocks (`rag/prompts.py`).
3. `rag/chat.py` streams a GPT-4o completion grounded in that context via `SYSTEM_PROMPT`, which enforces inline `[n]` citations, calls out protocol maturity, and asks a clarifying question when client-vs-compositor perspective is ambiguous. `search`/`/api/search` stop after step 2 (retrieval only, no LLM call).

**Serving**: `api/main.py` wires CORS + `api/routes.py` (FastAPI) on top of the same `ChromaStore`/`stream_chat` used by the CLI; `/api/chat` streams via Server-Sent Events (`sources` → `token`* → `done`). The `frontend/` (Vite + React) `Chat.tsx` and `Search.tsx` components consume these endpoints directly.

## Tiers

- **Tier 1**: core `wayland.xml`, `wayland-protocols/{stable,staging}`,
  `wlr-protocols/unstable`, and the Wayland Book's preface. Covers everyday
  compositor/client development.
- **Tier 2**: adds `wayland-protocols/{unstable,experimental}`, the Book's
  Appendix B/C (client/server C API reference), and the wlroots Doxygen site.
