from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from tauri_assistant.api.routes import routers
from tauri_assistant.ingest.chunking.tokens import get_token_counter
from tauri_assistant.logs import configure_logger

configure_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fails fast if chunking.max_tokens exceeds the embedding model's
    # max_seq_length, instead of letting ingest silently clamp it later.
    get_token_counter()
    logger.info("API docs available at http://localhost:8000/docs (ReDoc: http://localhost:8000/redoc)")
    yield


app = FastAPI(title="Tauri assistant", lifespan=lifespan)
app.include_router(routers)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
