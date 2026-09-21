# Appendix C — Quick Overview of Agentic Frameworks

> **Source:** *Agentic Design Patterns* — Appendix C: Quick overview of Agentic Frameworks (PDF pp. 383–390 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite. Framework details reflect the book's snapshot in time.

## TL;DR

Frameworks sit on a spectrum from **low-level building blocks with fine control** (LangChain → LangGraph) to **opinionated, higher-level team orchestration** (Google ADK, CrewAI). Pick the abstraction level your application needs: a simple sequence, a dynamic reasoning loop, or a managed team of specialists.

## Main frameworks

### LangChain
- Core: **LCEL** pipes components into chains — `chain = prompt | model | output_parser`.
- Workflows are **DAGs** (one direction, no loops), generally stateless per run.
- Use for: simple RAG, summarisation, structured extraction.

### LangGraph
- Built on LangChain; workflow = **graph** of nodes (functions/chains) and edges (conditional logic).
- Supports **cycles** (loop, retry, call tools in flexible order) and **explicit, persistent state** passed between nodes.
- Use for: multi-agent systems with a supervisor, plan-and-execute agents, human-in-the-loop (graph waits for input).
- Also supports parallel branches (e.g. joke + story + poem nodes feeding an aggregator).

| | LangChain | LangGraph |
|---|---|---|
| Core abstraction | Chain (LCEL) | Graph of nodes |
| Workflow | Linear (DAG) | Cyclical |
| State | Generally stateless per run | Explicit, persistent |
| Best for | Simple, predictable sequences | Complex, dynamic, stateful agents |

**Rule:** linear A→B→C with no looping → LangChain. Reason/plan/reflect/retry loop → LangGraph.

### Google ADK (Agent Development Kit)
- Higher-level, **opinionated, production-oriented** framework for **teams of agents**.
- Pre-built patterns: `SequentialAgent`, `ParallelAgent`, `LoopAgent`, LLM-driven delegation to `sub_agents`.
- Sessions/state handled more implicitly (less granular than LangGraph's explicit state).
- Analogy: LangGraph = detailed wiring of a single robot or team; ADK = a factory assembly line for a fleet that already knows how to cooperate.
- Minimal agent: `LlmAgent(model=..., name=..., instruction="Respond using google search", tools=[google_search])`.

### CrewAI
- Team-charter model: **Agents** (role, goal, backstory), **Tasks** (description, expected output, assigned agent), **Crew** (agents + tasks + a **Process**: *sequential* or *hierarchical* with a manager agent).
- You design the team, not the state machine. Focused on collaboration logic rather than the full lifecycle.

## Other frameworks

| Framework | Focus | Strength | Trade-off |
|---|---|---|---|
| **Microsoft AutoGen** | Multi-agent **conversation** | Flexible, dynamic interactions | Less predictable paths; needs careful prompting to converge |
| **LlamaIndex** | **Data framework** connecting LLMs to private data | Powerful ingestion/indexing/retrieval for RAG | Weaker native agent control flow |
| **Haystack** | Scalable, production **search pipelines** | Performance on large retrieval/QA | Rigid for highly dynamic agent behaviour |
| **MetaGPT** | SOP-driven multi-agent "software company" | Structured, coherent outputs (code) | Highly specialised |
| **SuperAGI** | Full lifecycle management, GUI, monitoring | Production readiness, loop handling, observability | More overhead/complexity |
| **Semantic Kernel** (Microsoft) | LLM + conventional code via plugins and planners | Fits enterprise .NET/Python codebases | Steeper conceptual learning curve |
| **Strands Agents** (AWS) | Lightweight, model-driven agent SDK | Simple, model-agnostic, native MCP support | You build more of the ops infrastructure |

## How to choose

1. **Is the flow linear and known?** → plain chains / a script (don't over-engineer).
2. **Does it loop, reflect, retry, need state or human input?** → a graph framework (LangGraph).
3. **Is it a team of role-based specialists?** → CrewAI or ADK.
4. **Is the hard part data retrieval?** → LlamaIndex / Haystack.
5. **Need production lifecycle and observability?** → ADK, SuperAGI, or add tracing/evals yourself (Ch. 19).

The core trade-off: **granular control** (graph-based) vs. **faster development** (opinionated platforms).

## Key takeaways

- LangChain = linear chains; LangGraph = stateful cyclical graphs.
- ADK and CrewAI raise the level to multi-agent teams; ADK is more production-oriented, CrewAI more role-play/collaboration-oriented.
- Specialised options exist for retrieval (LlamaIndex, Haystack), SOP-driven coding (MetaGPT), enterprise integration (Semantic Kernel) and lightweight agents (Strands).

**Prev:** [Appendix B — Agentic Interactions](appendix-b-agentic-interactions.md) · **Next:** [Appendix D — Building an Agent with AgentSpace](appendix-d-agentspace.md)
