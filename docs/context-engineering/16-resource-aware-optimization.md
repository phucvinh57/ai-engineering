# 16 — Resource-Aware Optimization

> **Source:** *Agentic Design Patterns* — Chapter 16: Resource-Aware Optimization (PDF pp. 244–259 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Agents should **monitor and manage cost, latency and compute** — not just sequence actions. Use a cheap/fast model or path for easy work, spend more only when the task is hard or the stakes are high, and **fall back** gracefully when a preferred model is unavailable.

## Why it differs from planning

Planning decides *what steps*. Resource-aware optimisation decides *how much to spend on each step* within a budget: accurate-but-expensive vs. fast-but-cheap, extra compute for a polished answer vs. a quick rough one.

Example: a quick preliminary report → small fast model. A critical investment forecast with a bigger budget → powerful slow model.

## Use cases

- **Cost-optimised LLM use** (small model for simple queries, large for complex).
- **Latency-sensitive systems** (faster, less exhaustive reasoning path).
- **Energy efficiency** on edge devices.
- **Fallback for reliability** when the primary model is overloaded or rate-limited.
- **Data usage:** fetch summaries instead of full datasets.
- **Adaptive task allocation** in multi-agent systems based on load.

## Building blocks

### Router agent
Classifies each query and dispatches it (see Routing, Ch. 2):
- Simple heuristics (e.g. query < 20 words → Flash, else Pro).
- Better: an LLM or ML classifier judging complexity; improve via prompt tuning or fine-tuning on (query, best-model) pairs.

Typical split in a hierarchical travel planner: **strong model plans**; **cheap model executes** the many simple tool calls (flight prices, hotel lookup, reviews).

### Critique agent
Reviews answers to (1) trigger self-correction, (2) track accuracy/relevance for monitoring, (3) feed learning signals back to the router. It indirectly saves money by revealing bad routing (simple → Pro is wasteful; complex → Flash gives poor results). Its prompt should define an evaluator role, what to focus on, and demand **constructive** feedback listing strengths and weaknesses.

### Three-way classifier (OpenAI example)
Classify the prompt as `simple`, `reasoning` or `internet_search`; return JSON like `{"classification": "simple"}`.
- `simple` → cheap model directly.
- `reasoning` → stronger model.
- `internet_search` → call Google Custom Search, pass results as context to the model.

### OpenRouter
One API in front of hundreds of models. Two routing modes:
- **Auto selection:** `"model": "openrouter/auto"` picks a model based on the prompt.
- **Sequential fallback:** `"models": ["primary", "backup", ...]` — tries each in order on unavailability, rate limiting or content filtering; you're billed for the model that succeeded.

## Wider menu of optimisations

| Technique | Idea |
|---|---|
| Dynamic model switching | Match model size to task difficulty. |
| Adaptive tool selection | Choose tools by cost, latency, execution time. |
| **Contextual pruning & summarisation** | Keep only relevant history to cut prompt tokens and inference cost. |
| Proactive resource prediction | Forecast workload to allocate ahead of time. |
| Cost-sensitive exploration | Count communication cost between agents. |
| Energy-efficient deployment | Extend battery life / lower running cost. |
| Parallel/distributed awareness | Spread work across machines. |
| Learned allocation policies | Improve resource decisions from feedback. |
| Graceful degradation & fallback | Keep essential functionality under severe limits. |
| Prioritisation of critical tasks | Spend scarce resources on what matters (Ch. 20). |

## Practical tips

- Measure first: log tokens, latency and cost per step and per model.
- Combine **routing + caching + context trimming**; often the biggest savings come from sending less context.
- Always define a fallback chain, and test behaviour when the primary model is throttled.

## When to use

Strict API/compute budgets, latency-critical apps, resource-constrained hardware, or workflows whose steps have very different resource needs.

## Key takeaways

- Trade quality against cost/latency deliberately, per task.
- Router + critique agents implement dynamic model selection that improves over time.
- Fallback chains keep the service alive; pruning/summarising context cuts tokens.

**Prev:** [15 — Inter-Agent Communication (A2A)](15-inter-agent-communication-a2a.md) · **Next:** [17 — Reasoning Techniques](17-reasoning-techniques.md)
