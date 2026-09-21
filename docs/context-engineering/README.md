# Agentic Design Patterns — Condensed Study Notes

A shortened, easier-to-read rewrite of the book, split into one file per chapter.

## Original source

> **Antonio Gulli. _Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems._** (Springer; foreword by Saurabh Tiwary.)
> Local copy: [`Agentic_Design_Patterns_Complete.pdf`](../../Agentic_Design_Patterns_Complete.pdf) — 458 pages.

These notes are **paraphrased summaries for personal study**, not a substitute for the book. Wording, structure and examples were condensed; code listings were reduced to their essential idea. Each file starts with a *Source* line giving the chapter and the **PDF page range** so you can jump to the original (page numbers are PDF pages, not the book's per-chapter numbering). Figures, most long code listings, reference lists and the PDF's Index of Terms (pp. 447–458) are not reproduced. Please buy/read the original for full detail, complete code and citations; the book's author donates royalties to Save the Children.

**How each chapter note is organised:** TL;DR → problem/solution → use cases → implementation notes → tips (context-engineering angle where relevant) → when to use → key takeaways → prev/next links.

## Contents

| # | Note | Original PDF pages |
|---|---|---|
| 00 | [Introduction — What is an agent?](00-introduction.md) (foreword, preface, agent levels) | 5–20 |
| 01 | [Prompt Chaining](01-prompt-chaining.md) | 21–33 |
| 02 | [Routing](02-routing.md) | 34–47 |
| 03 | [Parallelization](03-parallelization.md) | 48–62 |
| 04 | [Reflection](04-reflection.md) | 63–76 |
| 05 | [Tool Use (Function Calling)](05-tool-use.md) | 77–97 |
| 06 | [Planning](06-planning.md) | 98–110 |
| 07 | [Multi-Agent Collaboration](07-multi-agent-collaboration.md) | 111–129 |
| 08 | [Memory Management](08-memory-management.md) | 130–151 |
| 09 | [Learning and Adaptation](09-learning-and-adaptation.md) | 152–164 |
| 10 | [Model Context Protocol (MCP)](10-model-context-protocol.md) | 165–180 |
| 11 | [Goal Setting and Monitoring](11-goal-setting-and-monitoring.md) | 181–193 |
| 12 | [Exception Handling and Recovery](12-exception-handling-and-recovery.md) | 194–201 |
| 13 | [Human-in-the-Loop](13-human-in-the-loop.md) | 202–210 |
| 14 | [Knowledge Retrieval (RAG)](14-knowledge-retrieval-rag.md) | 211–228 |
| 15 | [Inter-Agent Communication (A2A)](15-inter-agent-communication-a2a.md) | 229–243 |
| 16 | [Resource-Aware Optimization](16-resource-aware-optimization.md) | 244–259 |
| 17 | [Reasoning Techniques](17-reasoning-techniques.md) | 260–283 |
| 18 | [Guardrails / Safety Patterns](18-guardrails-safety-patterns.md) | 284–303 |
| 19 | [Evaluation and Monitoring](19-evaluation-and-monitoring.md) | 304–322 |
| 20 | [Prioritization](20-prioritization.md) | 323–332 |
| 21 | [Exploration and Discovery](21-exploration-and-discovery.md) | 333–346 |
| A | [Advanced Prompting Techniques](appendix-a-advanced-prompting.md) | 347–375 |
| B | [Agentic Interactions: GUI to Real World](appendix-b-agentic-interactions.md) | 376–382 |
| C | [Quick Overview of Agentic Frameworks](appendix-c-agentic-frameworks.md) | 383–390 |
| D | [Building an Agent with AgentSpace](appendix-d-agentspace.md) | 391–396 |
| E | [AI Agents on the CLI](appendix-e-cli-agents.md) | 397–401 |
| F | [Under the Hood: Agents' Reasoning Engines](appendix-f-reasoning-engines.md) | 402–416 |
| G | [Coding Agents](appendix-g-coding-agents.md) | 417–422 |
| — | [Conclusion and Glossary](conclusion-and-glossary.md) | 423–446 |

## Reading paths

**If you're here for context engineering** (curating what goes into the model's window):
[01 Prompt Chaining](01-prompt-chaining.md) (context vs. prompt engineering) → [Appendix A](appendix-a-advanced-prompting.md) (prompt structure, context layers, structured output) → [05 Tool Use](05-tool-use.md) → [08 Memory](08-memory-management.md) → [14 RAG](14-knowledge-retrieval-rag.md) → [10 MCP](10-model-context-protocol.md) → [16 Resource-Aware Optimization](16-resource-aware-optimization.md) (context pruning) → [Appendix G](appendix-g-coding-agents.md) (hand-curated context for coding agents).

**Building blocks of an agent (in book order):** 01 → 08 for control flow, tools, planning, multi-agent and memory; 09 → 13 for learning, protocols, goals, recovery and humans; 14 → 21 for retrieval, communication, optimisation, reasoning, safety, evaluation and discovery.

**Production readiness:** [12 Exception Handling](12-exception-handling-and-recovery.md) → [13 HITL](13-human-in-the-loop.md) → [18 Guardrails](18-guardrails-safety-patterns.md) → [19 Evaluation and Monitoring](19-evaluation-and-monitoring.md).

## Pattern cheat-sheet

| Need | Pattern |
|---|---|
| Split a hard task into steps | [Prompt Chaining](01-prompt-chaining.md), [Planning](06-planning.md) |
| Pick the right path/tool | [Routing](02-routing.md), [Prioritization](20-prioritization.md) |
| Go faster | [Parallelization](03-parallelization.md) |
| Improve output quality | [Reflection](04-reflection.md), [Reasoning Techniques](17-reasoning-techniques.md) |
| Reach the outside world | [Tool Use](05-tool-use.md), [MCP](10-model-context-protocol.md), [RAG](14-knowledge-retrieval-rag.md) |
| Remember and improve | [Memory](08-memory-management.md), [Learning](09-learning-and-adaptation.md) |
| Work as a team | [Multi-Agent](07-multi-agent-collaboration.md), [A2A](15-inter-agent-communication-a2a.md) |
| Stay on track | [Goals & Monitoring](11-goal-setting-and-monitoring.md), [Evaluation](19-evaluation-and-monitoring.md) |
| Be safe and reliable | [Exception Handling](12-exception-handling-and-recovery.md), [HITL](13-human-in-the-loop.md), [Guardrails](18-guardrails-safety-patterns.md) |
| Control cost/latency | [Resource-Aware Optimization](16-resource-aware-optimization.md) |
| Discover new things | [Exploration & Discovery](21-exploration-and-discovery.md) |

## Notes on the notes

- Product names, model versions and framework APIs (ADK, LangChain, CrewAI, etc.) reflect the book's 2025 snapshot and may have changed — check current docs before copying code.
- Where the book is inconsistent or its extracted text was garbled, the note says so (e.g. the "MCP" expansion in Appendix E; Grok's answer in Appendix F).
- Appendix D is mostly UI screenshots, so its note is short.
