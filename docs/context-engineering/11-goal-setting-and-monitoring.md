# 11 — Goal Setting and Monitoring

> **Source:** *Agentic Design Patterns* — Chapter 11: Goal Setting and Monitoring (PDF pp. 181–193 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Give the agent an explicit, **measurable objective** and a way to **track progress toward it**. Monitoring closes the loop: if the agent drifts, it corrects, re-plans or escalates. Without goals and monitoring an agent just executes tasks with no way of knowing whether it succeeded.

## Concept

Like planning a trip: know the destination (goal state), the starting point (initial state), the constraints, then the steps (Ch. 6). This chapter adds **success criteria** and **feedback**:

1. Define goals — ideally **SMART** (specific, measurable, achievable, relevant, time-bound).
2. Define metrics / success criteria.
3. Monitor actions, environment state and tool outputs.
4. Compare with the goal; **adapt, revise the plan, or escalate**.

In Google ADK, goals are usually conveyed through agent instructions, and monitoring through state management and tool interactions.

## Use cases

| Domain | Goal | Monitoring signal |
|---|---|---|
| Customer support | Resolve a billing inquiry | Billing change confirmed, customer feedback; escalate if unresolved |
| Personalised learning | Improve algebra understanding | Exercise accuracy and time; adapt material |
| Project management | Milestone X by date Y | Task status, comms, resources; flag delays |
| Trading bot | Maximise gains within risk tolerance | Market data, portfolio value, risk indicators |
| Autonomous vehicle | Get passengers safely from A to B | Environment, vehicle state, route progress |
| Content moderation | Remove harmful content | False positive/negative rates; escalate ambiguous cases |

## Example: a self-refining code-writing agent

Inputs: a **use case** and a **list of goals** ("simple", "functionally correct", "handles edge cases", …).

Loop (max 5 iterations):
1. **Generate** code (prompt includes previous code and feedback).
2. **Critique**: an LLM reviewer compares code with the goals.
3. **Goals met?** A second LLM call answers only `True`/`False` — a trivially parseable stop signal.
4. If `False`, feed the critique back and refine; else stop.
5. Save to a `.py` file with a header comment and a short generated filename.

```python
for i in range(max_iterations):
    code = llm(generate_prompt(use_case, goals, previous_code, feedback))
    feedback = llm(critique_prompt(code, goals))
    if goals_met(feedback, goals):     # LLM returns "True" / "False"
        break
    previous_code = code
```

### Caveats (the book stresses this is *not* production code)

- The LLM may misunderstand a goal or hallucinate success.
- The same model writing *and* judging has trouble noticing it's going wrong → use **separate agents/roles** (e.g. Peer Programmer, Code Reviewer, Documenter, Test Writer, Prompt Refiner).
- Still **run and test** the output; LLMs don't guarantee correct code.
- Naive monitoring can loop forever → enforce iteration/time budgets.

## When to use

When an agent must autonomously carry out a multi-step task, adapt to changing conditions, and reliably reach a high-level objective with little human supervision.

## Key takeaways

- Goals give direction; monitoring tells you whether you're getting there.
- Make success criteria explicit and machine-checkable where possible.
- Feedback loops let agents adapt, re-plan or escalate.
- Separate the "doer" from the "judge" and cap the number of iterations.

**Prev:** [10 — Model Context Protocol](10-model-context-protocol.md) · **Next:** [12 — Exception Handling and Recovery](12-exception-handling-and-recovery.md)
