from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tauri_assistant import telemetry
from tauri_assistant.api.routes import router
from tauri_assistant.config import get_settings
from tauri_assistant.ingest.embedder import get_embeddings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    telemetry.init(settings)  # first, so a failure warming up the embedding model is traced
    await anyio.to_thread.run_sync(get_embeddings, settings.embedding_model)
    yield
    telemetry.shutdown()


app = FastAPI(title="Tauri Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
