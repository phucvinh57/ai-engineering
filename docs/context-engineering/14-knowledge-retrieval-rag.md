# 14 — Knowledge Retrieval (RAG)

> **Source:** *Agentic Design Patterns* — Chapter 14: Knowledge Retrieval (RAG) (PDF pp. 211–228 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

**Retrieval-Augmented Generation**: before the LLM answers, search an external knowledge base for relevant snippets and **add them to the prompt**. The LLM goes from a *closed-book* to an *open-book* reasoner: fresher, grounded, less prone to hallucination, able to use private data and cite sources.

```
query ─► semantic search over knowledge base ─► top-k chunks ─► prompt = question + chunks ─► LLM ─► grounded answer (+ citations)
```

## Core concepts

| Concept | Meaning |
|---|---|
| **Embedding** | A vector (hundreds–thousands of numbers) capturing a text's meaning; similar meanings → nearby vectors ("cat" ≈ "kitten", far from "car"). |
| **Semantic similarity / distance** | Compare meaning, not words: "a furry feline companion" ≈ "a domestic cat". RAG retrieves the chunks with the *smallest distance* to the query embedding. |
| **Chunking** | Split documents into meaningful pieces (sections, paragraphs, sentences) so retrieval returns focused context rather than a 50-page manual. Chunk quality drives answer quality. |
| **Retrieval methods** | **Vector search** (semantic), **BM25** (keyword/term frequency), **hybrid** (both: literal precision + conceptual recall). |
| **Vector database** | Stores embeddings and does fast approximate nearest-neighbour search (e.g. HNSW). Options: Pinecone, Weaviate, Chroma, Milvus, Qdrant; or Redis, Elasticsearch, Postgres+pgvector; libraries FAISS, ScaNN. |

## Challenges

- Answers spread across several chunks/documents may not be fully retrieved.
- Poor chunking/retrieval injects **noise** that confuses the LLM.
- Contradictory sources are hard to reconcile.
- The knowledge base must be pre-processed, stored and **kept in sync** (wikis change).
- Adds latency, cost and prompt tokens.

## Two advanced variants

### GraphRAG
Retrieves from a **knowledge graph** (entities = nodes, relationships = edges) instead of a flat vector store. Excellent for questions requiring facts fragmented across documents (financial analysis, gene–disease links). Downsides: heavy effort/cost to build and maintain the graph, higher latency, quality depends on the graph.

### Agentic RAG
Adds a **reasoning agent** between retrieval and generation that:

1. **Validates sources & freshness** – prefers the 2025 policy over a 2020 blog post using metadata.
2. **Reconciles conflicts** – picks the finalised financial report (€65k) over the initial proposal (€50k).
3. **Does multi-step reasoning** – decomposes "compare our product to Competitor X" into four sub-queries and synthesises.
4. **Detects knowledge gaps** – if the weekly-updated KB has nothing on yesterday's launch, calls a live web-search tool.

Cost: more complexity, latency and money; the agent itself can loop, misread the task or wrongly discard good context.

## Use cases

Enterprise search/Q&A (HR policies, manuals), customer support over FAQs/tickets, personalised content recommendation, news summarisation, legal research.

## Implementations shown

- **ADK + Google Search:** `Agent(tools=[google_search])` — the simplest retrieval tool.
- **ADK + Vertex AI RAG:** `VertexAiRagMemoryService(rag_corpus=..., similarity_top_k=5, vector_distance_threshold=0.7)` – top-k caps how many chunks come back; the threshold drops results that are too far in meaning.
- **LangChain + LangGraph:** load text → split into chunks → embed → store in a vector DB (Weaviate) → a `StateGraph` with `retrieve_documents_node` and `generate_response_node`; prompt says *"use the retrieved context; if you don't know, say so; three sentences max."*

## Context-engineering tips

- Tune `top_k`, distance thresholds and chunk size — more context is not always better.
- Use hybrid search and metadata (date, source, authority) to filter before generation.
- Instruct the model to answer only from context and to say "I don't know"; return citations.
- Consider a re-ranking or validation step (Agentic RAG) for high-stakes answers.

## When to use

When an LLM must answer from specific, up-to-date or proprietary information not in its training data, especially with a need for verifiable, cited answers.

## Key takeaways

- RAG = **retrieve** relevant snippets + **augment** the prompt.
- Embeddings + semantic search + vector DBs find meaning, not just keywords; hybrid search is more robust.
- GraphRAG handles connected facts; Agentic RAG validates, reconciles and fills gaps — at a cost.
- Retrieval quality (chunking, ranking, freshness) determines answer quality.

**Prev:** [13 — Human-in-the-Loop](13-human-in-the-loop.md) · **Next:** [15 — Inter-Agent Communication (A2A)](15-inter-agent-communication-a2a.md)
