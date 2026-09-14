from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    chat_base_url: str = "http://localhost:11434/v1"
    chat_api_key: str = "ollama"
    chat_model: str = "llama3.2"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    data_dir: Path = PROJECT_ROOT / "data"
    repos_dir: Path = PROJECT_ROOT / "data" / "repos"
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma"
    manifest_path: Path = PROJECT_ROOT / "data" / "manifest.jsonl"

    chroma_collection: str = "wayland_docs"

    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 100

    retrieval_top_k: int = 8

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
