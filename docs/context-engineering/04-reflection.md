# 04 — Reflection

> **Source:** *Agentic Design Patterns* — Chapter 4: Reflection (PDF pp. 63–76 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

The agent **evaluates its own output and improves it** in a feedback loop: *execute → critique → refine → (repeat until good enough)*. Best done with two roles — a **Producer** and a **Critic** — so the reviewer isn't biased by having written the work.

## The loop

1. **Execute** – produce a first output.
2. **Evaluate / critique** – check accuracy, coherence, style, completeness, instruction-following (another LLM call, tests, or rules).
3. **Refine** – rewrite using the critique, adjust parameters, or change the plan.
4. **Iterate** – stop on "good enough" or a max-iteration limit.

Unlike chaining (output flows forward) or routing (pick a path), reflection loops **backward**.

## Producer–Critic (Generator–Critic)

- **Producer:** generates the draft, code or plan.
- **Critic:** different system prompt/persona ("senior engineer", "meticulous fact-checker"), judges against explicit criteria and returns structured feedback.
- Separation avoids "cognitive bias" of self-review; the critic can be a specialist.
- Could be two agents or one model called twice with different prompts.

## Related patterns

- **Goals & monitoring (Ch. 11):** the goal is the benchmark for critique; monitoring supplies the signals; reflection is the corrective engine.
- **Memory (Ch. 8):** keeping history turns reflection from isolated events into *cumulative* learning (don't repeat earlier mistakes).

## Use cases

| Domain | Reflection loop |
|---|---|
| Writing | draft → critique flow/tone/clarity → rewrite |
| Code | write → run tests / static analysis → fix |
| Problem solving | propose step → check for contradictions → backtrack |
| Summarisation | summary → compare to source key points → add omissions |
| Planning | plan → check feasibility vs. constraints → revise |
| Conversation | review history + last reply for coherence |

## Implementation sketch

**LangChain loop** (generic Python control flow; LangGraph is the natural fit for stateful cycles):

```python
history = [HumanMessage(task)]
for i in range(MAX_ITERS):
    code = llm.invoke(history)                    # 1. generate / refine
    critique = llm.invoke([SystemMessage(REVIEWER_PROMPT),
                           HumanMessage(f"Task:{task}\nCode:{code}")])  # 2. reflect
    if "CODE_IS_PERFECT" in critique:             # stop condition
        break
    history += [code, HumanMessage(f"Critique:{critique}\nRefine the code.")]
```

The reviewer prompt asks for either a sentinel (`CODE_IS_PERFECT`) or a bullet list of problems — a simple, parseable contract.

**Google ADK:** `SequentialAgent([generator, reviewer])` where the generator writes to `output_key="draft_text"` and the reviewer reads it and returns `{"status": "ACCURATE|INACCURATE", "reasoning": ...}`. A `LoopAgent` extends this to repeated refinement.

## Trade-offs

- Extra LLM calls → higher **cost and latency**.
- **Context grows** every iteration (draft + critique + rewrite), risking context-window overflow and API throttling.
- Always cap iterations and define a clear stopping criterion.

## When to use

When correctness, polish and detail matter more than speed/cost: long-form content, code, detailed plans. Add a separate critic when you need objectivity or specialised review.

## Key takeaways

- Reflection = feedback loop of execute → critique → refine.
- Producer/Critic separation gives more objective, structured feedback.
- Pair with memory and goal-monitoring for cumulative improvement.
- Budget for latency, cost and context growth; set max iterations.

**Prev:** [03 — Parallelization](03-parallelization.md) · **Next:** [05 — Tool Use](05-tool-use.md)
