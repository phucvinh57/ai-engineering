# 05 — Tool Use (Function Calling)

> **Source:** *Agentic Design Patterns* — Chapter 5: Tool Use (Function Calling) (PDF pp. 77–97 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Tools let an LLM step outside its frozen training data: fetch live data, calculate, query private systems, run code, or trigger actions. The model **decides** when to call a tool and emits a **structured request** (usually JSON); the framework **executes** it and feeds the result back.

## The six-step flow

1. **Define tools** – name, purpose, parameters (types + descriptions). The description is what the model reads, so write it well.
2. **LLM decides** – given the request and tool list, does it need a tool?
3. **Generate call** – structured output such as `{"tool": "get_weather", "args": {"city": "London"}}`.
4. **Execute** – the orchestration layer (not the model) runs the real function.
5. **Observe** – the result returns to the agent.
6. **Process** – the LLM writes the final answer or picks the next step (another tool, reflection, etc.).

```
user ─► LLM ─► tool call (JSON) ─► framework runs function ─► result ─► LLM ─► answer
                    ▲──────────── loop until no more tool calls ─────────┘
```

**"Tool calling" is broader than "function calling":** a tool may be a plain function, an API endpoint, a database query, or even *another specialised agent*.

## Use cases

| Use case | Tool |
|---|---|
| Live information (weather, news) | weather / search API |
| E-commerce (stock, order status, payments) | inventory / order / payment APIs |
| Calculation and analysis | calculator, stock API, spreadsheet |
| Communication | email / messaging API |
| Executing code | sandboxed code interpreter |
| Device control | smart-home / IoT API |

## Framework notes

- **LangChain:** wrap a Python function with `@tool` (docstring becomes the description), bind tools to the model, and build an agent with `create_tool_calling_agent` + `AgentExecutor`.
- **CrewAI:** `@tool("Name")` function, attach to an `Agent(role, goal, backstory, tools=[...])`, give it a `Task` with clear success/failure instructions, run a `Crew.kickoff()`. Good practice: tools return raw data or raise errors rather than returning ambiguous strings.
- **Google ADK:** built-in tools — **Google Search**, **code execution** (`BuiltInCodeExecutor`, a sandboxed Python interpreter for deterministic maths), **Vertex AI Search** (enterprise datastore, returns source attributions). Vertex **Extensions** are managed API wrappers that Vertex executes automatically, whereas plain function calls are executed by your client.

```python
@tool
def search_information(query: str) -> str:
    """Provides factual information on a topic. Use for 'capital of France' etc."""
    ...


agent = create_tool_calling_agent(llm, [search_information], prompt)
executor = AgentExecutor(agent=agent, tools=[search_information])
```

## Practical tips

- Precise descriptions and typed parameters → better tool selection.
- Return clear, compact results (context-engineering: don't dump huge payloads back into the prompt).
- Handle errors explicitly and tell the agent how to react (see Ch. 12).
- Sandbox code execution and gate dangerous actions (see Ch. 13, 18).

## When to use

Any time the agent must escape the model's internal knowledge: real-time data, private/proprietary data, exact calculation, code execution, or actions in other systems.

## Key takeaways

- Tool Use turns a text generator into an agent that can act.
- Model *chooses* tool + arguments; the framework *executes* and returns observations.
- Clear tool schemas and descriptions are essential.
- Frameworks provide decorators/adapters and pre-built tools (search, code, enterprise search).

**Prev:** [04 — Reflection](04-reflection.md) · **Next:** [06 — Planning](06-planning.md)
