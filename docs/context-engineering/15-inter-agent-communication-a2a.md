# 15 — Inter-Agent Communication (A2A)

> **Source:** *Agentic Design Patterns* — Chapter 15: Inter-Agent Communication (A2A) (PDF pp. 229–243 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

**A2A (Agent2Agent)** is an open, HTTP-based protocol (from Google, backed by many vendors) that lets agents built with **different frameworks** (ADK, LangGraph, CrewAI…) discover each other, delegate tasks and exchange results. Think: **MCP connects an agent to tools and data; A2A connects agents to other agents.**

## Core concepts

| Concept | What it is |
|---|---|
| **Actors** | *User* → *A2A client* (agent acting for the user) → *A2A server / remote agent* (HTTP endpoint; **opaque** — the client needn't know its internals). |
| **Agent Card** | JSON "digital identity": name, description, endpoint `url`, `version`, `capabilities` (streaming, push notifications), `authentication` schemes, default input/output modes, and `skills` (id, name, description, examples, tags). |
| **Discovery** | *Well-known URI* (`/.well-known/agent.json`), *curated registries* (enterprise catalogue with access control), or *direct configuration* (private/tightly-coupled). Protect card endpoints (access control, mTLS, network limits). |
| **Task** | The unit of (often long-running, asynchronous) work with a unique id and lifecycle states such as *submitted → working → completed / failed*, plus `input-required` for multi-turn clarification. |
| **Message / Part** | A message has metadata attributes and one or more **parts** (text, files, structured JSON). |
| **Artifact** | Tangible output of a task, also made of parts, can be streamed. |
| **contextId / sessionId** | Groups related tasks to keep context across interactions. |
| **Transport** | HTTP(S) with **JSON-RPC 2.0** payloads; modality-agnostic (text, audio, video). |

## Interaction modes

| Mode | Use when |
|---|---|
| **Synchronous request/response** (`sendTask`) | Quick operations; client waits for the full answer. |
| **Asynchronous polling** | Longer tasks; server returns "working" + task id; client polls until done. |
| **Streaming via SSE** (`sendTaskSubscribe`) | Incremental results / status updates over a persistent one-way connection. |
| **Push notifications (webhooks)** | Very long-running work; server calls the client's registered URL on significant change. |

The Agent Card declares which of streaming/push an agent supports.

Sample synchronous request (abridged):

```json
{ "jsonrpc": "2.0", "id": "1", "method": "sendTask",
  "params": { "id": "task-001", "sessionId": "session-001",
    "message": { "role": "user",
      "parts": [ { "type": "text", "text": "What is the exchange rate from USD to EUR?" } ] },
    "acceptedOutputModes": ["text/plain"], "historyLength": 5 } }
```

## Security

- **Mutual TLS** for authenticated, encrypted connections.
- **Audit logs** of all inter-agent traffic.
- Authentication requirements **declared in the Agent Card**.
- Credentials (OAuth 2.0 tokens, API keys) sent in **HTTP headers**, never in URLs or bodies.

## A2A vs. MCP

| | MCP | A2A |
|---|---|---|
| Connects | LLM/agent ↔ tools, resources, prompts | agent ↔ agent |
| Focus | Structuring context and external capabilities | Coordination, delegation, collaboration |
| Relationship | Complementary — an A2A remote agent may itself use MCP tools. |

## Use cases

Multi-framework collaboration; automated enterprise workflow orchestration (collect → analyse → report handled by three agents); dynamic information retrieval from specialised data-fetching agents.

## Example (ADK calendar agent as an A2A server)

1. Build an `LlmAgent` with `CalendarToolset` (Google Calendar API) and an instruction to use RFC3339 timestamps and the current date.
2. Describe it with an `AgentSkill` (`check_availability`) and an `AgentCard` (name, url, version, capabilities `streaming=True`, skills).
3. Wrap the ADK `Runner` in an `ADKAgentExecutor`, plug it into the A2A request handler, serve via a Starlette app on Uvicorn.

Sample multi-framework clients/servers (Python, Java, Go) are in the `a2a-samples` repository.

## When to use

When two or more agents — especially from different frameworks — must collaborate, or an agent must dynamically discover and consume other agents' capabilities.

## Key takeaways

- A2A = open standard for agent-to-agent interoperability over HTTP/JSON-RPC.
- The **Agent Card** enables automatic discovery of skills and requirements.
- Choose sync, polling, SSE or webhooks according to task duration; tasks can request more input.
- Built-in security (mTLS, declared auth, audit logs); complements MCP.

**Prev:** [14 — Knowledge Retrieval (RAG)](14-knowledge-retrieval-rag.md) · **Next:** [16 — Resource-Aware Optimization](16-resource-aware-optimization.md)
