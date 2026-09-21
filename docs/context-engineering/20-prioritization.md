# 20 — Prioritization

> **Source:** *Agentic Design Patterns* — Chapter 20: Prioritization (PDF pp. 323–332 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

When an agent faces many possible actions, conflicting goals and limited resources, it must **rank what to do next** by criteria such as urgency and importance, and **re-rank as conditions change**. Without this it becomes slow, unfocused or fails key objectives.

## Four elements

1. **Criteria definition** – the metrics: *urgency*, *importance* (impact on the main goal), *dependencies* (prerequisites), *resource availability*, *cost/benefit*, *user preferences*.
2. **Task evaluation** – score each candidate against the criteria (simple rules, weighted scores, or LLM reasoning).
3. **Scheduling / selection logic** – pick the next task or ordering (a priority queue or a planner).
4. **Dynamic re-prioritisation** – update when a critical event happens or a deadline nears.

## Levels of prioritisation

- **Goal level** – which overarching objective to pursue.
- **Sub-task level** – order of steps inside a plan.
- **Action level** – the next immediate action.

## Use cases

| Domain | Example |
|---|---|
| Customer support | Outage reports before password resets; VIP customers first |
| Cloud computing | Critical apps at peak, batch jobs off-peak |
| Autonomous driving | Collision braking > lane keeping > fuel efficiency |
| Trading | Rank trades by market conditions, risk tolerance, margin, news |
| Project management | Deadlines, dependencies, availability, strategic value |
| Cybersecurity | Alerts by threat severity, impact, asset criticality |
| Personal assistants | Calendar/notifications by user-defined importance and deadlines |

## Example: LangChain Project-Manager agent

A small in-memory `SuperSimpleTaskManager` (Pydantic `Task`: `id`, `description`, `priority` P0/P1/P2, `assigned_to`) exposed as **tools** with validated argument schemas:

- `create_new_task` (call first to get an id)
- `assign_priority_to_task`
- `assign_task_to_worker`
- `list_all_tasks`

The system prompt encodes the policy: *create the task → map words like "urgent/ASAP/critical" to **P0** → assign the named worker → if priority or assignee is missing, apply defaults (**P1**, 'Worker A') → finish by listing all tasks.* An `AgentExecutor` with `ConversationBufferMemory` runs two scenarios: an urgent login-system task for Worker B, and a vague low-urgency marketing-site review that receives defaults.

```text
System policy (abridged)
1. create_new_task → get task_id
2. urgent/ASAP/critical → P0; named worker → assign
3. missing info → P1 + Worker A
4. list_all_tasks
```

Takeaway: the LLM interprets ambiguous language, chooses tools and sequences them; deterministic tools enforce valid values (`P0|P1|P2`).

## Design tips

- Make criteria **explicit and weighted**, not implicit in a vague prompt; keep a numeric score you can audit.
- Keep deterministic constraints (deadlines, dependencies) in code; use the LLM for fuzzy judgments like urgency from free text.
- Re-run prioritisation on events (new task, failure, deadline) rather than only at start.
- Combine with planning (Ch. 6), resource-awareness (Ch. 16) and goal monitoring (Ch. 11).

## When to use

When an agent must autonomously manage multiple, possibly conflicting tasks or goals under resource constraints in a dynamic environment.

## Key takeaways

- Prioritisation = criteria + evaluation + selection + dynamic updates.
- It operates at goal, sub-task and action levels.
- It separates a genuinely agentic system from a fixed automation script.

**Prev:** [19 — Evaluation and Monitoring](19-evaluation-and-monitoring.md) · **Next:** [21 — Exploration and Discovery](21-exploration-and-discovery.md)
