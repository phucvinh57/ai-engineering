from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    source: str | None = None
    maturity: str | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    source: str | None = None


class SearchResult(BaseModel):
    text: str
    heading_path: str
    url: str
    source: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


class StatsResponse(BaseModel):
    total_chunks: int
    chunks_by_source: dict[str, int]
    last_fetch_at: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
