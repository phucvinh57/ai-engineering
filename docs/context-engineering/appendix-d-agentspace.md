# Appendix D — Building an Agent with AgentSpace

> **Source:** *Agentic Design Patterns* — Appendix D: Building an Agent with AgentSpace (PDF pp. 391–396 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite. Product details reflect the book's snapshot in time; the appendix is mostly UI screenshots, so this summary is short.

## TL;DR

**AgentSpace** (Google Cloud) is an enterprise platform for an "agent-driven enterprise": unified search across a company's documents, email and databases, plus a **no-code Agent Designer** for building agents that reason, plan and run multi-step tasks.

## What it provides

- **Unified enterprise search** over documents, email and databases, powered by Gemini for understanding and synthesis.
- **Agents, not just chatbots:** e.g. research a topic, compile a cited report, even produce an audio summary.
- **Enterprise knowledge graph** mapping relations between people, documents and data → context-aware, personalised results (or connect Google's / your own private knowledge graph).
- **Agent Designer:** no-code interface for custom agents.
- **Multi-agent collaboration** through the open **A2A protocol** (Ch. 15).
- **Security:** role-based access control and data encryption.

## Building an agent in the UI (steps from the figures)

1. In the Google Cloud Console, open **AI Applications** to reach AgentSpace.
2. **Connect services** — e.g. Calendar, Gmail, Workday, Jira, Outlook, ServiceNow.
3. **Choose a prompt** from Google's gallery of pre-made prompts, or **write your own** custom prompt/instructions for the agent.
4. Optionally enable advanced features: **datastores** for your own data, knowledge-graph integration, a **web interface** to expose the agent, and **analytics** for usage monitoring.
5. Use the AgentSpace **chat interface** to talk to the finished agent.

## Why it matters (context-engineering view)

A no-code agent is essentially: **instructions (prompt) + connected data sources (context) + tools (connectors)**. The platform handles retrieval, permissions and knowledge-graph context so you configure rather than code — the same components as Ch. 5 (tools), 8 (memory) and 14 (RAG).

## Key takeaways

- AgentSpace abstracts agent construction behind a GUI: connect data, define prompts, deploy.
- Good fit for enterprises wanting agents inside existing workflows without deep programming.
- For hands-on practice the book points to the Google Cloud Skills Boost lab "Build a Gen AI Agent with Agentspace".

**Prev:** [Appendix C — Agentic Frameworks](appendix-c-agentic-frameworks.md) · **Next:** [Appendix E — AI Agents on the CLI](appendix-e-cli-agents.md)
