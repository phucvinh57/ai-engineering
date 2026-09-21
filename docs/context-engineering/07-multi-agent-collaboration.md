# 07 — Multi-Agent Collaboration

> **Source:** *Agentic Design Patterns* — Chapter 7: Multi-Agent Collaboration (PDF pp. 111–129 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Instead of one do-everything agent, build a **team of specialised agents**, each with a role, goal and tools, coordinated through a defined communication structure. Benefits: modularity, scalability, robustness (one agent failing doesn't kill the system) and better quality on multi-domain tasks.

## What makes it work

1. **Roles and responsibilities** for each agent.
2. **Communication channels** (a shared protocol/ontology so agents can exchange data and delegate).
3. **A task flow / interaction protocol** that orchestrates them.

## Forms of collaboration

| Form | Idea |
|---|---|
| **Sequential handoff** | Agent A's output feeds agent B (a pipeline of specialists). |
| **Parallel processing** | Agents work on different parts at once; results are merged. |
| **Debate & consensus** | Agents with different views/sources argue toward a better decision. |
| **Hierarchical** | A manager delegates dynamically to workers and synthesises results; each worker owns a subset of tools. |
| **Expert team** | Researcher + writer + editor, etc. |
| **Critic–reviewer** | One group creates, another checks policy, security, correctness, quality; creator revises. Reduces hallucinations; good for code and research writing. |

## Communication topologies (Fig. 2 in the book)

| Model | Summary | Trade-off |
|---|---|---|
| **Single agent** | No interaction. | Simple; limited scope. |
| **Network** | Peer-to-peer, decentralised. | Resilient; communication overhead, hard to keep coherent. |
| **Supervisor** | One agent coordinates subordinates. | Clear control; single point of failure and bottleneck. |
| **Supervisor as a tool** | Supervisor supplies resources/analysis rather than commands. | Less rigid top-down control. |
| **Hierarchical** | Multi-level supervisors. | Scales complexity; more layers. |
| **Custom** | Hybrid tailored to the problem. | Flexible; needs deep design effort. |

Choose based on task complexity, number of agents, desired autonomy, robustness needs and communication overhead.

## Use cases

Complex research teams; software development (analyst → coder → tester → doc writer); marketing campaigns; financial analysis (data, sentiment, technical analysis, recommendation); support escalation (front-line → specialist); supply-chain optimisation; network fault triage and remediation.

## Framework examples

**CrewAI:** define `Agent(role, goal, backstory)` objects and `Task`s; a later task receives an earlier task's output via `context=[research_task]`; `Crew(agents, tasks, process=Process.sequential).kickoff()`.

**Google ADK** offers several composition primitives:

| Primitive | Behaviour |
|---|---|
| `sub_agents=[...]` on an `LlmAgent` | **Hierarchy**; the parent's instruction says when to delegate (LLM-driven delegation). |
| `SequentialAgent` | Runs sub-agents in order; passes data through session `state` (`output_key`). |
| `ParallelAgent` | Runs sub-agents concurrently; each writes its own state key. |
| `LoopAgent(max_iterations=N)` | Repeats sub-agents until a checker agent **escalates** (`EventActions(escalate=True)`) or the limit is hit. |
| `AgentTool(agent)` | **Agent as a tool**: a parent calls another agent like a function (e.g. an "Artist" writes a prompt, then calls "ImageGen"). |
| `BaseAgent` subclass | Custom non-LLM logic (e.g. a condition checker or task executor). |

## Design tips

- Give each agent a narrow role and only the tools it needs (smaller tool lists → better tool selection and less context).
- Pass **compact, structured** hand-offs (state keys, JSON) rather than whole transcripts.
- Always cap loops/iterations and handle a failed agent.
- Multi-agent systems are still limited by underlying LLM reasoning and cost more tokens; start with one agent and split only when needed.

## When to use

The task is too complex for one agent and decomposes into sub-tasks needing different skills/tools: research and analysis, software development, content creation, or anything benefiting from parallelism or cross-checking.

## Key takeaways

- Specialised agents + defined communication = more than the sum of the parts.
- Pick the topology (network, supervisor, hierarchy…) deliberately.
- Frameworks (CrewAI, ADK) give building blocks for sequential, parallel, loop and hierarchical flows.

**Prev:** [06 — Planning](06-planning.md) · **Next:** [08 — Memory Management](08-memory-management.md)
