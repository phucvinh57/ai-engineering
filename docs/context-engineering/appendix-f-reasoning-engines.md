# Appendix F — Under the Hood: An Inside Look at Agents' Reasoning Engines

> **Source:** *Agentic Design Patterns* — Appendix F: Under the Hood: An Inside Look at the Agents' Reasoning Engines (PDF pp. 402–416 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite. Most of the appendix is verbatim model self-descriptions; this summary keeps the comparison and the conclusion.

## TL;DR

The author asked six LLMs — **Gemini, ChatGPT, Grok, Kimi, Claude, DeepSeek** — the same question: *"I understand you can reason, can you explain to me how you reason? Explain me step by step."* Their answers converge on a **consistent multi-stage pipeline**, which is exactly why an LLM works as the "planner" inside an agent.

## The shared pipeline

1. **Deconstruct the prompt** – identify the task, key concepts, constraints and the user's intent.
2. **Retrieve / activate knowledge** – not a database lookup but pattern activation learned in training (Transformer attention connects related concepts).
3. **Choose a strategy** – e.g. deduction, induction, causal or analogical reasoning; decide between direct computation and something cleverer.
4. **Think step by step** – a chain-of-thought ("simulate thinking it through").
5. **Construct the answer** – synthesise into a structure that answers the question directly.
6. **Refine / check** – review for accuracy, clarity, tone, constraints; sometimes backtrack or iterate.

## How each model described it

| Model | Distinctive framing |
|---|---|
| **Gemini** | Deconstruct prompt → information retrieval & synthesis (pattern recognition, not lookup) → generate response with formatting, tone and a quick review; reasoning = "sophisticated pattern matching and prediction". |
| **ChatGPT** | Six steps: read/understand → activate knowledge → **choose reasoning method** (deduction, induction, causal, analogical) → chain-of-thought → formulate answer → adjust clarity/tone; illustrated with an age-ordering logic puzzle. |
| **Grok** | Understand query → contextual analysis with attention → build a mental model → evaluate options (probabilistic reasoning) → construct response → review; lists limitations (bounded by training data, no independent new knowledge). *(The extracted text of this answer contains garbled fragments.)* |
| **Kimi** | Most explicit pipeline, demonstrated on "Which is larger, 3⁴ or 4³?": Phase 0 tokenise/parse, Phase 1 classify task and pick strategy (direct evaluation vs. logarithms), Phase 2 retrieve facts, Phase 3 execute and **cross-check**, Phase 4 plan and realise the response, Phase 5 **metacognition** (confidence score, edge cases). |
| **Claude** | Candid about limited self-insight: pattern recognition & context building → information assembly → structural planning → iterative refinement with mental backtracking → **constraint checking** (accurate, helpful, clear, safe) → analogical thinking. |
| **DeepSeek** | Stresses it is *not* human reasoning: parse → contextualise/retrieve → identify concepts and structure → build a chain-of-thought plan → compute token probabilities via attention → iterate → apply RLHF-trained helpfulness/honesty/safety. "Following footprints of reasoning laid down in training data." |

Common admissions: reasoning is **pattern-based and probabilistic**, bounded by training data and architecture, and may not capture intuitive or emotional aspects.

## Why this matters for agent design

- An agent needs a **central planner** that decomposes goals into executable actions — the LLM's staged reasoning provides this.
- The pipeline maps directly to agent components: *parse → plan (Ch. 6) → retrieve (Ch. 14) → act with tools (Ch. 5) → verify/reflect (Ch. 4) → respond*.
- Because the "reasoning" is simulated and probabilistic, agents need **external verification** — tests, tools, guardrails and evaluation (Ch. 18–19) — rather than trusting a model's account of its own thinking. Self-explanations are plausible narratives, not guaranteed traces of the actual computation.
- Consistency across vendors means the core patterns (CoT, self-check, constraint checking) transfer between models, while style differs.

## Key takeaways

- All leading LLMs describe a similar deconstruct → retrieve → reason step by step → generate → refine loop.
- This staged, chain-of-thought-like process is what makes LLMs viable reasoning engines for autonomous agents.
- Improving the **reliability of simulated reasoning** is central to building trustworthy agents.

**Prev:** [Appendix E — AI Agents on the CLI](appendix-e-cli-agents.md) · **Next:** [Appendix G — Coding Agents](appendix-g-coding-agents.md)
