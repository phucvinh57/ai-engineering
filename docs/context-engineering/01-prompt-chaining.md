# 01 — Prompt Chaining

> **Source:** *Agentic Design Patterns* — Chapter 1: Prompt Chaining (PDF pp. 21–33 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Split a complex task into a **sequence of small prompts**, where each step's output becomes the next step's input. Also called the **Pipeline** pattern. It trades one overloaded prompt for several focused ones that are easier to debug and more reliable.

## Problem: why one big prompt fails

A single prompt with many instructions often causes:

- **instruction neglect** – parts of the prompt are ignored,
- **contextual drift** – the model loses the original context,
- **error propagation** – an early mistake gets amplified,
- **hallucination** – higher cognitive load → more invention,
- context-window pressure for long inputs.

Example: "Analyse this market report, summarise it, find trends with data, and write an email" – the model may summarise well but botch the email.

## Solution

Decompose into steps, each with one job (and optionally its own **role**):

1. *Summarise* the report (role: Market Analyst).
2. *Identify top-3 trends + supporting data* from the summary (role: Trend Analyst).
3. *Draft an email* from the trends (role: Documentation Writer).

```
input ─► [Prompt 1] ─► out1 ─► [Prompt 2] ─► out2 ─► [Prompt 3] ─► result
              ▲ validate / branch / call a tool between steps ▲
```

Key design points:

- **Structured output (JSON/XML) between steps.** Ambiguous free text in → broken next step. Ask for a schema so the next prompt can parse it unambiguously.
- **Deterministic code between LLM calls:** validation, conditional branching, arithmetic via a calculator tool, database lookups.
- **Combine with parallelization (Ch. 3):** gather/extract from many sources in parallel, then run the *dependent* synthesis → review steps as a chain.

## Use cases

| Use case | Example chain |
|---|---|
| Information processing | extract text → summarise → extract entities → query KB → write report |
| Complex Q&A | split into sub-questions → research each → synthesise |
| Data extraction | extract fields → validate → re-prompt for missing/malformed fields → output |
| Content generation | ideas → pick one → outline → draft section by section → revise |
| Stateful conversation | parse intent/entities → update state → respond → repeat |
| Code generation | pseudocode → draft → find issues → refine → add tests/docs |
| Multimodal reasoning | read text in image → link to labels → interpret table |

OCR-style example: LLM extracts text → LLM normalises ("one thousand and fifty" → 1050) → a **calculator tool** does the arithmetic (LLMs are weak at exact maths).

## Minimal code (LangChain LCEL)

```python
extract   = ChatPromptTemplate.from_template("Extract the technical specifications from:\n\n{text_input}")
transform = ChatPromptTemplate.from_template("Turn these specs into JSON with keys cpu, memory, storage:\n\n{specifications}")

extraction_chain = extract | llm | StrOutputParser()
full_chain = {"specifications": extraction_chain} | transform | llm | StrOutputParser()

full_chain.invoke({"text_input": "3.5 GHz octa-core, 16GB RAM, 1TB NVMe SSD"})
```

LangChain gives linear chains; **LangGraph** adds state and cycles for richer agents. CrewAI and Google ADK offer equivalents.

## Context engineering vs. prompt engineering

The chapter introduces this idea (central to this docs folder):

- **Prompt engineering** = optimise the wording of the immediate query.
- **Context engineering** = design the *entire information environment* delivered to the model before it generates: system prompt, retrieved documents, tool outputs, plus implicit data (user identity, interaction history, environment state).
- Output quality depends less on the model and more on the **richness and relevance of the context**.
- "Engineering" = runtime pipelines that fetch/transform that data, and feedback loops to improve it (e.g. automated prompt optimisers such as Vertex AI Prompt Optimizer).

Example: an email-drafting agent should first pull calendar availability (tool), the recipient relationship (implicit), and notes from past meetings (retrieval) *before* writing.

## When to use

Use it when a task is too complex for one prompt, has distinct processing stages, needs external tools between steps, or needs multi-step reasoning with state.

## Key takeaways

- Break complex tasks into small focused steps; output of step *n* feeds step *n+1*.
- Prefer structured (JSON) hand-offs and validate between steps.
- Improves reliability, modularity and debuggability; costs extra latency/tokens.
- It's the foundation for planning, tool use and multi-step agent workflows.

**Prev:** [00 — Introduction](00-introduction.md) · **Next:** [02 — Routing](02-routing.md)
