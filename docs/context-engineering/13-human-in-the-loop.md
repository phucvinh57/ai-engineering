# 13 — Human-in-the-Loop (HITL)

> **Source:** *Agentic Design Patterns* — Chapter 13: Human-in-the-Loop (PDF pp. 202–210 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Keep humans involved where **judgment, ethics, nuance or high stakes** matter. The AI does the scalable heavy lifting; humans validate, correct, decide and teach. It augments people rather than replacing them.

## Forms of human involvement

| Aspect | Meaning |
|---|---|
| **Oversight** | Monitor outputs via logs or dashboards to keep the agent within guidelines. |
| **Intervention & correction** | The agent asks for help on errors/ambiguity; humans fix or supply data. |
| **Feedback for learning** | Human preferences refine models (e.g. RLHF, labelled data). |
| **Decision augmentation** | AI analyses and recommends; the human decides (e.g. loan officer, judge). |
| **Human–agent collaboration** | Agent handles routine processing; human handles creative/negotiation work. |
| **Escalation policies** | Explicit rules for *when and how* the agent hands off to a human. |

**Human-on-the-loop** is a variation: humans set the **policy** (e.g. "70% tech / 30% bonds, ≤5% per company, auto-sell at −10%"; or "route any call mentioning *service outage* to tech support, offer a human if the caller sounds frustrated"), and the AI executes it at speed without per-case approval.

## Use cases

Content moderation (ambiguous cases → human), autonomous driving (hand control back in extreme situations), fraud detection (high-risk alerts → analyst), legal document review, complex/emotional customer support, data labelling, refining generative content, and autonomous-network operations (approve high-risk changes).

## Caveats

- **Doesn't scale:** humans can't review millions of items → hybrid designs (automation for volume, humans for accuracy).
- **Depends on expertise:** only a skilled developer can spot subtle code bugs; annotators need training to give useful corrections.
- **Privacy:** sensitive data may need anonymising before a human sees it.

## Example (Google ADK): support agent with escalation

A technical-support agent with tools `troubleshoot_issue`, `create_ticket` and `escalate_to_human`. Its instruction says: check the customer's support history in `state`, troubleshoot, log a ticket if unresolved, and **escalate to a human for complex issues**. A `before_model` **callback** injects personalisation (name, tier, recent purchases) from state into every LLM request as a system message before the model is called — a small but real example of **context engineering**.

```python
def personalization_callback(callback_context, llm_request):
    info = callback_context.state.get("customer_info", {})
    llm_request.contents.insert(0, system_msg(f"Customer: {info['name']}, tier: {info['tier']}"))
    return None  # continue with the modified request
```

LangChain has comparable interrupt/approval mechanisms.

## Design tips

- Define **clear triggers** for escalation (low confidence, high risk/cost, policy violation, user request, repeated failure).
- Pause **before** irreversible actions and ask for approval; give the human enough context (what, why, alternatives) to decide quickly.
- Record human decisions as feedback/training data.

## When to use

When errors carry significant safety, ethical or financial consequences (healthcare, finance, autonomous systems), when tasks are ambiguous, or when you need high-quality human labels/refinement.

## Key takeaways

- HITL blends AI scale with human judgment; escalation policies are essential.
- Trade-offs: accuracy vs. volume, need for skilled operators, privacy.
- Human-on-the-loop = humans set policy, AI acts.
- Enables responsible deployment plus continuous improvement from human feedback.

**Prev:** [12 — Exception Handling and Recovery](12-exception-handling-and-recovery.md) · **Next:** [14 — Knowledge Retrieval (RAG)](14-knowledge-retrieval-rag.md)
