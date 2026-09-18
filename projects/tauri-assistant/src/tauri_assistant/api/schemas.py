from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class IngestRequest(BaseModel):
    force: bool = False


class ActionAccepted(BaseModel):
    status: str = "started"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    k: int = 6


class SearchRequest(BaseModel):
    query: str
    k: int = 6


class SearchResult(BaseModel):
    document_id: str
    heading_path: str
    url: str | None
    score: float
    text: str


class SearchResponse(BaseModel):
    results: list[SearchResult]


class RunSummary(BaseModel):
    id: int
    started_at: float
    finished_at: float | None
    status: str
    docs_total: int
    sources_total: int
    chunks_written: int
    embed_seconds: float


class VariantSummary(BaseModel):
    fingerprint: str
    collection_name: str
    embedding_model: str
    strategy: str
    created_at: float
    chunk_count: int
    is_current: bool
    latest_run: RunSummary | None


class VariantListResponse(BaseModel):
    variants: list[VariantSummary]
    current_fingerprint: str | None


class IngestRunListResponse(BaseModel):
    runs: list[RunSummary]
