# 21 — Exploration and Discovery

> **Source:** *Agentic Design Patterns* — Chapter 21: Exploration and Discovery (PDF pp. 333–346 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Instead of only executing known tasks or optimising inside a fixed solution space, the agent **proactively seeks new information, forms hypotheses, runs experiments and finds "unknown unknowns."** Typically implemented as a *team* of agents mirroring the scientific method: **generate → critique → rank → evolve**.

## Use cases

- **Scientific research automation:** design experiments, analyse results, propose new hypotheses (materials, drugs, principles).
- **Game playing / strategy** (AlphaGo-style exploration of game states).
- **Market research & trend spotting** across unstructured data.
- **Security vulnerability discovery.**
- **Creative generation:** explore style/theme combinations.
- **Personalised education:** prioritise learning paths by progress and weaknesses.

Related: exploration–exploitation trade-off from reinforcement learning (try new things vs. use what works).

## Case 1 — Google AI Co-Scientist

A Gemini-based **multi-agent** collaborator for hypothesis generation, proposal refinement and experiment design, coordinated by a **supervisor** in an asynchronous task framework that scales compute flexibly.

| Agent | Role |
|---|---|
| **Generation** | Produces initial hypotheses via literature exploration and simulated scientific debates. |
| **Reflection** | Peer-reviewer: correctness, novelty, quality. |
| **Ranking** | **Elo-based tournament** — hypotheses compete in simulated debates. |
| **Evolution** | Refines top hypotheses: simplify, synthesise, try unconventional reasoning. |
| **Proximity** | Builds a proximity graph to cluster similar ideas. |
| **Meta-review** | Aggregates patterns across reviews/debates into feedback for the whole system. |

Loop: **generate → debate → evolve**, using **test-time compute scaling** (more inference compute ⇒ better hypotheses, measured by Elo).

Reported validation:
- GPQA "diamond": top-1 accuracy 78.4%; Elo correlates with accuracy; beat other SOTA models and expert "best guesses" on 15 hard problems.
- **Drug repurposing for AML:** proposed candidates (e.g. KIRA6, with no prior AML evidence) that inhibited tumour-cell viability in vitro.
- **Liver fibrosis:** novel epigenetic targets validated in human hepatic organoids.
- **Antimicrobial resistance:** in two days re-derived an unpublished result (cf-PICIs and phage tails) that a lab had needed a decade to establish.

Design philosophy: **augmentation, "scientist-in-the-loop"** (natural-language guidance). Limits: relies on open-access literature, little access to negative results, inherits LLM hallucinations. Safety: research goals and hypotheses screened; tested on 1,200 adversarial goals; released via a Trusted Tester Program.

## Case 2 — Agent Laboratory (+ AgentRxiv)

An open-source autonomous research workflow (MIT licence) that augments researchers:

1. **Literature review** – agents gather and analyse papers (e.g. arXiv).
2. **Experimentation** – plan, prepare data, write/run Python, use Hugging Face models, iterate on results.
3. **Report writing** – synthesise into an academic-style paper (LaTeX).
4. **Knowledge sharing** – **AgentRxiv**, a repository where agents share and build on each other's findings.

Roles mirror an academic hierarchy: **Professor** (sets agenda, delegates), **PostDoc** (runs the research, writes code and papers), **Reviewers**, **ML Engineer** and **Software Engineer** agents that dialogue to write simple data-prep code.

**Tripartite judgement:** three reviewer agents with different personas — one critical of experiment quality, one "harsh but fair" wanting impact, one wanting novelty — each fill a rubric in a strict JSON format (Summary, Strengths, Weaknesses, Originality, Quality, Clarity, Significance, Soundness, Overall 1–10, Confidence, Decision = Accept/Reject only, …) after a brief `<THOUGHT>` note-taking phase.

## Patterns to reuse

- Separate **generator**, **critic**, **ranker** and **evolver** roles (Ch. 4, 7).
- Rank ideas by a **tournament/Elo** rather than a single subjective score.
- Give different reviewer personas the same rubric to reduce single-judge bias.
- Scale **test-time compute** for better ideas (Ch. 17).
- Keep humans in the loop and add safety screening of goals and outputs (Ch. 13, 18).

## When to use

Open-ended, complex or fast-changing domains where the solution space isn't fully defined and the goal is new hypotheses, strategies or insights rather than optimising a known process.

## Key takeaways

- Exploration is proactive: set sub-goals, seek novelty, experiment.
- Multi-agent scientific-method pipelines (generate/debate/evolve; literature → experiment → report) are the leading design.
- These systems augment human researchers; they need oversight and safety measures.

**Prev:** [20 — Prioritization](20-prioritization.md) · **Next:** [Appendix A — Advanced Prompting Techniques](appendix-a-advanced-prompting.md)
