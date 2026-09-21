# Appendix E — AI Agents on the CLI

> **Source:** *Agentic Design Patterns* — Appendix E: AI Agents on the CLI (PDF pp. 397–401 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite. Tool details reflect the book's snapshot in time and may have changed.

## TL;DR

The terminal is becoming a collaborative workspace: **agent CLIs** understand natural language, keep context about your whole codebase and perform multi-step development tasks. There's no single best tool — the differences lie in quality, efficiency and philosophy. Many use cases work in several of them.

## The four tools

| Tool | Philosophy / strength | Typical uses |
|---|---|---|
| **Claude CLI (Claude Code)** | High-level coding agent with a holistic model of your repo; conversational, explains its plan before acting (pair-programming style). Deep Git integration; extensible with custom tools via MCP (private APIs, DB queries, project scripts). Best for large, architecture-spanning work. | Large refactors (session cookies → stateless JWT across endpoints, middleware and frontend); integrating a new API from an OpenAPI spec (service module + UI component + dashboard); generating TSDoc for a poorly documented module. |
| **Gemini CLI** | Open-source all-rounder: Gemini 2.5 Pro, very large context window, multimodal, generous free tier, transparent "Reason and Act" loop. Built-in tools: file system, shell, web fetch/search, multi-file read, memory tool. **Sandboxing** isolates actions; MCP servers bridge to local/other APIs. | Screenshot → responsive React component; find outdated GKE clusters and generate upgrade commands; call an internal HR tool (`get-employee-details`) to fill a template; refactor Java from log4j to slf4j. |
| **Aider** | Open-source, model-agnostic pair programmer that edits your files, **runs tests, and auto-commits each successful change** to Git — a transparent, auditable trail. | Test-driven development (write failing test → make it pass); fix a leap-year bug and verify against the test suite; upgrade `requests` usage and `requirements.txt`. |
| **GitHub Copilot CLI** | Native GitHub integration; can be **assigned an issue**, work on a branch and open a pull request for human review. | Automated issue resolution; repo-aware Q&A ("where is DB connection logic defined and which env vars?"); shell-command helper (`gh? find files > 50MB, compress…`). |

> Note: in this appendix the book expands "MCP" as "Multi-tool Control Protocol"; elsewhere (Ch. 10) it is the **Model Context Protocol**.

## Terminal-Bench

A benchmark for agents in command-line environments (text-based and sandboxed, so an ideal agent habitat). **Terminal-Bench-Core-v0** has **80 hand-curated tasks** (scientific workflows, data analysis, …). **Terminus**, a minimal agent, provides a standard testbed for comparing language models. Extensible via containers or direct connections; future plans include massively parallel evaluation and more established benchmarks; open to contributions.

## Choosing

- Complex architectural changes → **Claude Code**.
- Versatile, multimodal, Google Cloud/open-source → **Gemini CLI**.
- Git-centric, direct edits, model choice/cost control → **Aider**.
- GitHub workflow integration (issues → PRs) → **Copilot CLI**.

## Practical context-engineering tips for CLI agents

- Give the agent the **right files and constraints** (project conventions, test commands) rather than the whole repo.
- Extend it with **MCP tools** for private APIs and project scripts; restrict permissions (least privilege, sandbox).
- Ask for a **plan first** on big changes; verify with tests and review diffs before merging.

## Key takeaways

- Agent CLIs bring planning, multi-file editing, Git and tool use into the terminal.
- Each tool has a niche; proficiency with them is becoming an essential developer skill.
- Benchmarks like Terminal-Bench aim to measure real agent capability objectively.

**Prev:** [Appendix D — AgentSpace](appendix-d-agentspace.md) · **Next:** [Appendix F — Under the Hood: Agents' Reasoning Engines](appendix-f-reasoning-engines.md)
