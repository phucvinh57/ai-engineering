# 02 — Routing

> **Source:** *Agentic Design Patterns* — Chapter 2: Routing (PDF pp. 34–47 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Routing adds **conditional logic** to an agent: analyse the input (or current state), then send control to the most suitable tool, chain or sub-agent. It turns a fixed pipeline (Ch. 1) into an adaptive workflow.

## Problem

A linear chain treats every input the same. Real requests vary: an order-status question, a product question, a technical fault and an ambiguous message all need different handling.

## Solution

A **router** makes a decision, then dispatches:

```
user query ─► [Router] ─┬─► order-status tool / DB
                        ├─► product-catalog search
                        ├─► tech-support chain or human escalation
                        └─► clarification prompt (intent unclear)
```

### Four ways to implement the router

| Method | How it works | Pros / cons |
|---|---|---|
| **LLM-based** | Prompt the LLM to output a label (`'booker'`, `'info'`, `'unclear'`). Code reads the label and branches. | Flexible, handles nuance; costs a call, can mislabel. |
| **Embedding-based** | Embed the query; pick the route whose description embedding is closest (semantic routing, see Ch. 14). | Meaning-based, cheap, no generation. |
| **Rule-based** | `if/else`, keywords, regex, structured fields. | Fast, deterministic; brittle on novel input. |
| **ML classifier** | A small model fine-tuned on labelled routing examples; logic lives in the weights, not a prompt. (LLMs may only help generate training data.) | Fast and specialised; needs labelled data. |

Routing can happen **at the start** (classify the task), **mid-chain** (choose the next action) or **inside a subroutine** (choose a tool).

## Use cases

- **Assistants / tutors:** interpret intent → retrieval tool, human handoff, or next lesson module.
- **Data pipelines:** classify emails / tickets / payloads → sales-lead flow, CSV vs JSON transformer, urgent-escalation path.
- **Multi-agent dispatch:** research system routes work to search, summarise or analyse agents.
- **Coding assistants:** detect language and intent (debug / explain / translate) → right specialised tool.

## Implementation notes

- **LangChain / LangGraph:** a router chain outputs a label; `RunnableBranch` (or conditional edges in a LangGraph state graph) sends the request to the matching handler, with a default branch for `unclear`. LangGraph's explicit graph is best for complex routing driven by accumulated state.
- **Google ADK:** define specialised sub-agents (each with tools) and a `Coordinator` whose instruction says "only delegate". Having `sub_agents` enables LLM-driven delegation ("Auto-Flow") — routing is implicit in tool/agent selection, simpler when actions are discrete.

Minimal router prompt idea:

```text
Analyse the request. Output ONE word only:
'booker' (flights/hotels) | 'info' (general questions) | 'unclear'
```

Always include a **fallback** route for low-confidence or unknown classes, and `.strip()`/validate the label before branching.

## When to use

Use routing when an agent must choose between several distinct workflows, tools or sub-agents based on input or state — e.g. a support bot that triages sales vs. technical vs. account queries.

## Key takeaways

- Routing gives dynamic, conditional control flow instead of a fixed pipeline.
- Implement with an LLM, embeddings, rules or a trained classifier — mix them (rules first for speed, LLM for the hard cases).
- Always provide a default/clarification path.
- LangGraph = explicit graph; ADK = delegation via sub-agents/tools.

**Prev:** [01 — Prompt Chaining](01-prompt-chaining.md) · **Next:** [03 — Parallelization](03-parallelization.md)
