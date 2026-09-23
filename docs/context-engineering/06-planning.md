# 06 — Planning

> **Source:** *Agentic Design Patterns* — Chapter 6: Planning (PDF pp. 98–110 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Instead of just reacting, the agent first **works out a sequence of steps** from the current state to the goal, then executes — and **re-plans** when the world changes. You specify the *what*; the agent discovers the *how*.

## Key ideas

- **Initial state → goal state:** e.g. "organise a team offsite" (budget, headcount, dates) → "offsite booked". The plan doesn't exist beforehand; it's generated per request.
- **Adaptability:** a plan is a starting point, not a script. If a venue is unavailable, the agent registers the new constraint and re-plans.
- **Flexibility vs. predictability trade-off.** Dynamic planning adds uncertainty. If the solution is already known and repeatable, use a **fixed workflow** (chain/graph) instead. The deciding question:

> **Does the "how" need to be discovered, or is it already known?**

## Use cases

- **Procedural automation** – onboarding an employee: create accounts → assign training → coordinate departments, respecting dependencies.
- **Robotics / navigation** – find a path from A to B while optimising time/energy and avoiding obstacles.
- **Research and report writing** – phases: gather → summarise → structure → refine.

  > *Example — "Write a report comparing the top 3 vector databases for a RAG pipeline."*
  > 1. **Plan:** the agent first emits a numbered plan: (1) identify candidate DBs, (2) gather data on cost/latency/scaling/integrations for each, (3) run small benchmark queries if tooling allows, (4) draft comparison table, (5) write summary + recommendation, (6) cite sources.
  > 2. **Gather:** for each candidate, issue targeted searches ("Pinecone pricing 2026", "Weaviate vs Qdrant benchmark"), pulling structured facts rather than raw pages.
  > 3. **Gap check / re-plan:** if pricing data is missing for one DB, the agent adds a step to search vendor docs directly instead of failing silently.
  > 4. **Structure:** organise findings into a table + narrative outline before drafting prose.
  > 5. **Refine:** pass the draft through a **reflection** step (Ch. 4) to check claims are cited and the recommendation follows from the evidence.
  > This mirrors the Gemini Deep Research / OpenAI Deep Research flows below — the plan is what turns "write a report" from a single LLM call into a controllable, inspectable multi-step process.
  >
  > Runnable implementation: [`projects/playground/src/playground/planning.py`](../../projects/playground/src/playground/planning.py) (`uv run planning`) — plan → gather → gap-check/re-plan → structure → refine over a small mock knowledge base, so it runs offline against a local Ollama model.

- **Customer support** – diagnose → apply fix → escalate.

## Implementations in the book

### 1. CrewAI "plan-then-act" agent
One agent with a task that says: *"1. Create a bullet-point plan for a summary of {topic}. 2. Write the ~200-word summary based on your plan."* Run with `Process.sequential`. Simple, but shows that just **prompting the agent to plan first** improves structure.

### 2. Google Gemini Deep Research
A managed, long-running agent:
1. Decomposes the prompt into a **multi-point research plan** shown to the user for review/edit (human-in-the-loop).
2. Runs an iterative **search → analyse → find gaps → search again** loop, cross-checking facts.
3. Runs asynchronously (robust to single failures; user is notified when done), can include the user's own documents.
4. Produces a structured multi-page report with citations and the full list of consulted sources.

Good for competitive analysis and literature reviews; reduces selection bias by covering more sources than a human could.

### 3. OpenAI Deep Research API
`client.responses.create(model="o3-deep-research-…", input=[developer message, user query], tools=[{"type": "web_search_preview"}], reasoning={"summary": "auto"})`.
- Returns a cited report (inline citation annotations with URL/title/span).
- **Exposes intermediate steps**: reasoning, each web-search query, any code interpreter runs — useful for debugging.
- Extensible with **MCP** tools (Ch. 10) to mix web research with private data.
- A faster `o4-mini-deep-research` variant exists for latency-sensitive use.

## Design tips

- Ask the model to output an explicit, numbered plan (ideally structured) before acting.
- Let the user approve or edit the plan when actions are costly or ambiguous.
- Store the plan in state so progress can be tracked (Ch. 11) and re-planning is possible.
- Pair with **reflection** (Ch. 4) to critique the plan and **exception handling** (Ch. 12) to recover when a step fails.

## When to use

When a request is too complex for a single action or tool: multi-step, interdependent processes such as research reports, onboarding or competitive analyses.

## Key takeaways

- Planning turns a reactive agent into a goal-driven one.
- LLMs can decompose goals into steps; prompt/design tasks so they must plan first.
- Prefer fixed workflows when the procedure is already known.
- Deep-research agents are the archetype: plan → iterate → synthesise with citations.

**Prev:** [05 — Tool Use](05-tool-use.md) · **Next:** [07 — Multi-Agent Collaboration](07-multi-agent-collaboration.md)
