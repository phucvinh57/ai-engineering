# Langfuse (self-hosted)

LLM observability backend for `tauri-assistant`'s telemetry (see
`projects/tauri-assistant/src/tauri_assistant/telemetry.py`). Six containers:
`langfuse-web` (UI + API), `langfuse-worker` (async ingestion), Postgres (app
data), ClickHouse (traces/observations/scores), Redis (queue/cache), and
MinIO (S3-compatible blob storage for event/media uploads).

## Setup

```bash
cp .env.example .env
# Fill in every blank secret with: openssl rand -hex 32
# ENCRYPTION_KEY must be exactly 64 hex characters.
docker compose up -d
```

First boot runs Postgres + ClickHouse migrations -- give it 30-60s, then
open http://localhost:3000. `LANGFUSE_INIT_*` in `.env` auto-provisions a
project with the deterministic keys `pk-lf-local-dev` / `sk-lf-local-dev`
(as shipped in `.env.example`), so there's no click-through signup: paste
those two values straight into `projects/tauri-assistant/.env` as
`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`, with `LANGFUSE_HOST=http://localhost:3000`.

## Resource cost

ClickHouse wants roughly 2 GB RAM idle, which isn't free on a laptop already
running Ollama and a local embedding model. If that's too much, use
[Langfuse Cloud](https://cloud.langfuse.com) instead: skip this
docker-compose entirely, sign up there, and set
`LANGFUSE_HOST=https://cloud.langfuse.com` plus its own key pair in
`projects/tauri-assistant/.env`. The application code doesn't change either
way.

**Privacy trade-off:** self-hosted, every prompt and retrieved doc chunk
stays in your own Postgres/ClickHouse. On Cloud, that same data -- real
questions users asked, and the doc snippets retrieved to answer them --
leaves your machine and goes to a third party. `.env.example` in
`projects/tauri-assistant/` defaults to the self-hosted host for this
reason.

## The app must survive Langfuse being down

`tauri-assistant`'s telemetry is fire-and-forget: it never flushes
synchronously on a request, never blocks startup waiting on Langfuse (only
`LANGFUSE_DEBUG=true` triggers an `auth_check()`, and that's the one
deliberate exception), and every write swallows its own exceptions. Chat and
search work at normal speed whether this stack is up or down; you just lose
the trace for whatever happened while it was down.

## Stopping / resetting

```bash
docker compose stop          # keep data, stop containers
docker compose down          # remove containers, keep volumes
docker compose down -v       # also wipe all Langfuse data
```
