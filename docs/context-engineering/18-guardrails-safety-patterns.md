# 18 — Guardrails / Safety Patterns

> **Source:** *Agentic Design Patterns* — Chapter 18: Guardrails/Safety Patterns (PDF pp. 284–303 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Guardrails are a **layered defence** that keeps agents safe, ethical, on-topic and predictable. They don't limit usefulness — they make an autonomous system trustworthy. No single check is enough; combine several.

## Where guardrails go (defence in depth)

| Layer | Examples |
|---|---|
| **Input validation / sanitisation** | Moderation APIs, schema validation (Pydantic), jailbreak and off-topic detection *before* the main agent sees the input. |
| **Output filtering / post-processing** | Scan generated text for toxicity, bias, leaked data; redact or block. |
| **Behavioural constraints (prompt-level)** | Role/goal/backstory, explicit "never do X" instructions, narrow specialist agents. |
| **Tool-use restrictions** | Limit which tools and arguments are allowed; validate arguments in a `before_tool` callback. |
| **External moderation APIs** | Dedicated content-safety services. |
| **Human oversight (HITL)** | Escalate risky or critical decisions (Ch. 13). |

A **small, fast, cheap model** (Gemini Flash / Flash-Lite) can act as an extra gatekeeper, pre-screening inputs and double-checking outputs for policy violations.

## Use cases

Customer-service bots (block toxic input, refuse medical/legal advice, escalate), content generation (flag/redact harmful text), tutors (curriculum-bound, no homework answers), legal assistants (never definitive legal advice), HR tools (avoid discriminatory criteria), social-media moderation, scientific assistants (don't fabricate data).

## Example 1 — CrewAI "policy enforcer" agent

A dedicated agent screens user input before it reaches the primary AI:

- A fast model (`gemini-2.0-flash`, temperature 0) plays the **AI Content Policy Enforcer**.
- Policy directives: (1) **instruction subversion / jailbreaks** ("ignore previous rules", "reveal your instructions"); (2) **prohibited content** (hate, hazardous acts, explicit, abusive); (3) **off-domain** talk (politics, religion, sports, gossip, homework cheating); (4) **brand/competitor** mentions.
- Includes *examples of permissible inputs* and a tie-break rule: **if ambiguous, default to "compliant"** (avoid over-blocking).
- Output contract: JSON `{compliance_status, evaluation_summary, triggered_policies}`.
- A Pydantic model `PolicyEvaluation` plus a **task-level `guardrail=` validation function** checks the LLM output itself (strips ```json fences, validates schema and allowed values); on failure the task retries/errors.
- A wrapper returns `(is_compliant, message, triggered_policies)` and the app proceeds or blocks. Tested on eight inputs, including a jailbreak, competitor comparison, abuse, essay request and political question.

## Example 2 — Vertex AI / ADK callbacks

- **`before_tool_callback`** validates tool arguments before execution, e.g. compare the `user_id` in the tool args with the one in session state; return an error dict to **block** the call, or `None` to allow.
- Prompt-based **AI Safety Guardrail** (Flash model) returns `{"decision": "safe"|"unsafe", "reasoning": ...}` with the same categories; unsure → "safe".
- Other Vertex practices: agent/user identity and authorisation, built-in Gemini safety filters and system instructions, **isolated code execution**, monitoring, network boundaries (VPC Service Controls), a prior **risk assessment**, and **sanitising model output before rendering in a UI** (prevent script injection).

## Engineering reliable agents (treat agents as software)

- **Checkpoint & rollback:** each validated state is a "commit"; rollback is fault tolerance — like a transactional database.
- **Modularity / separation of concerns:** small specialised agents are easier to test, isolate and optimise than a monolith.
- **Observability via structured logs:** record tool calls, data received, reasoning and confidence — not just the final answer.
- **Principle of least privilege:** a news summariser gets a news API only — limits the blast radius of errors and attacks.
- Plus: input schema validation, retries with exponential backoff, rate limits, context-window management, secure API-key handling, adversarial training/testing.

## Practical checklist

1. Screen inputs (jailbreak/injection, policy) with a cheap model **and** deterministic rules.
2. Validate **structured** outputs and tool arguments in code; never trust free text.
3. Constrain tools and permissions; sandbox execution.
4. Filter/sanitise outputs; redact sensitive data.
5. Log everything; evaluate and refine guardrails continuously (Ch. 19).
6. Add human approval for high-impact actions.

## When to use

Any application whose agent output can affect users, systems or reputation — customer-facing bots, content platforms, finance/health/legal settings.

## Key takeaways

- Layer guardrails: input → prompt constraints → tool limits → output filters → human oversight.
- Use fast models as gatekeepers; make decisions and outputs structured and validated.
- Apply classic engineering: least privilege, rollback, modularity, observability.
- Guardrails need ongoing monitoring and refinement as threats evolve.

**Prev:** [17 — Reasoning Techniques](17-reasoning-techniques.md) · **Next:** [19 — Evaluation and Monitoring](19-evaluation-and-monitoring.md)
