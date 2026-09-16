from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class _GroupSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        toml_file=PROJECT_ROOT / "config.toml",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


class ChatSettings(_GroupSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT_", toml_table_header=("chat",))
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "llama3.2"
    stream_usage: bool = True


class EmbeddingSettings(_GroupSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", toml_table_header=("embedding",))
    model: str = "BAAI/bge-m3"
    batch_size: int = 32
    normalize: bool = True


class PathSettings(_GroupSettings):
    model_config = SettingsConfigDict(env_prefix="PATHS_", toml_table_header=("paths",))
    data_dir: Path = PROJECT_ROOT / "data"

    @property
    def repos_dir(self) -> Path:
        return self.data_dir / "repos"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def catalog_db(self) -> Path:
        return self.data_dir / "catalog.db"


class ChunkingSettings(_GroupSettings):
    model_config = SettingsConfigDict(env_prefix="CHUNKING_", toml_table_header=("chunking",))
    strategy: str = "heading"
    # Upper bound we impose; the effective budget is min(this, the embedding
    # model's own max_seq_length) -- see ingest/chunking/tokens.py.
    max_tokens: int = 1024
    min_tokens: int = 64
    overlap_tokens: int = 64
    include_translations: bool = False
    exclude_globs: list[str] = Field(default_factory=lambda: ["_fragments/**", "blog/**", "releases/**"])


class LangfuseSettings(_GroupSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFUSE_", toml_table_header=("langfuse",))
    base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("base_url", "LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )
    public_key: str | None = None
    secret_key: str | None = None
    environment: str = "development"
    enabled: bool = True
    release: str | None = None
    sample_rate: float = 1.0
    debug: bool = False

    @property
    def active(self) -> bool:
        return bool(self.enabled and self.public_key and self.secret_key)


@dataclass(frozen=True)
class Settings:
    chat: ChatSettings = field(default_factory=ChatSettings)
    embedding: EmbeddingSettings = field(default_factory=EmbeddingSettings)
    chunking: ChunkingSettings = field(default_factory=ChunkingSettings)
    paths: PathSettings = field(default_factory=PathSettings)
    langfuse: LangfuseSettings = field(default_factory=LangfuseSettings)


settings = Settings()
