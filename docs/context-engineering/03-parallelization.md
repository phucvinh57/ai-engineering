# 03 — Parallelization

> **Source:** *Agentic Design Patterns* — Chapter 3: Parallelization (PDF pp. 48–62 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Run **independent** steps (LLM calls, tool calls, whole sub-agents) at the same time, then merge the results. Total latency becomes "slowest branch" instead of "sum of all branches". Most useful when steps wait on I/O such as APIs and databases.

## Sequential vs. parallel

Research two sources sequentially: search A → summarise A → search B → summarise B → synthesise.
In parallel: (search A ∥ search B) → (summarise A ∥ summarise B) → synthesise. The final synthesis still has to wait for its inputs — a *fan-out / fan-in* shape.

```
            ┌─► task A ─┐
input ─► split ─► task B ─┼─► merge / synthesise ─► output
            └─► task C ─┘
```

Rule: find the parts of a workflow that **don't depend on each other's output** and run them concurrently.

## Use cases

| Area | Parallel tasks |
|---|---|
| Research | news search + stock data + social mentions + internal DB |
| Data analysis | sentiment + keywords + categorisation + urgency detection over a batch |
| Multi-API | flights + hotels + events + restaurants for a trip plan |
| Content generation | subject line + body + image + CTA text |
| Validation | email format + phone + address lookup + profanity check |
| Multimodal | analyse text and image of the same post simultaneously |
| Options / A-B | generate several headline variants, pick the best |

## Implementation

- **LangChain (LCEL):** `RunnableParallel({...})` runs several chains side by side; a `RunnablePassthrough()` entry forwards the original input. The dict result feeds a synthesis prompt: `map_chain | synthesis_prompt | llm | parser`.
- **LangGraph:** several nodes fan out from one node, then converge at a join node.
- **Google ADK:** `ParallelAgent(sub_agents=[...])` runs researcher agents concurrently, each storing output in shared session state via `output_key`; a `SequentialAgent([parallel_agent, merger_agent])` then runs the merger, whose prompt interpolates `{renewable_energy_result}`, etc. Tell the merger to use *only* the provided summaries to keep it grounded.

```python
map_chain = RunnableParallel({
    "summary":   summarize_chain,
    "questions": questions_chain,
    "key_terms": terms_chain,
    "topic":     RunnablePassthrough(),
})
full_chain = map_chain | synthesis_prompt | llm | StrOutputParser()
```

> **Concurrency ≠ parallelism.** Python `asyncio` runs on one thread and switches tasks while they wait on the network (GIL applies). That is perfect for I/O-bound LLM/API calls but does not speed up CPU-bound work.

## Trade-offs

- More design, debugging and logging complexity (non-deterministic ordering, partial failures).
- Rate limits and cost: N simultaneous calls cost the same tokens, just faster.
- Decide how to handle one branch failing (retry, skip, fail all).

## When to use

Multiple independent operations, e.g. fetching from several APIs, processing chunks of data, or generating pieces of content for later synthesis.

## Key takeaways

- Parallelization cuts latency for independent tasks, especially I/O-bound ones.
- It combines naturally with chaining (sequential dependent steps) and routing (conditional paths).
- Watch the added complexity and cost.
- Tools: `RunnableParallel` (LangChain), fan-out nodes (LangGraph), `ParallelAgent` (ADK) or LLM-driven delegation.

**Prev:** [02 — Routing](02-routing.md) · **Next:** [04 — Reflection](04-reflection.md)
