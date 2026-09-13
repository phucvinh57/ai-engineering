Các topic:
- Prompt engineering technique: few shot, chain of thought
- Context engineering technique
- Harness engineering
- Loop/graph engineering
- Hermes agent
- Advance: Cách eval/benchmark performance hiệu quả, cách chống prompt, injection
- Prompt caching
Lib: genkit, claude sdk

---------------------------------------------------------------------------------------
Let me check what's actually trending right now so I'm not just giving you 2024 advice.That's mostly generic listicle noise, not much actionable. Let me check the more specific, technical trend — MCP and agent orchestration, which is where the real 2026 shift is happening.Market's screaming one thing right now: **MCP + agentic systems** are the actual frontier, not basic RAG anymore. Here's the current signal — LLM/RAG got demand from mainstream orgs, while the harder/higher-paying reqs want agent orchestration, security, and eval/observability chops. Here's a harder challenge list:

**1. Build an MCP server from scratch (no SDK shortcuts)**
- Raw JSON-RPC, implement tools/resources/prompts primitives yourself
- Then build a client that discovers tools dynamically and calls them
- This is *the* hot skill right now — 6,400+ registered servers, every major platform speaks it. You already use MCP tools in this very chat.

**2. Multi-agent orchestration (not single-agent chatbot)**
- 3+ specialized agents (researcher, coder, reviewer) talking through a shared state/message bus
- Build with LangGraph, then rebuild the same thing raw with just async Python — compare complexity
- Add a supervisor/router agent that decides who handles what

**3. Prompt injection red-teaming your own RAG**
- Deliberately poison your knowledge base with injected instructions
- Build detection/sanitization middleware (structured output anchors, input validation)
- This is now interview material at "elite AI lab" level roles — security is the fastest-growing sub-skill

**4. Token-efficiency challenge: Tool Search pattern**
- Instead of loading all tool schemas upfront (expensive), implement lazy/on-demand tool loading
- Anthropic's own approach cuts token usage ~85% in tool-heavy setups — replicate it yourself, measure the savings

**5. Production observability harness**
- Full tracing (Langfuse/Phoenix) across a multi-step agent
- Add automatic eval scoring on every trace (hallucination check, tool-call correctness)
- This is the "bottleneck skill" market reports keep flagging — companies can build agents, can't measure them

**6. Structured extraction under adversarial conditions**
- Feed it messy real-world text (your medical PDFs are great for this — tables, mixed VN/EN, weird formatting)
- Pydantic schema + automatic retry-with-error-feedback loop when validation fails
- Push it until it handles edge cases gracefully, not just happy path

**7. Cost/latency optimization exercise**
- Take an existing RAG/agent, profile it, then cut latency 50% and cost 70% (model routing — small model for easy queries, big model for hard ones; caching; batching)
- Document before/after numbers — this is exactly the resume-bullet material that gets interviews

Given your MCP exposure already (you're literally using MCP-based tools every day in Claude), #1 and #3 would be the sharpest differentiators — most bootcamp grads have never touched the protocol itself, just used pre-built servers. Want a starter spec for the raw MCP server build?