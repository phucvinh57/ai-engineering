# 19 — Evaluation and Monitoring

> **Source:** *Agentic Design Patterns* — Chapter 19: Evaluation and Monitoring (PDF pp. 304–322 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Agents are **probabilistic**, so classic pass/fail tests aren't enough. You need continuous, mostly *external* measurement of **quality, latency, cost, trajectory, compliance and drift** — in development (evals) and in production (monitoring). Chapter 11 covers the agent tracking its own goals; this chapter covers *you* measuring the agent.

## What to measure / use cases

- **Live performance tracking** – accuracy, resolution rate, latency, resource use.
- **A/B testing** of agent versions, prompts, planning strategies.
- **Compliance and safety audits** – automated reports, KPIs, alerts (reviewed by a human or another agent).
- **AI "contracts"** for enterprise governance: codified objectives, rules and controls for delegated tasks.
- **Drift detection** – quality degrades as inputs or environment change.
- **Anomaly detection** – odd actions signalling bugs, attacks or unwanted emergent behaviour.
- **Learning-progress assessment** – learning curves and generalisation.

## Metrics and techniques

### Response accuracy
Exact match (`agent.strip().lower() == expected`) is trivially simple and **wrong for paraphrases** ("The capital of France is Paris." ≠ "Paris is the capital of France." → score 0). Better options:

- string similarity (Levenshtein, Jaccard), keyword checks;
- **semantic similarity** (cosine similarity of embeddings);
- **LLM-as-a-Judge**;
- **RAG-specific** metrics: *faithfulness* (answer supported by retrieved context) and *relevance*.

### Latency monitoring
Don't just print it — persist it: JSON logs, time-series DBs (InfluxDB, Prometheus), warehouses (BigQuery, Snowflake, Postgres), or observability platforms (Datadog, Splunk, Grafana).

### Token usage
Cost is driven by input + output tokens; track per interaction (use the provider's real tokenizer/usage fields), find prompt bloat, and inform routing (Ch. 16).

### LLM-as-a-Judge
A rubric prompt scores a subjective quality. The book's example judges **legal survey questions** on five 1–5 criteria — clarity & precision, neutrality & bias, relevance & focus, completeness, audience appropriateness — and returns JSON: `overall_score`, `rationale`, `detailed_feedback`, `concerns`, `recommended_action`. Tips: low temperature, JSON response mode, handle blocked/empty responses and JSON decode errors, test with good, biased and vague examples.

### Comparison of evaluation methods

| Method | Strength | Weakness |
|---|---|---|
| **Human** | Captures subtle behaviour | Slow, costly, hard to scale |
| **LLM-as-a-Judge** | Consistent, scalable | May overlook intermediate steps; bounded by the judge's ability |
| **Automated metrics** | Objective, scalable | May miss the full picture |

## Trajectory evaluation

Judge not only the final answer but the **sequence of steps** (tool choice, strategy, efficiency). Compare the actual trajectory to a ground-truth one:

| Match type | Meaning |
|---|---|
| **Exact** | Identical to the ideal sequence (high-stakes). |
| **In-order** | Right actions in order; extra steps allowed. |
| **Any-order** | Right actions, any order; extras allowed. |
| **Precision** | Fraction of predicted actions that are relevant. |
| **Recall** | Fraction of essential actions captured. |
| **Single-tool** | A specific action was used. |

Example ideal trajectory for a product query: determine intent → search database tool → review results → generate report.

## Google ADK evaluation

- **Test files** (JSON): one session, several turns — user query, expected tool-use trajectory, intermediate responses, final response (e.g. "Turn off device_2 in the Bedroom" → `set_device_info(location=Bedroom, device_id=device_2, status=OFF)` → "I have set the device_2 status to off."). Best for **unit tests**; optional `test_config.json` for criteria.
- **Evalset files:** many multi-turn sessions ("evals") for **integration tests** (e.g. roll a die twice, then check primality).
- **Run via:** `adk web` (interactive; save sessions into eval sets), **pytest** (`AgentEvaluator.evaluate`), or **`adk eval`** CLI in CI/CD.

## Multi-agent evaluation

Ask team-level questions: Do agents **cooperate** (correct dates passed from flight to hotel agent)? Did they **make and follow a plan** (no booking a hotel before the flight; no endless loops)? Is the **right agent chosen** (Weather Agent vs. generic knowledge)? Does **adding an agent help** or create conflict and slowdown (scalability)? Environments change, so test cases must evolve.

## From agents to "contractors"

Proposed in Google's *Agent Companion*: replace brittle, under-specified prompts with formal **contracts** — four pillars:

1. **Formalised contract** – precise deliverables, sources, scope, cost/time; objectively verifiable ("20-page PDF, five visualisations, Q1 2025 vs Q1 2024, risk assessment…").
2. **Negotiation and feedback lifecycle** – agent flags ambiguity or inaccessible sources *before* work starts.
3. **Quality-focused iterative execution** – self-validate against unit tests/metrics; submit only what passes.
4. **Hierarchical decomposition via subcontracts** – a primary contractor splits work into sub-contracts for specialist agents.

## Practical tips

- Build an **eval set early** from real traces; run it on every prompt/model change (regression tests).
- Combine cheap automated metrics with LLM judges, and calibrate the judge against human labels.
- Trace every run (inputs, tool calls, tokens, latency) so failures can be replayed.
- Monitor drift and set alerts; feed findings back into prompts, routing and guardrails (Ch. 18).

## When to use

Any production agent where reliability matters; when comparing versions/models; in regulated or high-stakes domains; when performance may drift; when judging trajectories or subjective quality.

## Key takeaways

- Evaluate outputs **and** trajectories, offline (evals) **and** online (monitoring).
- Exact-match is too crude; use semantic metrics and LLM-as-a-Judge with clear rubrics.
- Track latency and tokens persistently; A/B test and watch for drift/anomalies.
- Multi-agent systems need team-level evaluation; formal contracts point to more accountable agents.

**Prev:** [18 — Guardrails / Safety Patterns](18-guardrails-safety-patterns.md) · **Next:** [20 — Prioritization](20-prioritization.md)
