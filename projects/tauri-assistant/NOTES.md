# Prior implementation — architecture notes

The `src/`, `tests/`, and `web/` implementation was removed on 2026-09-16 for a
from-scratch rewrite. This file summarizes the previous design as a starting
point / reference; none of the code exists anymore (see `git log` on the
removed paths — everything up to this point is still in history if you want
to look something up directly). `pyproject.toml`, `README.md`,
`.env.example`, and `data/` (cloned repos, fetched docs, the Chroma DB, past
eval runs) were left in place.

## What it was

A RAG chatbot answering questions about the Tauri app framework (Rust
backend, JS/TS `@tauri-apps/api`, plugin ecosystem, permissions/capabilities
model), with a FastAPI backend, a React chat/search UI, and a CLI for
ingestion and evaluation.

## Pipeline: fetch -> ingest -> serve

**Sources** (`sources/`) — one parser per doc source, each reading structured
data directly rather than scraping rendered HTML where possible:
- `repos.py` — shallow git clone/pull of `tauri-docs`, `tauri`, and
  `plugins-workspace`.
- `guide.py` — reads `tauri-docs`' MDX guide pages directly off disk, strips
  frontmatter/imports/JSX.
- `js_api.py` — regex-segments `@tauri-apps/api`'s prettier-formatted TS
  source into one record per top-level exported symbol (handles both inline
  `export function foo` and trailing `export { foo, bar }` forms), pairing
  each with its leading `/** ... */` JSDoc block.
- `permissions.py` — parses each plugin's `permissions/*.toml` (TOML, no
  scraping) into permission / default / set records.
- `rust_api.py` — the one source with no local clone: crawls docs.rs
  rustdoc HTML for the `tauri` crate root and every linked item page,
  converts to Markdown via `markdownify`. Gated behind "tier 2" since it's
  a live crawl (tier 1 = guide + JS API + permissions only).
- `manifest.py` — a JSONL append-log of `(source, identifier, content_hash,
  fetched_at)` so re-fetching is incremental and `stats`/`fetch` can report
  what's new.

**Chunking** (`ingest/chunker.py`) — one chunk per JS symbol / permission;
guide and Rust API markdown split per leaf heading section (via a
heading-stack parser), then token-windowed with overlap only if a
section/symbol is unusually large. Every chunk is prefixed with a breadcrumb
(`"@tauri-apps/api > event > listen"`, `"fs plugin > permissions >
allow-read-file"`) so it reads standalone out of context. Chunk id = sha256
of its final text, used both for incremental upsert and cross-request dedup.

**Embedding + storage** (`ingest/embedder.py`, `ingest/store.py`) — local
sentence-transformers embeddings (`all-MiniLM-L6-v2` by default) via
LangChain's `HuggingFaceEmbeddings`, stored in a persistent Chroma collection
(cosine space) via `langchain-chroma`. Upsert is keyed by content hash so
re-ingesting is idempotent; query returns `(text, metadata, distance)` with
metadata carrying `source` / `heading_path` / `url` / `chunk_index`.

**Retrieval + chat** (`rag/`):
- `retriever.py` — embed the query, Chroma similarity search, dedup by exact
  text, convert distance -> score (`1 - distance`).
- `prompts.py` — one shared system prompt (cite `[1]`/`[2]` inline, never
  invent a code sample, don't blur near-duplicate permission blocks, call
  out when a capability/permission is required, mention both Rust- and
  JS-side APIs when both apply, ask a clarifying question if v1-vs-v2 or
  desktop-vs-mobile is ambiguous) plus a query-condensation prompt for
  multi-turn follow-ups.
- `chat.py` — `prepare_turn()` (condense -> retrieve -> assemble context ->
  build messages) is the one function shared by both the live SSE chat path
  and the offline eval runner, specifically so both score/exercise
  byte-identical prompts. `stream_chat()` wraps it and streams
  tokens/reasoning from an OpenAI-compatible endpoint (pointed at local
  Ollama by default).

**API** (`api/`) — FastAPI app; `/api/chat` is SSE (`sources` -> `thinking`*
-> `token`* -> `done` events, trace id returned both as a response header and
in the `done` event so a client can rate a response that errored before
completion), plus `/api/search` (pure retrieval, no LLM), `/api/feedback`
(thumbs up/down -> Langfuse score), `/api/stats`, `/api/health`.

**CLI** (`cli.py`, Typer) — `fetch [--tier]`, `ingest [--tier]`, `search
<query>`, `stats`, `eval` (score the golden set), `eval harvest` (pull real
traces from Langfuse into candidate golden items), `serve`.

**Web UI** (`web/`) — Vite + React + TS, two tabs (Chat, Search) against the
API above; `session.ts` mints a per-tab session id and a persistent anonymous
user id (localStorage/sessionStorage, never a real identity) purely to group
Langfuse traces.

## Evaluation (`eval/`)

A hand-curated `GOLDEN_SET` (`dataset.py`) of question -> expected
`heading_path`/`url` substrings, each verified against the live corpus via
`tauri-assistant search` rather than guessed. `runner.py` runs every item
through the *same* `prepare_turn()` the live path uses, then scores:
- Retrieval: Hit Rate@k, MRR, Precision@k (`metrics.py`) — deliberately not
  NDCG (this is single-relevance QA, not graded ranking).
- Generation: Faithfulness and Answer Relevancy, LLM-judged by a *different*,
  larger model (`eval_judge_model`) than the one under test, so the system
  never grades its own homework. Judge prompts ask for reasoning before a
  score and are parsed leniently (regex fallback) since small local judge
  models can truncate mid-JSON.

`harvest.py` closes the loop: pulls real chat traces + `user_feedback` scores
out of Langfuse, and only *suggests* `expected_matches` from thumbs-up traces
(seeding them from a thumbs-down trace would bake the failure in as
"expected"). Promotion from harvested candidate to `GOLDEN_SET` stays a
manual, human-reviewed edit.

## Telemetry (`telemetry.py`)

Langfuse, and the only module allowed to import it — every other module
degrades to a no-op automatically when `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`
aren't set (`Settings.telemetry_active`), never checked ad hoc at call sites.
The one hazard worth remembering if you re-implement streaming + tracing
together: `/api/chat` streams through a *sync* generator that Starlette
drives via `anyio.to_thread.run_sync`, one `yield` at a time, and each call
gets its own copy of the contextvar `Context`. A `with
start_as_current_span():` spanning a `yield` attaches in one copy and
detaches in another — children silently orphan into their own traces. The
previous implementation avoided this entirely by never using OTel ambient
context: spans were plain objects threaded explicitly through function
parameters and ended manually in a `finally`.

## Config (`config.py`)

Single `pydantic-settings` `Settings`, `.env`-backed, covering model/endpoint
config (chat + embedding + eval-judge models, all pointed at a local
OpenAI-compatible endpoint by default), data paths, chunking/retrieval
knobs, CORS, and the Langfuse block.

## Dependencies that mattered

FastAPI/uvicorn, `openai` (OpenAI-compatible client against local Ollama),
`chromadb` + `langchain-chroma` + `langchain-huggingface` (vector store +
local embeddings), `sentence-transformers`, `tiktoken` (chunk sizing),
`gitpython` (repo sync), `httpx`/`beautifulsoup4`/`lxml`/`markdownify`
(docs.rs crawl), `tenacity` (retry), `typer` (CLI), `langfuse` (telemetry).
