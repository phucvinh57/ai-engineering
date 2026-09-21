# 08 — Memory Management

> **Source:** *Agentic Design Patterns* — Chapter 8: Memory Management (PDF pp. 130–151 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Without memory an agent is stateless. Two layers are needed:

- **Short-term (contextual) memory** – what is inside the LLM's context window right now (recent messages, tool results, reflections). Limited, ephemeral, costly to keep large.
- **Long-term (persistent) memory** – external storage (databases, knowledge graphs, **vector DBs**) that survives across sessions; retrieved by semantic similarity and **injected back into the context** when relevant.

Long-context models enlarge short-term memory but don't make it persistent, and processing everything every turn is slow and expensive. Managing what enters the window (summarise old turns, keep key facts) *is* context engineering.

## Use cases

- **Chatbots:** short-term for coherence; long-term for user preferences and past issues.
- **Task agents:** track steps, progress, goals; look up user data outside the context.
- **Personalisation:** store preferences and behaviours.
- **Learning:** keep successful strategies and mistakes for later.
- **RAG:** the knowledge base *is* long-term memory (Ch. 14).
- **Autonomous systems:** maps, routes, learned behaviours.

## Google ADK: Session, State, Memory

| Concept | What it is |
|---|---|
| **Session** | One chat thread: id, `app_name`, `user_id`, list of `Event`s, `state`, `last_update_time`. |
| **State** (`session.state`) | Key-value scratchpad for the current thread (preferences, progress, flags). Serialisable values only. |
| **Memory** | Searchable store of information from many past sessions / external sources. |

**Services** (in-memory for tests; database or cloud for production):

- `SessionService`: `InMemorySessionService`, `DatabaseSessionService`, `VertexAiSessionService`. Lifecycle: create/resume → agent reads context → response wrapped in an `Event` → `append_event()` persists it and state changes → optionally `delete_session()`.
- `MemoryService`: `add_session_to_memory(session)` to store and `search_memory(query)` to retrieve. `InMemoryMemoryService` (tests) or `VertexAiRagMemoryService` (semantic search over a RAG corpus with `similarity_top_k`, distance threshold).

**State scoping via key prefixes**

| Prefix | Scope |
|---|---|
| *(none)* | this session only |
| `user:` | this user across all sessions |
| `app:` | all users of the app |
| `temp:` | this processing turn only, never persisted |

**Updating state — do it via events, never by mutating the dict directly:**

1. `output_key="last_greeting"` on an `LlmAgent` saves its final text reply into state.
2. `EventActions(state_delta={...})` (or a tool using `tool_context.state[...]`) for multi-key, non-text or scoped updates.

Direct mutation bypasses the event history, may not persist, and causes concurrency issues. Keep state simple: basic types, clear key names, little nesting.

## LangChain / LangGraph memory

- **Short-term** = thread-scoped state persisted with a **checkpointer** (resume any thread). Watch context-window size.
- `ChatMessageHistory` – manual history; `ConversationBufferMemory` – auto-injects history into a prompt (`memory_key`, `return_messages=True` for chat models, with `MessagesPlaceholder("chat_history")`).
- **Long-term** = a **store** of JSON documents under a **namespace** (folder-like) and **key** (filename-like); supports `put`, `get`, and semantic `search` (with an embedding index) shared across threads.

### Three kinds of long-term memory

| Type | Holds | Typical implementation |
|---|---|---|
| **Semantic** | Facts, preferences, domain knowledge | A user "profile" JSON or a collection of fact documents |
| **Episodic** | Past experiences / how a task was done | Few-shot examples from successful past runs |
| **Procedural** | Rules for how to act | System-prompt instructions; the agent can **reflect** on recent interactions and rewrite its own instructions (stored in the store) |

## Vertex AI Memory Bank

A managed service that uses Gemini to *asynchronously* extract key facts/preferences from conversations, store them scoped by user, **merge and resolve contradictions**, and retrieve them at session start (full recall or embedding similarity). Works with ADK natively and with LangGraph/CrewAI via API.

## When to use

Whenever an agent must do more than answer a single question: keep context across a conversation, track multi-step progress, personalise, or learn from past successes and failures.

## Key takeaways

- Memory = short-term (context window) + long-term (external, searchable).
- Retrieval brings only *relevant* memories into the window; summarise or trim the rest.
- ADK: Session (thread) / State (thread scratchpad, prefixed scopes) / MemoryService (long-term). Update state through events.
- LangGraph: checkpointer for threads, stores with namespaces for semantic/episodic/procedural memory.
- Managed options (Memory Bank) automate extraction and consolidation.

**Prev:** [07 — Multi-Agent Collaboration](07-multi-agent-collaboration.md) · **Next:** [09 — Learning and Adaptation](09-learning-and-adaptation.md)
