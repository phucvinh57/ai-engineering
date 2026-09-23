# 10 — Model Context Protocol (MCP)

> **Source:** *Agentic Design Patterns* — Chapter 10: Model Context Protocol (PDF pp. 165–180 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

MCP is an **open standard** — a "universal adapter" — that lets any compliant LLM app (client) discover and use tools, data and prompts exposed by any compliant **server**, instead of writing a custom integration for every pair.

## Architecture

| Component | Role |
|---|---|
| **LLM** | Decides when it needs external information/action. |
| **MCP client** | Wrapper/host around the LLM; discovers servers, translates the LLM's intent into MCP requests. |
| **MCP server** | Gateway exposing **tools** (executable actions), **resources** (static data such as files or DB records) and **prompts** (templates guiding interaction). Usually one domain per server. |
| **3rd-party service** | The real database/SaaS/API behind the server. |

**Flow:** 1) *Discovery* – client asks the server for its manifest → 2) LLM formulates a call (tool + params) → 3) client sends a standard request → 4) server authenticates, validates, executes → 5) server returns a standard response → client feeds it back into the LLM's context.

**Transports:** JSON-RPC over **STDIO** for local servers; **Streamable HTTP / SSE** for remote ones. Servers can be local (fast, private data) or remote (shared, scalable); usable on demand or in batch.

## MCP vs. plain function calling

| | Function calling | MCP |
|---|---|---|
| Standardisation | Vendor-specific formats | Open protocol |
| Scope | LLM → one predefined function | Framework for discovery + communication |
| Architecture | 1-to-1 with the app's tool handler | Client–server; many clients ↔ many servers |
| Discovery | Tools listed up-front in the conversation | Dynamic ("just-in-time") query of a server |
| Reusability | Coupled to the app/LLM | Reusable standalone servers |

Analogy: function calling = a custom toolkit for a fixed workshop; MCP = a universal power outlet any tool can plug into. For small fixed tool sets, plain function calling is enough.

## Caveats (important)

- **MCP is only a contract; the underlying API must be agent-friendly.** Wrapping a legacy API unchanged can be slow and inaccurate (e.g. a ticket API that only returns one full ticket at a time makes "summarise high-priority tickets" hopeless). Add deterministic features — **filtering, sorting, pagination** — so the non-deterministic agent works efficiently.
- **Data format matters.** A document server returning PDFs is useless if the agent can't parse them; return **Markdown/text**.
- **Security:** authentication and authorisation for clients, servers and each action.
- **Errors:** communicate failures clearly so the LLM can recover or try another approach.
- **Implementation:** SDKs (Anthropic SDKs, FastMCP) hide much boilerplate.

## Use cases

Database access (e.g. BigQuery via MCP Toolbox), generative-media orchestration (Imagen, Veo, Chirp, Lyria), any external API (weather, stocks, CRM, email), reasoning-based information extraction (pull the exact clause instead of a whole document), custom internal tools, standardised LLM↔app communication, multi-step workflow orchestration, IoT control, financial services.

## Hands-on (Google ADK)

**Consume an existing server (filesystem):**

```python
LlmAgent(
    model="gemini-2.0-flash",
    name="filesystem_assistant_agent",
    instruction="Help the user manage files in: " + TARGET_FOLDER_PATH,
    tools=[
        MCPToolset(
            connection_params=StdioServerParameters(
                command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", TARGET_FOLDER_PATH]
            )
        )
    ],
)
```
(`npx` runs Node-based servers; `uvx` runs Python ones in an isolated env; use `tool_filter=[...]` to expose only some tools. Add `__init__.py` with `from . import agent` and launch with `adk web`.)

**Build a server with FastMCP:**

```python
mcp_server = FastMCP()


@mcp_server.tool
def greet(name: str) -> str:
    """Generates a personalised greeting."""  # docstring → tool description
    return f"Hello, {name}! Nice to meet you."


mcp_server.run(transport="http", host="127.0.0.1", port=8000)
```
FastMCP auto-generates the schema from type hints and docstrings and supports server composition and proxying.

**Consume it from an agent:** `MCPToolset(connection_params=HttpServerParameters(url="http://localhost:8000"), tool_filter=["greet"])`.

## When to use

Complex, scalable or enterprise systems with many evolving tools/data sources, when interoperability across LLMs/tools matters and agents must discover capabilities without redeployment.

## Key takeaways

- MCP = open client–server standard for tools, resources and prompts.
- Enables dynamic discovery and reuse; function calling is simpler but proprietary and static.
- Design agent-friendly APIs behind the protocol (filters, text formats, good errors) and secure them.
- FastMCP builds servers; ADK's `MCPToolset` consumes them.

**Prev:** [09 — Learning and Adaptation](09-learning-and-adaptation.md) · **Next:** [11 — Goal Setting and Monitoring](11-goal-setting-and-monitoring.md)
