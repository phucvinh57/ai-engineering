from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    source: str | None = None
    maturity: str | None = None
    # Client-generated (see web/src/session.ts); optional so curl/older
    # clients keep working -- they just produce ungrouped traces.
    session_id: str | None = None
    user_id: str | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    source: str | None = None
    session_id: str | None = None


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


class FeedbackRequest(BaseModel):
    # Langfuse v3 OTel trace ids are 32-char lowercase hex; the regex guard
    # matters because score ingestion doesn't validate trace existence, so
    # without it a malformed id lands in the project unnoticed.
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    value: int = Field(ge=0, le=1)  # 1 = thumbs up, 0 = thumbs down
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    ok: bool = True
    # Whether the score actually reached Langfuse. `ok` stays true even when
    # this is false -- telemetry failure must never surface as a UI error.
    recorded: bool = False
