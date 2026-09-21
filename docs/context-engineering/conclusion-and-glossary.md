# Conclusion and Glossary

> **Source:** *Agentic Design Patterns* — Conclusion (PDF pp. 423–427) and Glossary (PDF pp. 428–446) of `Agentic_Design_Patterns_Complete.pdf`. Condensed rewrite. (The PDF's glossary appears twice — a short version on pp. 428–430 and a longer one on pp. 431–446; this page follows the content of both. The PDF's "Index of Terms" on pp. 447–458 is omitted.)

## Conclusion — the book's 21 patterns in four groups

| Group | Patterns | Idea |
|---|---|---|
| **1. Core execution & task decomposition** | Prompt Chaining (1), Routing (2), Parallelization (3), Planning (6) | Break work into steps, choose paths, run independent parts concurrently, and plan toward a goal. |
| **2. Interacting with the external environment** | Tool Use (5), Knowledge Retrieval / RAG (14) | Ground the agent in real APIs, data and documents. |
| **3. State, learning & self-improvement** | Memory (8), Reflection (4), Learning & Adaptation (9) | Keep context, critique and refine output, improve from experience. |
| **4. Collaboration & communication** | Multi-Agent Collaboration (7), A2A (15), MCP (10) | Specialised agents working together, with standard protocols for agents and tools. |

The remaining patterns are cross-cutting: **Goal Setting & Monitoring (11)**, **Exception Handling & Recovery (12)**, **Human-in-the-Loop (13)**, **Resource-Aware Optimization (16)**, **Reasoning Techniques (17)**, **Guardrails/Safety (18)**, **Evaluation & Monitoring (19)**, **Prioritization (20)**, **Exploration & Discovery (21)**.

### Patterns work best combined

Example — an autonomous **research assistant**:

1. **Planning** – a Planner turns "analyse the impact of quantum computing on cybersecurity" into research steps.
2. **Tool Use** – each step calls search (Google, Vertex AI Search) or databases (arXiv, financial APIs).
3. **Multi-Agent Collaboration** – a *Researcher* gathers material, a *Writer* drafts using the plan as an outline.
4. **Reflection** – a *Critic* checks logic, facts and clarity; the Writer self-corrects.
5. **Memory Management** – holds the plan, gathered data, drafts and feedback across the whole workflow.

Five patterns together achieve what no single prompt or simple chain could.

### Looking ahead

- Greater autonomy and reasoning: ambiguity, causal/abstract reasoning, common sense; neuro-symbolic approaches; a shift from human-*in*-the-loop (co-pilot) to human-*on*-the-loop (agents run long tasks, report at completion or on critical exceptions).
- **Agent ecosystems and standards:** marketplaces of agents-as-a-service; MCP and A2A-style standards for exchanging data, context, goals and capabilities (the "Awesome Agents" GitHub list curates open-source agents and frameworks).
- **Open challenges:** safety, alignment and robustness — preventing drift from original purpose, resisting adversarial attacks, handling unpredictable environments — requiring new safety patterns and rigorous testing/validation.

The author's closing image: patterns are the palette and brushstrokes; the craft is in composing them. *"The canvas is before you, the patterns are in your hands. Now, it is time to build."*

---

## Glossary (condensed)

### Fundamental concepts
- **Prompt** – the input (question/instruction) given to a model; its quality and structure heavily shape the output.
- **Context window** – the maximum tokens a model can process at once (input + output). Anything outside is ignored; larger windows allow longer conversations and documents.
- **In-context learning** – learning a task from examples inside the prompt, with no retraining.
- **Zero-/one-/few-shot prompting** – zero, one, or a few examples to guide the model; more examples usually help.
- **Multimodality** – handling text, images, audio, etc.
- **Grounding** – tying outputs to verifiable sources (often via RAG) to improve accuracy and reduce hallucination.

### Core model architectures
- **Transformer** – the foundation of most LLMs; self-attention captures relationships across long sequences.
- **RNN** – earlier sequential architecture with loop-based "memory".
- **Mixture of Experts (MoE)** – a router activates a small subset of expert sub-networks per input: huge parameter counts at manageable compute.
- **Diffusion models** – generate (esp. images) by learning to reverse a noising process.
- **Mamba** – selective state-space model, efficient on very long sequences; potential Transformer alternative.

### LLM development lifecycle
**Pre-training → fine-tuning → alignment.**
- *Pre-training objectives:* causal LM (next token), masked LM, denoising, contrastive learning, next-sentence prediction.
- *Fine-tuning:* supervised fine-tuning (SFT), instruction tuning, parameter-efficient methods (**LoRA**, **QLoRA**); RAG can further connect the model to external knowledge.
- *Alignment & safety:* **RLHF** (reward model from human preferences, often with **PPO**), simpler alternatives **DPO** and **KTO**, and **guardrails** as a final real-time safety layer.

### Enhancing agent capabilities
- **Agent** – a system that perceives its environment and acts autonomously toward goals.
- **Chain of Thought (CoT)** – reasoning step by step before answering.
- **Tree of Thoughts (ToT)** – explore and evaluate multiple reasoning branches.
- **ReAct** – loop of thought → action (tool) → observation.
- **Planning** – decompose a goal into ordered sub-tasks.
- **Deep Research** – autonomous, iterative searching, synthesising and follow-up questioning.
- **Critique model** – a model that reviews another model's output to find errors and improve quality.

**Prev:** [Appendix G — Coding Agents](appendix-g-coding-agents.md) · **Back to:** [README](README.md)
