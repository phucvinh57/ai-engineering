# tauri-assistant

A RAG corpus builder over the [Tauri](https://tauri.app) framework's documentation,
source and plugin ecosystem. It reads four upstream sources off local git clones,
normalizes them into one document shape, chunks them with a swappable strategy, and
stores the result in Chroma.

Fetching and ingesting are actions on a small FastAPI service, not a CLI. A `/chat`
endpoint retrieves from the currently ingested collection and completes against an
OpenAI-compatible endpoint (Ollama by default); a web layer does not exist yet.

[DECISIONS.md](DECISIONS.md) records why the pipeline is shaped this way — the
measurements behind the chunking default, the token-budget traps, and the rejected
alternatives.

## Setup

```sh
uv sync
cp .env.example .env            # optional; every value has a default
uv run tauri-assistant          # starts the API on http://0.0.0.0:8000
```

The first ingest downloads the embedding model (bge-m3 is ~2.2GB). To use the much
smaller `all-MiniLM-L6-v2` instead, set `EMBEDDING_MODEL` — but see the note on its
256-token limit under [Chunking](#chunking).

## Usage

Fetch and ingest are triggered over HTTP and run in the background; each returns
`202` immediately and rejects a second trigger while one is already in flight
(`409`). Progress shows up in the server logs.

```sh
# Shallow-clone/pull tauri-docs, tauri, plugins-workspace
curl -X POST localhost:8000/fetch

# Chunk, embed and upsert. Incremental: unchanged documents are skipped entirely
curl -X POST localhost:8000/ingest -H 'content-type: application/json' -d '{}'
curl -X POST localhost:8000/ingest -d '{"source": ["tauri-docs"]}'   # one source
curl -X POST localhost:8000/ingest -d '{"full": true}'               # re-embed everything
```

## Chat

`/chat` retrieves from whatever collection matches the *current* config and source
shas (the same variant `/ingest` would build right now — see
[Comparing choices](#comparing-choices)) and streams a grounded reply from
`CHAT_BASE_URL`/`CHAT_MODEL`. It 409s if that variant hasn't been ingested yet.

```sh
curl -X POST localhost:8000/chat -H 'content-type: application/json' -d '{
  "messages": [{"role": "user", "content": "How do I call a Rust command from the frontend?"}]
}'
```

The response body is newline-delimited JSON: one `{"type": "sources", ...}` line with
the retrieved passages (`document_id`, `heading_path`, `url`, `score`), then any number
of `{"type": "delta", "text": ...}` lines as the model streams, then a final
`{"type": "done", "usage": ...}` (or `{"type": "error", ...}` if the chat backend
fails mid-stream). `messages` follows the OpenAI shape so multi-turn history can be
passed straight through; only the last (user) message is used as the retrieval query.

## Sources

| Source | Input | Unit | Documents |
|---|---|---|---|
| `tauri-docs` | 161 Starlight `.mdx` guide pages | page | 134 |
| `plugin-permissions` | 217 `permissions/*.toml` across 31 plugins | permission / set / command | 420 |
| `js-api` | `@tauri-apps/api` TypeScript + JSDoc | exported symbol or class method | 409 |
| `rust-api` | `///` doc comments in the workspace crates | item | 1986 |

Translated page trees (`zh-cn/`, `ja/`, …) are excluded by default: they duplicate the
English corpus with near-identical vectors that crowd out real answers. `blog/` and
`releases/` are excluded for staleness. Both are `CHUNKING_EXCLUDE_GLOBS`.

## Chunking

Measured on the English guide pages, with the model's own tokenizer:

| Unit | p50 tokens | p90 | max | over 256 |
|---|---|---|---|---|
| Whole page | 1487 | 4328 | 12718 | **97%** |
| Heading section | 186 | 592 | 5148 | 35% |

Two findings drive the default:

- **`all-MiniLM-L6-v2` truncates at 256 tokens**, not the 512 its tokenizer config
  advertises — sentence-transformers uses `max_seq_length` from
  `sentence_bert_config.json`. Past that, text is dropped with no error. Whole-page
  chunks would lose ~87% of a median page silently.
- **This corpus runs 2.12 tokens/word, and 2.80 inside code fences**, far above the
  usual ~1.3, because it is dense with identifiers, paths and code. Character- or
  word-based sizing under-counts by roughly 2x.

So chunks are **heading sections**, with the tails bounded: stubs merge into the next
sibling, oversized sections split without severing code fences. The budget comes from
the embedding model itself (`ingest/chunking/tokens.py`), so swapping models re-derives
it rather than silently overrunning.

### Swapping strategies

`Document` in, `Chunk` out — nothing upstream or downstream names a strategy:

```
sources/*  ->  Document  ->  Chunker (swappable)  ->  [Chunk]  ->  db  ->  Chroma
```

| Strategy | Behaviour |
|---|---|
| `heading` | Heading sections, code-fence aware. The default for prose. |
| `record` | Identity pass for pre-split sources (permissions, symbols, items). |
| `fixed` | Fixed token windows with overlap. A baseline: it cuts through fences. |
| `whole` | One chunk per document. A baseline. |

Size bounds, breadcrumb prefixing and parent linkage live in post-processors that wrap
*any* strategy (`ingest/chunking/postprocess.py`), so a new strategy only decides where
to cut and inherits every invariant the storage layer expects. Adding one is a module
under `strategies/` plus a line in the `CHUNKERS` registry.

## Comparing choices

The index is a pure function of `(corpus, chunking config, embedding config)`. Those
inputs are hashed into a **variant fingerprint** that names the Chroma collection, so:

- changing the chunker or embedding model writes to a **different collection** — two
  experiments can never contaminate each other, and both stay queryable for comparison.
  (This is also forced: MiniLM is 384-dimensional and bge-m3 is 1024.)
- leaving them alone writes to the **same collection**, so a repo update is a
  document-level diff rather than a rebuild.
- every cost figure recorded in `catalog.latest_runs` is keyed back to the exact config.

```sh
curl -X POST localhost:8000/ingest -d '{}'                       # current config
CHUNKING_STRATEGY=fixed uv run tauri-assistant                  # a second, isolated variant
```

Vectors are cached on `(model, sha256(text))` in `data/catalog.db`, so a variant sweep
re-embeds only what genuinely differs — in practice a 99% hit rate when only chunking
parameters move.

## Evaluating variants

Retrieval quality is scored against ground truth expressed as
`question -> (document_id, heading_path substring)` — **never chunk ids**, which change
whenever chunking does and would silently invalidate the dataset the moment you compared
two chunkers.

`eval/matrix.py` fixes four variants to compare (embedding model / strategy / max
tokens), holding the corpus (source git shas) constant across all of them:

| Label | Embedding model | Strategy | Max tokens |
|---|---|---|---|
| `bge-m3-heading-1024` | `BAAI/bge-m3` | `heading` | 1024 |
| `bge-m3-fixed-1024` | `BAAI/bge-m3` | `fixed` | 1024 |
| `bge-m3-heading-512` | `BAAI/bge-m3` | `heading` | 512 |
| `minilm-heading-256` | `all-MiniLM-L6-v2` | `heading` | 256 |

`eval/generate.py` samples chunks from the baseline collection, generates one
question per chunk with a local LLM (`EVAL_GENERATOR_MODEL`), and filters out
leaked/unanswerable/unretrievable questions before they land in
`evalset/questions.jsonl` (committed — this is a versioned asset, not derived
output). `eval/runner.py` uploads that set to a Langfuse dataset once, then runs one
[experiment](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk) per
variant — Hit Rate/MRR/Precision@k, retrieval latency, and context token cost — so
they compare side by side in the Langfuse UI, timestamped for tracking drift over
time as the upstream repos move.

```sh
uv run python -m tauri_assistant.eval matrix-ingest      # build the 4 collections
uv run python -m tauri_assistant.eval generate            # sample + generate + filter questions
uv run python -m tauri_assistant.eval verify               # drop questions no variant can retrieve
uv run python -m tauri_assistant.eval run                  # upload dataset, run 1 experiment/variant
```

Needs `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` set (see [Telemetry](#telemetry) and
`infra/langfuse/` at the repo root for a local, self-hosted stack).

## Layout

```
src/tauri_assistant/
├── settings.py              pydantic-settings groups: init > env > .env > config.toml
├── telemetry.py             Langfuse -- the only module that imports it
├── db.py                    Chroma, addressed by variant fingerprint
├── api/                     FastAPI app: fetch/ingest/chat routes
├── chat/                    retrieval + turn assembly + OpenAI-compatible completion
│   └── turn.py              prepare_turn() -- shared by /chat and eval/runner.py
├── eval/                    variant matrix, golden set, Langfuse experiment runner
├── sources/                 one normalizer per upstream source -> Document
└── ingest/
    ├── types.py             Document / Chunk -- the stable contract
    ├── variant.py           fingerprinting
    ├── catalog.py           SQLite: runs, parent sections, eval, embedding cache
    ├── embedding.py         cached embedder
    ├── pipeline.py          incremental ingest
    └── chunking/
        ├── tokens.py        budget derived from the embedding model
        ├── base.py          Chunker protocol + heading parser
        ├── textsplit.py     fence-aware splitting
        ├── postprocess.py   merge / parent / budget -- shared by all strategies
        └── strategies/
```

Chroma holds the `doc_hash` on every chunk, so the ingest manifest is derived from the
collection itself rather than tracked separately — nothing can drift out of sync if a
run dies partway. The SQLite catalog holds only what Chroma should not: parent section
texts, run history, eval results, and the embedding cache.

## Telemetry (optional)

Langfuse, disabled unless `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are set
(`telemetry.py` -- the only module that imports `langfuse`; every other module
degrades to a no-op automatically). When active, each `/chat` request gets one trace
(root span "chat", a "retrieve" child, a "chat" generation) with the trace id
returned in the `sources` and `done` events, and `eval/runner.py` runs each
variant's golden-set questions as a Langfuse experiment (see
[Evaluating variants](#evaluating-variants)). `infra/langfuse/` at the repo root has
a self-hosted docker-compose stack; Langfuse Cloud works too by pointing
`LANGFUSE_BASE_URL` at it instead.

## Tests

```sh
uv run pytest
```
