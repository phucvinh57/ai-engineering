import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

model = ChatOllama(
    model="llama3.2",
    temperature=0,
)

# --- Use case: research and report writing (Ch. 6) ---
# "Compare vector databases for a RAG pipeline": plan the comparison axes,
# gather facts for each, re-plan when a fact is missing, then structure and
# write up the report. The knowledge base below stands in for real web search
# so the example runs offline and deterministically.

TOPIC = "Compare Pinecone, Weaviate and Qdrant for a RAG pipeline"
DATABASES = ["pinecone", "weaviate", "qdrant"]
ASPECTS = ["pricing", "latency", "self-hosting", "integrations"]

PLANNER_PROMPT = """
You are a research planner comparing vector databases for a RAG pipeline.

Break the request into a numbered plan, one step per comparison aspect, using
ONLY these aspects, each at most once, in this order:
pricing, latency, self-hosting, integrations

Output ONLY a numbered list like:
1. pricing
2. latency

Request:
{topic}
"""

REFINE_PROMPT = """
You are writing the final section of a research report comparing {databases}
for a RAG pipeline, covering: {aspects}.

Use ONLY the findings table below. Do not invent numbers or claims that are
not in the table. If a cell says "no data found", say so explicitly instead
of guessing.

Findings:
{table}

Write:
1. One short paragraph per aspect summarising the comparison.
2. A final recommendation: which database fits which use case.
Keep the whole report under 250 words.
"""

# Primary knowledge base: what a first pass of "search" turns up.
KNOWLEDGE_BASE = {
    "pinecone": {
        "pricing": {
            "fact": "Serverless, usage-based pricing (~$0.096/GB-month storage plus per-request read/write units); free tier for prototyping.",  # noqa: E501
            "source": "Pinecone pricing page, 2026",
        },
        "self-hosting": {
            "fact": "Fully managed SaaS only, no self-hosted or on-prem option.",
            "source": "Pinecone docs, 2026",
        },
        "integrations": {
            "fact": "First-class LangChain/LlamaIndex SDKs, native OpenAI/Cohere embedding integrations.",
            "source": "Pinecone docs, 2026",
        },
        # latency intentionally missing: found later via a secondary source
    },
    "weaviate": {
        "pricing": {
            "fact": "Open-source self-hosted is free; Weaviate Cloud is priced per-node, from ~$25/month.",
            "source": "Weaviate pricing page, 2026",
        },
        "latency": {
            "fact": "Sub-50ms p95 query latency at ~1M vectors with the default HNSW index.",
            "source": "Weaviate benchmark report, 2026",
        },
        "self-hosting": {
            "fact": "Fully supports self-hosting via Docker/Kubernetes, open-source core.",
            "source": "Weaviate docs, 2026",
        },
        "integrations": {
            "fact": "GraphQL + REST APIs, LangChain/LlamaIndex support, built-in hybrid search (BM25 + vector).",  # noqa: E501
            "source": "Weaviate docs, 2026",
        },
    },
    "qdrant": {
        "pricing": {
            "fact": "Open-source self-hosted is free; Qdrant Cloud starts around $25/month for a managed cluster.",  # noqa: E501
            "source": "Qdrant pricing page, 2026",
        },
        "self-hosting": {
            "fact": "Fully supports self-hosting, single binary or Docker, written in Rust.",
            "source": "Qdrant docs, 2026",
        },
        "integrations": {
            "fact": "LangChain/LlamaIndex support, gRPC and REST APIs, payload filtering alongside vector search.",  # noqa: E501
            "source": "Qdrant docs, 2026",
        },
        # latency intentionally missing: found later via a secondary source
    },
}

# Only consulted after a gap triggers re-planning, mirroring the "find gaps ->
# search again" loop of the Deep Research agents.
SECONDARY_SOURCES = {
    "pinecone": {
        "latency": {
            "fact": "~35ms p95 query latency reported at 10M vectors in Pinecone's own serverless benchmark.",
            "source": "Pinecone engineering blog, 2026 (secondary)",
        },
    },
    "qdrant": {
        "latency": {
            "fact": "~20ms p95 query latency at 1M vectors in an independent ANN-benchmarks run.",
            "source": "ann-benchmarks.com, 2026 (secondary)",
        },
    },
}


@dataclass
class Finding:
    aspect: str
    database: str
    fact: str | None
    source: str | None


def parse_plan(text: str) -> list[str]:
    """Numbered lines -> known aspects only, in the order the model gave them."""
    steps = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+[.)]\s*(.+)", line)
        if not match:
            continue
        aspect = match.group(1).strip().lower().strip(".")
        if aspect in ASPECTS and aspect not in steps:
            steps.append(aspect)
    return steps or list(ASPECTS)  # fallback: a known-good default plan


def make_plan(topic: str) -> list[str]:
    # 1. Plan: the model decomposes the request into a numbered plan before
    #    any gathering happens, instead of writing the report in one shot.
    response = model.invoke([HumanMessage(PLANNER_PROMPT.format(topic=topic))])
    return parse_plan(response.text)


def gather(plan: list[str], knowledge_base: dict) -> list[Finding]:
    # 2. Gather: execute the plan step by step against the "search" tool
    #    (here, a lookup) instead of asking the model to recall facts itself.
    findings = []
    for aspect in plan:
        for db in DATABASES:
            entry = knowledge_base.get(db, {}).get(aspect)
            findings.append(
                Finding(aspect, db, entry["fact"] if entry else None, entry["source"] if entry else None)
            )
    return findings


def replan_and_regather(findings: list[Finding]) -> list[Finding]:
    # 3. Gap check / re-plan: a missing fact is a changed constraint, not a
    #    crash. The agent registers it and adds a follow-up search instead of
    #    silently dropping the comparison or inventing a number.
    gaps = [f for f in findings if f.fact is None]
    if not gaps:
        return findings

    print("\n=== Re-plan: gaps found, checking secondary sources ===")
    resolved = []
    for f in findings:
        if f.fact is not None:
            resolved.append(f)
            continue
        print(f"  - missing {f.aspect} for {f.database}, searching again...")
        entry = SECONDARY_SOURCES.get(f.database, {}).get(f.aspect)
        if entry:
            print(f"    found via {entry['source']}")
            resolved.append(Finding(f.aspect, f.database, entry["fact"], entry["source"]))
        else:
            print("    still not found, will be reported as a data gap")
            resolved.append(f)
    return resolved


def to_markdown_table(plan: list[str], findings: list[Finding]) -> str:
    # 4. Structure: organise findings into a table before drafting any prose,
    #    so the writer works from a clean, complete-or-flagged data model.
    by_aspect: dict[str, dict[str, Finding]] = {}
    for f in findings:
        by_aspect.setdefault(f.aspect, {})[f.database] = f

    header = "| Aspect | " + " | ".join(db.title() for db in DATABASES) + " |"
    divider = "| --- | " + " | ".join(["---"] * len(DATABASES)) + " |"
    rows = [header, divider]
    for aspect in plan:
        cells = [aspect]
        for db in DATABASES:
            finding = by_aspect.get(aspect, {}).get(db)
            cells.append(finding.fact if finding and finding.fact else "no data found")
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def refine_report(table: str) -> str:
    # 5. Refine: only now does the model write prose, grounded in the
    #    structured table rather than free recall. Pair with reflection
    #    (Ch. 4) here to critique the draft before it ships.
    prompt = REFINE_PROMPT.format(
        databases=", ".join(db.title() for db in DATABASES),
        aspects=", ".join(ASPECTS),
        table=table,
    )
    chunks = []
    for chunk in model.stream(
        [SystemMessage("You are a precise technical report writer."), HumanMessage(prompt)]
    ):
        print(chunk.text, end="", flush=True)
        chunks.append(chunk.text)
    print()
    return "".join(chunks)


def list_sources(findings: list[Finding]) -> str:
    sources = sorted({f.source for f in findings if f.source})
    return "\n".join(f"- {s}" for s in sources)


def main():
    print(f"=== Topic ===\n{TOPIC}\n")

    plan = make_plan(TOPIC)
    print("=== Plan ===")
    for i, aspect in enumerate(plan, 1):
        print(f"{i}. {aspect}")

    findings = gather(plan, KNOWLEDGE_BASE)
    findings = replan_and_regather(findings)

    table = to_markdown_table(plan, findings)
    print(f"\n=== Structured findings ===\n{table}")

    print("\n=== Final report ===")
    refine_report(table)

    print("\n=== Sources ===")
    print(list_sources(findings))
