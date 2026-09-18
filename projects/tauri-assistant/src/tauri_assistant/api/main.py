from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from tauri_assistant import telemetry
from tauri_assistant.api.routes import router
from tauri_assistant.ingest.chunking.tokens import get_token_counter
from tauri_assistant.ingest.embedding import get_embedding_model
from tauri_assistant.logs import configure_logger
from tauri_assistant.settings import settings

configure_logger()

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fails fast if chunking.max_tokens exceeds the embedding model's
    # max_seq_length, instead of letting ingest silently clamp it later.
    get_token_counter()
    # Load the embedding model now so the first request doesn't pay for it.
    # Pass the resolved name explicitly to match the lru_cache key Embedder uses.
    get_embedding_model(settings.embedding.model)
    # No-ops when LANGFUSE_PUBLIC_KEY/SECRET_KEY aren't set -- see telemetry.py.
    telemetry.init(settings)
    logger.info("API docs available at http://localhost:8000/docs (ReDoc: http://localhost:8000/redoc)")
    yield
    telemetry.shutdown()


app = FastAPI(title="Tauri assistant", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="ui")
