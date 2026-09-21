# Appendix A — Advanced Prompting Techniques

> **Source:** *Agentic Design Patterns* — Appendix A: Advanced Prompting Techniques (PDF pp. 347–375 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Prompting is an **engineering discipline**, not just asking questions: clear instructions, examples, structure, reasoning aids, tool/action loops and dynamic context turn a general LLM into a reliable component. Agents depend on it — every agent step is a prompt.

## 1. Core principles

| Principle | Guidance |
|---|---|
| **Clarity & specificity** | Define task, output format, constraints; avoid vagueness. |
| **Conciseness** | Direct wording, active verbs (Analyze, Classify, Extract, Generate, Rank, Summarize, Translate, …). "Summarize the text" beats "Think about summarizing this." |
| **Instructions over constraints** | Say what to do rather than what not to do; keep hard "don'ts" for safety/format. |
| **Experiment & iterate** | Draft → test → analyse → refine; vary phrasing and settings (temperature, top-p); document attempts. |

## 2. Basic techniques

| Technique | What | Use when |
|---|---|---|
| **Zero-shot** | Instruction only. | Common tasks; try first. |
| **One-shot** | One input→output example. | A specific format/style is needed. |
| **Few-shot** | ~3–5 diverse, correct examples. | Classification, schema extraction, style. **Mix class order** to avoid overfitting to sequence. |
| **Many-shot** | Hundreds of examples in long context. | Complex patterns with long-context models. |

Example quality matters more than quantity: one wrong example can mislead the model.

## 3. Structuring prompts

- **System prompting** – persistent rules/persona/safety ("helpful and harmless assistant…"); can be auto-optimised (e.g. Vertex AI Prompt Optimizer).
- **Role prompting** – "Act as a seasoned travel blogger" sets expertise, tone and style.
- **Delimiters** – XML tags (`<instruction>`, `<article>`), triple backticks or `---` to separate instructions, context, examples and input.
- **Context engineering** – *dynamically* assemble the information the model needs. Layers:
  1. **System prompt** (fixed operating rules),
  2. **External data**: retrieved documents (RAG) and tool outputs,
  3. **Implicit data**: user identity, history, environment state (needs privacy/governance, especially in enterprise, health, finance).

  Output quality depends more on the **richness and relevance of context** than on the model architecture. In agents it underlies memory, decisions and coordination; "engineering" = runtime pipelines to fetch/transform context + feedback loops (optimisers) to improve it. It moves systems from stateless chatbots to situation-aware ones.
- **Structured output** – request JSON/XML/CSV/Markdown tables (forces structure, limits hallucination). Enforce with **Pydantic**: `User.model_validate_json(llm_output)` parses *and* validates in one step ("parse, don't validate" at component boundaries); use `xmltodict` + field aliases for XML.

## 4. Reasoning techniques

| Technique | How | Trade-off |
|---|---|---|
| **Chain of Thought** | "Let's think step by step" (zero-shot) or examples with worked reasoning (few-shot). | More tokens/latency; more accurate and interpretable. Put the answer *after* the reasoning; use temperature 0 for single-answer tasks. |
| **Self-consistency** | Sample several reasoning paths at higher temperature; **majority vote** on final answers. | Multiplies cost. |
| **Step-back prompting** | First ask a general/principle question, feed the answer as context to the specific task. | Extra call; better grounding. |
| **Tree of Thoughts** | Explore and evaluate several branches, backtrack. | Heavier to implement. |

## 5. Action & interaction

- **Tool use / function calling:** describe tools (name, purpose, parameters); the model emits a structured call (JSON), **your system executes it** and returns the result.
- **ReAct:** loop of *Thought → Action → Observation* until *Final Answer* (e.g. search "capital of France", then "population of Paris", then answer).

## 6. Advanced techniques

- **Automatic Prompt Engineering (APE):** an LLM generates candidate prompts, they're scored on sample inputs, the best is kept.
- **Programmatic optimisation (DSPy-style):** treat prompts as modules. Provide a **goldset** of good input/output pairs and an **objective metric**; an optimiser (e.g. Bayesian) searches *which few-shot examples* and *which instruction wording* maximise the score.
- **Iterative refinement:** human loop — generic prompt → add emphasis → add product name, features, audience.
- **Negative examples:** show what *not* to output — use sparingly.
- **Analogies** ("act as a data chef…"), **factored cognition / decomposition** (outline → sections → conclusion; see Ch. 1), **RAG** (Ch. 14), **user-persona pattern** (describe the *audience*: "high-school student with no prior knowledge").
- **Google Gems:** saved, task-specific instruction sets on top of Gemini so you don't re-supply context every time.
- **Meta-prompting:** ask an LLM to critique and improve your prompt (spots ambiguity, suggests delimiters, format, persona, examples). Always test its suggestions.

## 7. Task-specific

- **Code:** generate, explain, translate, debug/review — always give language/version, context, and the error/traceback.
- **Multimodal:** combine image/audio/video with text (e.g. explain a diagram).

## 8. Best-practice checklist

Provide examples · keep prompts simple · specify output format/length/style · prefer instructions to constraints · control max tokens · use **variables/templates** in app prompts · try different phrasings and formats · shuffle classes in few-shot classification · re-test after **model updates** · request structured output · collaborate on prompts · **document attempts** · **store prompts in the codebase** (separate, versioned files) · **automate tests and evaluation** for production (see Ch. 19).

## Key takeaways

- Clear, specific, iterated prompts + good examples are the base layer.
- Structure (system/role/delimiters/structured output) gives control and machine-readability.
- CoT/self-consistency/step-back/ToT improve reasoning; ReAct and function calling give agents hands; RAG and context engineering give them senses.
- Validate LLM output programmatically (Pydantic) — reliable agents need predictable interfaces.

**Prev:** [21 — Exploration and Discovery](21-exploration-and-discovery.md) · **Next:** [Appendix B — Agentic Interactions: GUI to Real World](appendix-b-agentic-interactions.md)
