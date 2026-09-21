# Appendix G — Coding Agents

> **Source:** *Agentic Design Patterns* — Appendix G: Coding Agents (PDF pp. 417–422 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

**Vibe coding** is great for ideation and prototypes, but production software needs a **human-led team of specialised coding agents**. The developer is the *orchestrator*; agents are *force multipliers*. Everything hinges on **context quality**.

## Vibe coding: the starting point

Use LLMs for first drafts, outlines and quick prototypes; it beats the "blank page", helps explore unfamiliar APIs or architectures, and gives you something to critique and refactor. Limit: it doesn't by itself produce robust, scalable, maintainable software.

The book notes industry claims of rapid adoption — e.g. over 30% of new code at Google being AI-assisted/generated (early 2025), with a similar claim from Microsoft — framing the goal as **empowering developers, not replacing them**.

## Three principles of the framework

1. **Human-led orchestration** – the developer is team lead and architect, always in the loop: sets goals, chooses which agent to use, supplies context, and makes the final call.
2. **The primacy of context** – an agent is only as good as its briefing. Prefer **deliberate, human-curated context** over automated black-box retrieval:
   - the complete relevant **codebase**,
   - **external knowledge** (docs, API definitions, design docs),
   - the **human brief** (goals, requirements, PR descriptions, style guides).
3. **Direct model access** – use frontier models directly (Gemini 2.5 Pro, Claude Opus 4, OpenAI, DeepSeek…); weaker models or intermediaries that truncate/obscure context degrade results.

## Components

| Component | Role |
|---|---|
| **Orchestrator (you)** | Defines tasks, prepares context, validates all output; works through terminal, editor and the models' native UIs. |
| **Context Staging Area** | A per-task folder (e.g. `task-context/`) with markdown files for goals (`01_BRIEF.md`), code (`02_CODE/`) and relevant docs — a complete, accurate briefing. |
| **Specialist agents** | Conceptual personas invoked via role-specific prompts (not separate apps). |

**Specialists and example invocation prompts**

| Agent | Purpose | Prompt gist |
|---|---|---|
| **Scaffolder** | Implement features / boilerplate | "You are a senior software engineer. Based on `01_BRIEF.md` and the patterns in `02_CODE/`, implement the feature…" |
| **Test Engineer** | Unit / integration / E2E tests | "You are a QA engineer. Write a full pytest suite covering all edge cases…" |
| **Documenter** | Docs for functions, APIs, codebases | "You are a technical writer. Generate markdown docs with request/response examples…" |
| **Optimizer** | Performance and refactoring | "Analyse for bottlenecks or clarity issues; propose specific changes and explain why." |
| **Process Agent / Reviewer** | **Critique → Reflection** code review | "You are a principal engineer. First critique the changes in detail; then reflect on your critique and give a concise, prioritised summary." (Reflection pattern, Ch. 4: filters pedantic points into actionable feedback.) |

## Setup checklist

1. **Provision two frontier-model providers** (e.g. Gemini 2.5 Pro + Claude 4 Opus) for comparison and redundancy; manage keys as production secrets.
2. **Local context orchestrator** – a lightweight CLI/runner driven by a config file (e.g. `context.toml`) that lists the files, directories or URLs compiled into the prompt, so you always know exactly what the model sees.
3. **Version-controlled prompt library** – a `/prompts` directory (`reviewer.md`, `documenter.md`, `tester.md`…) treated like code and refined by the team.
4. **Git hooks** – e.g. a pre-commit hook runs the Reviewer Agent on staged changes and prints its critique-and-reflection in the terminal.

## Principles for leading the augmented team

- **Maintain architectural ownership** – you define the what and why; agents accelerate the how.
- **Master the art of the brief** – a prompt is a briefing package for a highly capable new teammate.
- **Be the ultimate quality gate** – agent output is a *proposal*, never a command.
- **Engage in iterative dialogue** – refine rather than discard; treat the reviewer's reflection as the start of a discussion.

## Context-engineering takeaways

- Curate context by hand for important work: relevant code + docs + a crisp brief beats dumping the whole repo.
- Keep prompts and context definitions in Git so they are reviewable and reproducible.
- Use a second model/provider as an independent check.

## Key takeaways

- Vibe code to explore; use specialised, human-orchestrated agents to ship.
- Quality of context determines quality of output.
- Developers move from writing every line to leading a human–AI team focused on architecture and creative problem-solving.

**Prev:** [Appendix F — Reasoning Engines](appendix-f-reasoning-engines.md) · **Next:** [Conclusion and Glossary](conclusion-and-glossary.md)
