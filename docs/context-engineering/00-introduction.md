# 00 — Introduction: What Is an Agent?

> **Source:** *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* — Foreword, Preface and "What makes an AI system an Agent?" (PDF pp. 5–20 of `Agentic_Design_Patterns_Complete.pdf`). This is a condensed rewrite, not a substitute for the book.

## TL;DR

An **agent** is an LLM wrapped in a loop that lets it perceive, plan, act and learn. The LLM is the engine; **design patterns** are the reusable blueprints that turn the engine into a reliable system. The book teaches 21 such patterns.

## Why patterns?

Agentic systems are *autonomous* (act without constant supervision), *proactive* (start actions toward a goal), *reactive* (respond to change), *goal-oriented*, and they use *tools* and *memory* and *communicate*. Getting all of that to work raises hard questions: how is state kept across steps? when is a tool called? how do agents talk to each other? how do you recover from errors?

Design patterns are battle-tested templates that answer these questions. Like software design patterns, they give you:

- a shared vocabulary,
- reusable solutions instead of reinvention,
- more maintainable, reliable and efficient agents.

The book's metaphor: your infrastructure and frameworks are a **canvas**; patterns are the techniques you paint with. Code samples use **LangChain/LangGraph**, **CrewAI** and **Google ADK**.

## The five-step agent loop

1. **Get the mission** – receive a goal ("organize my schedule").
2. **Scan the scene** – gather information (emails, calendar, contacts).
3. **Think it through** – plan the best approach.
4. **Take action** – execute (send invites, update calendar).
5. **Learn and improve** – observe outcomes and adapt.

The field moved from prompts/triggers → RAG (grounding) → single tool-using agents → **teams of specialised agents** ("agentic AI").

## Four levels of agent complexity

| Level | Description | Example |
|---|---|---|
| **0 – Core reasoning engine** | LLM alone, no tools/memory. Only knows its training data. | Explains a concept; can't name last month's winner. |
| **1 – Connected problem-solver** | LLM + tools (search, APIs, RAG). Multi-step interaction with the outside world. | Looks up live stock price, finds new TV shows. |
| **2 – Strategic problem-solver** | Plans multi-step work and does **context engineering**: selecting, packaging and managing the *most relevant* information for each step. Can also refine its own prompts. | Maps tool returns street names → agent passes only that short list to a local-search tool. |
| **3 – Collaborative multi-agent system** | A team of specialists coordinated by a manager agent. Limited today by LLM reasoning quality. | "Project manager" agent delegates to market-research, design and marketing agents. |

> **Context engineering** (a theme of this docs folder): give the model a short, focused, powerful context instead of everything. It curates the model's limited attention to avoid overload and improve quality.

## Five hypotheses for the future

1. **Generalist agents** that manage long, ambiguous goals (e.g. plan a 30-person offsite) — or a "Lego-like" composition of small specialised language models.
2. **Deep personalisation and proactive goal discovery** — agents that anticipate needs you haven't stated.
3. **Embodiment** — agents driving robots in the physical world.
4. **Agent-driven economy** — autonomous agents running businesses and trading with each other.
5. **Goal-driven, metamorphic multi-agent systems** — you declare an outcome; the system spawns/removes agents, rewrites prompts and even its own architecture.

## Takeaways from the foreword essays

- Don't trust agents blindly: supervise and verify. Mistakes are cheap in a recipe app, costly in finance or health.
- **Messy systems + agents = disaster.** Invest in clean data, consistent metadata and well-defined APIs first.
- The valuable human skills become: explaining tasks clearly, delegating wisely, verifying output.

## Book structure (per chapter)

Overview → practical applications → hands-on code → key takeaways → references. Chapters can be read in any order as a reference.

**Next:** [01 — Prompt Chaining](01-prompt-chaining.md)
