# 09 — Learning and Adaptation

> **Source:** *Agentic Design Patterns* — Chapter 9: Learning and Adaptation (PDF pp. 152–164 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Learning lets an agent go beyond fixed instructions: it changes its **thinking, actions or knowledge** from experience and so gets better over time and copes with novel situations. "Adaptation" is the visible behaviour change that results from learning.

## Ways agents learn

| Approach | Idea | Fits |
|---|---|---|
| **Reinforcement learning** | Try actions, get rewards/penalties, learn a policy. | Robots, games, trading |
| **Supervised** | Learn from labelled input→output examples. | Email sorting, trend prediction |
| **Unsupervised** | Find structure in unlabelled data. | Exploration, clustering |
| **Few-/zero-shot (LLM)** | Adapt to new tasks from a few examples or clear instructions. | Rapid task changes |
| **Online learning** | Continuously update from a data stream. | Real-time, dynamic settings |
| **Memory-based** | Recall past experiences for similar situations (see Ch. 8, RAG in Ch. 14). | Agents with memory |

### PPO vs. DPO (aligning behaviour)

- **PPO (Proximal Policy Optimization):** an RL algorithm that improves a policy in *small, safe steps*. A **clipped objective** creates a "trust region" so an update can't stray too far from the working policy → stable training.
- **DPO (Direct Preference Optimization):** for aligning LLMs with human preferences. The classic route is two steps — train a **reward model** from human comparisons, then fine-tune with PPO (complex, unstable, reward can be "hacked"). DPO skips the reward model: it updates the LLM directly to make preferred responses more likely and disfavoured ones less likely.

## Applications

Personal assistants that adapt to a user; trading bots tuning parameters; apps that adjust UI from usage; robots/vehicles improving navigation; fraud detection learning new patterns; recommenders; game AI; and **knowledge-base learners** that store problems + proven solutions via RAG and reuse them.

## Case study: SICA — Self-Improving Coding Agent

An agent that **edits its own source code** (it is both modifier and modified).

Loop:
1. Review an **archive** of past versions with benchmark scores (weighted by success, time, compute cost).
2. Pick the best version.
3. Analyse the archive, propose and apply changes to its own code.
4. Benchmark the new version; add to the archive; repeat.

Self-invented improvements included a Smart Editor → Diff-Enhanced editor → AST-based minimal-diff tools, and navigation tools (AST Symbol Locator → Hybrid Symbol Locator).

Architecture worth copying:
- Base toolkit (file ops, shell, calculator) plus **sub-agents** (coding, problem-solving, reasoning) that decompose tasks and **keep the LLM's context length under control**.
- An **asynchronous overseer LLM** watching a call-graph and event log, detecting loops/stagnation, able to warn or cancel.
- **Structured context window:** system prompt (goals, tool docs) → core prompt (problem, open files, directory map) → assistant messages (reasoning, tool calls/results, overseer notes). File changes are stored as diffs and periodically consolidated.
- **Docker isolation** for safety and an observability UI for the event bus.
- Open challenge: getting the LLM to propose genuinely *novel* modifications each iteration.

## AlphaEvolve and OpenEvolve

- **AlphaEvolve (Google):** LLMs (Gemini Flash for breadth of proposals, Pro for depth) + automated evaluators + an evolutionary loop to discover/optimise algorithms. Results: 0.7% global compute saved in data-centre scheduling, TPU Verilog suggestions, 23% faster Gemini kernel, up to 32.5% FlashAttention GPU instruction optimisation, a 48-multiplication scheme for 4×4 complex matrices, and rediscovery/improvement of many open maths problems.
- **OpenEvolve (open source):** controller orchestrating a program sampler, program database, evaluator pool and LLM ensemble; evolves whole files, multi-language, multi-objective, distributed evaluation. Usage: `OpenEvolve(initial_program_path, evaluation_file, config_path).run(iterations=1000)`.

## Practical notes

- Self-modifying or online-learning agents need **sandboxing, monitoring and rollback**.
- For multi-agent learning, tuning data should capture the **full interaction trajectory** (each agent's inputs and outputs).
- The cheapest form of learning for LLM agents is often **memory + reflection** (store lessons; rewrite prompts), not weight updates.

## When to use

Agents in dynamic, uncertain or evolving environments, or needing personalisation and continuous improvement.

## Key takeaways

- Learning = improving from experience; adaptation = the resulting behaviour change.
- Options range from RL/PPO/DPO to memory-based and prompt-level self-improvement.
- SICA shows structured context, sub-agents and an overseer are key to self-improving systems.
- AlphaEvolve shows LLM + evaluator + evolution can discover new algorithms.

**Prev:** [08 — Memory Management](08-memory-management.md) · **Next:** [10 — Model Context Protocol](10-model-context-protocol.md)
