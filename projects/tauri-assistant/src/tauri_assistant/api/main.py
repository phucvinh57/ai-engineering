from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tauri_assistant.api.routes import router
from tauri_assistant.config import get_settings

app = FastAPI(title="Tauri Assistant API")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
