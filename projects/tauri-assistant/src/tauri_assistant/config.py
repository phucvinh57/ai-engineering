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

    # A different (larger) model than chat_model, used to grade eval runs so the
    # model under test never grades its own answers.
    eval_judge_model: str = "qwen2.5:7b-instruct"

    data_dir: Path = PROJECT_ROOT / "data"
    repos_dir: Path = PROJECT_ROOT / "data" / "repos"
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma"
    manifest_path: Path = PROJECT_ROOT / "data" / "manifest.jsonl"

    chroma_collection: str = "tauri_docs"

    chunk_max_tokens: int = 800
    chunk_overlap_tokens: int = 100

    retrieval_top_k: int = 8

    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Telemetry (Langfuse) ---
    # Field names deliberately mirror the SDK's own env vars (LANGFUSE_PUBLIC_KEY, ...)
    # so one .env feeds both pydantic-settings and any direct SDK usage.
    langfuse_enabled: bool = True
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_environment: str = "development"
    langfuse_release: str | None = None
    langfuse_sample_rate: float = 1.0
    langfuse_timeout_seconds: int = 5
    langfuse_debug: bool = False

    # Ollama only returns usage on a streamed completion when asked; gate it
    # since older Ollama builds 400 on an unrecognized request field.
    chat_stream_usage: bool = True

    @property
    def telemetry_active(self) -> bool:
        """Absence of keys -- not the enabled flag -- is what actually turns
        telemetry off, so a fresh checkout with no .env gets zero tracing and
        zero network calls. The flag exists to force-disable even when keys
        are present (e.g. CI, benchmarking)."""
        return bool(self.langfuse_enabled and self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
