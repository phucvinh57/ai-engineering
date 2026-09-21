# 17 — Reasoning Techniques

> **Source:** *Agentic Design Patterns* — Chapter 17: Reasoning Techniques (PDF pp. 260–283 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Reasoning techniques make an agent's **intermediate thinking explicit** and give it **more compute at inference time** (more steps, more candidate paths, tools) so it solves multi-step problems more accurately. The core loop for agents is **Thought → Action → Observation** (ReAct).

## Technique catalogue

| Technique | Idea | Notes |
|---|---|---|
| **Chain-of-Thought (CoT)** | Generate intermediate reasoning steps ("think step by step" or few-shot examples showing steps). | Big gains on arithmetic, commonsense, symbolic tasks; transparent and debuggable. |
| **Tree-of-Thought (ToT)** | Branch into several reasoning paths, evaluate them, **backtrack**. | Good for strategic planning where one line of thought may fail. |
| **Self-correction / self-refinement** | The agent critiques its own draft against the original requirements (accuracy, completeness, clarity, tone, engagement, verbosity), proposes concrete fixes, rewrites. | Same idea as Reflection (Ch. 4), inside the reasoning trace. |
| **Program-Aided LMs (PALMs)** | LLM writes **code** (e.g. Python) and a deterministic interpreter runs it; the result is turned back into language. | Exact maths/logic. ADK: `BuiltInCodeExecutor`, or a coding agent exposed as `AgentTool`. |
| **RLVR** (Reinforcement Learning with Verifiable Rewards) | How "reasoning models" are trained: on problems with checkable answers (math, code) so the model learns long, adaptive reasoning traces with self-correction and backtracking. | The model spends variable "thinking time" — thousands of tokens on hard problems. |
| **ReAct** | Interleave reasoning with tool use: *Thought → Action → Observation → Thought …* until a `finish` action. | Adapts plans from real feedback; few-shot trajectories guide it. Thoughts every step for knowledge tasks, sparse for long action sequences. |
| **Chain of Debates (CoD)** | Several diverse models argue, critique and counter one another (Microsoft) — an "AI peer review". | Higher accuracy, less bias, transparent record. |
| **Graph of Debates (GoD)** | Debate as a graph: arguments are nodes with *supports/refutes* edges; branches evolve and merge; the answer is the best-supported cluster (ground truth, search-grounded facts, or multi-model consensus). | More realistic than a linear chain. |
| **MASS** (Multi-Agent System Search) | Automates design of multi-agent systems by interleaving **prompt** and **topology** optimisation. | See below. |

### CoT prompt template (structure)
Persona + numbered process: *1) Analyse the query 2) Formulate search queries 3) Simulate/perform retrieval 4) Synthesise 5) Review and refine.* The model's numbered "thoughts" are the chain; the polished result is the final answer.

### MASS in three stages
1. **Block-level prompt optimisation** – tune each agent role in isolation (e.g. a debater prompted as an "expert fact-checker for a major publication").
2. **Workflow topology optimisation** – search agent arrangements guided by each topology's *incremental influence* over a baseline. Coding result: one predictor with several reflection rounds + one executor that runs test cases — iterative self-correction **plus** external verification beat simpler designs.
3. **Workflow-level prompt optimisation** – jointly re-tune all prompts for the chosen topology (meta-knowledge about the dataset, few-shot examples, high-stakes role-play).

Principles: optimise individual agents first; compose *influential* topologies rather than searching blindly; finish with joint optimisation of interdependencies.

## Scaling Inference Law

Performance improves predictably with **compute spent at inference**, not only with model size/training. A **smaller model given a bigger "thinking budget"** (multiple candidates, self-consistency, beam search + a selector, iterative refinement) can beat a larger model doing a single pass. It lets you balance model size (memory), latency and running cost — "bigger is better" is not always true. Ties to Resource-Aware Optimization (Ch. 16).

## Deep Research

Agents that trade a **time budget** (a few minutes) for a synthesised report: run targeted searches → read and reason → spot gaps/contradictions → run follow-up searches → final structured, cited summary. Products: Perplexity, Google Gemini, OpenAI. Google's open-source **DeepSearch** quickstart (LangGraph + Gemini): generate queries → parallel `web_research` → `reflection` node (knowledge-gap analysis) → conditional edge back to research or to `finalize_answer`.

## Use cases

Multi-hop question answering, mathematical problem solving (with code), code debugging with self-correction, strategic planning (ReAct), medical diagnosis, legal analysis — anywhere showing the reasoning matters as much as the answer.

## Practical notes

- Use reasoning depth **adaptively**: cheap single-pass for easy tasks, more thinking for hard ones.
- Offload exact computation to code/tools (PALMs) rather than trusting the model's arithmetic.
- Keep reasoning traces out of the final context if they're long — context budget matters (see Ch. 8, 16).
- Verification (tests, tools, second opinions) beats pure self-judgment.

## When to use

When a problem is too complex for a one-shot answer: decomposition, multi-step logic, tools or external data, strategic planning and adaptation — especially when the "work" must be inspectable.

## Key takeaways

- CoT = internal monologue; ToT/self-correction = deliberation; ReAct = reasoning + acting loop.
- Inference-time compute is a lever, often cheaper than a bigger model.
- Multi-agent debate and MASS extend reasoning to teams of agents.
- Deep Research is the flagship application combining these techniques.

**Prev:** [16 — Resource-Aware Optimization](16-resource-aware-optimization.md) · **Next:** [18 — Guardrails / Safety Patterns](18-guardrails-safety-patterns.md)
