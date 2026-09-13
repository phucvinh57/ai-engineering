from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    chat_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

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
