# Design decisions

Why the ingest pipeline is shaped the way it is. Each entry records the decision,
the evidence behind it, and what was rejected — so a future change can tell whether
it is overturning a measurement or just a preference.

Measurements were taken on 2026-09-16 against the cloned corpus in `data/repos/`
using `all-MiniLM-L6-v2`'s real tokenizer.

---

## 1. Chunk on heading sections, bounded on both ends

**Decision.** The default strategy splits markdown on `h2`–`h4`, then merges stubs
into siblings and splits oversized sections down. `fixed` and `whole` remain
available as measured baselines, not as realistic defaults.

**Evidence.** Token distribution over the 161 English pages in
`tauri-docs/src/content/docs`:

| Unit | p50 | p75 | p90 | max | % over 256 tok |
|---|---|---|---|---|---|
| Whole page | 1487 | 2540 | 4328 | 12718 | **97%** |
| Heading section (h2–h4) | 186 | 357 | 592 | 5148 | 35% |

Three things follow:

- **Whole-page chunking is disqualified**, not merely worse. `all-MiniLM-L6-v2`
  truncates at 256 tokens, so 97% of pages would be silently cut — roughly 87% of a
  median page discarded with no error raised anywhere.
- **Heading sections are already close to the right unit.** Starlight docs are
  written so each `##`/`###` answers one question, and there are 7.3 per page.
- **They still need bounding on both ends.** 27% are under 50 words (a heading plus
  a one-line pointer, nearly contentless once embedded); 35% exceed the cap.

Post-merge, tauri-docs' under-64-token share drops from 27% to **11.7%**. The
record-based sources sit at 30–41% short chunks, and that is correct: those are
single-chunk documents (one TOML permission, one TS symbol) where merging two
unrelated records would actively harm retrieval.

**Rejected.** Fixed-size windows as the default — they sever code fences from the
prose introducing them, which retrieves badly for both halves. Kept as `fixed` so
the claim stays falsifiable rather than assumed.

## 2. Size everything with the embedding model's own tokenizer

**Decision.** `ingest/chunking/tokens.py` derives the budget from the model, as
`min(settings.chunking.max_tokens, the model's real limit)`. Nothing is hardcoded.

**Evidence.** Two traps, both hit during implementation:

- `all-MiniLM-L6-v2`'s tokenizer advertises `model_max_length: 512`, but
  sentence-transformers truncates at `max_seq_length: 256` from
  `sentence_bert_config.json`. Trusting the tokenizer's own number would have
  halved the usable budget — silently. So the counter reads
  `sentence_bert_config.json` via `hf_hub_download`.
- This corpus runs **2.12 tokens/word, 2.80 inside code fences**, far above the ~1.3
  rule of thumb, because it is dense with identifiers and paths. Any character- or
  word-based sizing under-counts by roughly 2x.

`tiktoken` is a dependency already but is **wrong here** — it is OpenAI BPE, not the
embedding model's WordPiece.

**Consequence.** Swapping the embedding model automatically re-sizes chunks. The
pipeline additionally asserts no chunk exceeds the real limit before embedding, so
this trap cannot silently reappear.

## 3. Post-processors wrap any chunker, rather than each strategy re-implementing bounds

**Decision.** Size bounds, breadcrumb prefixing and parent linkage live in
`ingest/chunking/postprocess.py` and compose around *any* `Chunker`. A strategy only
decides **where to cut**.

**Why.** This is the mechanism behind the "swap strategy without touching surrounding
logic" requirement. Storage and retrieval depend on invariants (every chunk fits the
model; every chunk has a breadcrumb and a `parent_id`). Enforcing them once means a
new strategy inherits all of them, and a parametrized contract test proves all four
current strategies satisfy what storage assumes.

**Ordering is load-bearing:** `MergeUndersized` → `AttachParent` → `EnforceBudget`.

- `AttachParent` must run before any further cutting, because the parent *is* the
  whole section — its identity has to be captured while the chunk still holds it.
- Prefixing and splitting are deliberately **one step**. An earlier version prefixed
  after the budget check, so the breadcrumb's tokens pushed chunks back over the
  limit. `EnforceBudget` charges the trail up front and drops it entirely when it
  would cost more than half the budget (deeply nested Rust paths can).

## 4. Parent text goes to SQLite, not Chroma metadata

**Decision.** Small-to-big retrieval stores `parent_id` in Chroma but the parent
*text* in `catalog.db`'s `parent_section` table.

**Why.** Parent text in metadata is duplicated into every child chunk, inflating the
collection by roughly the size of the corpus a second time — while being unsearchable
and untyped. Chroma holds what it queries; SQLite holds what it only ever looks up.

## 5. The index is a pure function of its inputs, so hash them

**Decision.** `index = f(corpus_revision, chunking_config, embedding_config)`. Those
inputs are hashed into a 10-char fingerprint that names the collection.

**Why this one idea solves three separate requirements.**

- **Comparison:** different config → different fingerprint → different collection.
  Variants cannot contaminate each other, and can be queried side by side.
- **Incremental ingest:** same config → same collection → a document-level diff is
  meaningful.
- **Measurement:** every cost and quality metric has an obvious key.

**What is deliberately excluded from the fingerprint:** batch size, device, log level.
They do not change the vectors, and including them would orphan the whole index on an
unrelated edit.

**Constraint discovered:** chromadb 1.5.9 requires names of 3–512 chars from
`[a-zA-Z0-9._-]`, starting and ending alphanumeric. Both `BAAI/bge-m3` and
`sentence-transformers/all-MiniLM-L6-v2` contain an illegal `/`, so `slug()` rewrites
them and the fingerprint suffix restores uniqueness after slugging.

## 6. The manifest is derived from Chroma, not stored beside it

**Decision.** Every chunk carries `doc_hash` in its metadata, so
`db.indexed_documents()` reconstructs `document_id -> hash` by reading Chroma.

**Why.** A separately maintained manifest drifts the moment a run dies mid-write, and
the failure is silent — documents look ingested when they are not. Deriving it costs
one `get(include=["metadatas"])` over a few thousand chunks, which is cheap, and it
cannot disagree with reality.

**Related invariant:** old chunks of a changed document are deleted **before** the new
ones are upserted. Re-chunking can produce *fewer* chunks, and with content-addressed
chunk ids the stale extras would otherwise linger forever as orphans. This ordering is
covered by a test that was verified by sabotage — removing the delete makes it fail.

## 7. Chroma metadata omits absent keys rather than writing `None`

**Decision.** `to_metadata()` skips falsy optional keys (`parent_id`, `url`, `plugin`,
`module`, `crate`) instead of setting them to `None`.

**Why.** chromadb 1.5.9 raises `TypeError: Cannot convert Python object to
MetadataValue` on `None`. Since `Chunk.parent_id` is `str | None`, the naive mapper
fails on **every top-level chunk**. There is a regression test that asserts chromadb
really does reject `None`, so the test fails loudly if that behaviour ever changes
rather than quietly protecting against nothing.

## 8. Cache embeddings by `(model, sha256(text))`

**Decision.** `catalog.db`'s `embedding_cache`, with vectors packed as
`array.array("f")` bytes. The model is loaded lazily, so a fully cached run never
loads it at all.

**Why.** bge-m3 on CPU over ~5,100 chunks is roughly 6–18 minutes per pass; a
6-variant sweep without caching is over an hour of pure recompute. Content addressing
is what makes it work across variants: record-based sources are unaffected by prose
chunking parameters, so they are identical between strategies. Measured — a variant
differing only in `min_tokens` hit **514 cache hits / 2 misses**.

## 9. A hand-written fence-aware splitter instead of `langchain-text-splitters`

**Decision.** `ingest/chunking/textsplit.py`, replacing the dependency named in the
plan. This is a deliberate deviation from the approved plan.

**Why.** The off-the-shelf recursive splitter cuts through code fences. In a corpus
that is prose wrapped around Rust/TS/shell examples, that is the single worst place to
cut. Here fences are atomic: the packer moves whole fences between pieces, and only
cuts *inside* one when a single fence exceeds the budget alone — then repeating the
opening info string so the language tag survives into each part.

The cascade is paragraph → sentence → line → whitespace → **character**. The last step
is not defensive padding: `updater.mdx` contains a 286-character run of `-` as a table
rule, which is one whitespace-delimited "word" costing 286 tokens. Without a
character-level chop that piece reaches the embedder and is silently truncated — the
exact failure this layer exists to prevent. Full-corpus result: **0 chunks over
budget, max exactly 256**.

## 10. MDX stripping is fence-aware, line-wise

**Decision.** `strip_mdx` walks lines through `iter_lines_outside_fences` instead of
running regexes over the whole page.

**Why.** This fixed a real corpus bug, not a hypothetical one. A page-wide regex
gutted `<Wix>`/`<Fragment>`/`<DirectoryRef>` inside a **WiX XML code fence** in
`windows-installer.mdx`, and Android XML in `mobile-multiwindow.mdx` — JSX and XML are
indistinguishable to a regex, and the difference is only which fence you are in. The
same primitive protects heading detection, since `#` is a comment in shell and Python.

Multi-line `<CommandTabs npm="..." yarn="...">` tags are **rendered, not dropped** —
their attributes hold the install commands, which are among the highest-value content
on a page.

## 11. Document ids are deduplicated in one place

**Decision.** `dedupe_document_ids()` in the pipeline, applied to every source.

**Why.** Document id drives the incremental diff, so a collision means one document
silently shadows another on every run. Two real causes were fixed at the source: the
JS parser read `static` as a symbol name, and the Rust parser collided across `impl`
blocks (now `app::AppHandle::run_on_main_thread`). But `cfg`-gated duplicates are
genuinely ambiguous in the source, so uniqueness is enforced as a **pipeline
invariant** rather than trusted to each of four parsers independently.

## 12. Ground truth must be chunk-agnostic

**Decision (design only — `eval/` is not built).** `eval_run` is shaped for it, and
golden items must be expressed as `question -> (document_id, heading_path substring)`.

**Why it is recorded now.** Expressing ground truth as chunk ids would invalidate the
entire dataset the first time two chunkers are compared — which is the whole purpose of
the harness. This is cheap to get right up front and painful to retrofit, so it is
written down before the dataset exists.

---

## Open items

- **`eval/` is not implemented.** The cost side of measurement works (chunk counts,
  token distribution, embed seconds, cache hit rate, ingest history). The quality side
  — golden set, Hit Rate/MRR/Recall@k, sweep runner — does not exist yet.
- **`.env` pins `all-MiniLM-L6-v2`**, which correctly overrides the `BAAI/bge-m3` code
  default. All verification above ran on MiniLM. Switching costs a ~2.2GB download and
  buys an 8192-token budget, which would change nearly every decision's numbers above
  (though not their direction).
