from __future__ import annotations

from typing import Literal
from pydantic import BaseModel
from tauri_assistant.sources import SOURCES

SourceName = Literal[*SOURCES]


class IngestRequest(BaseModel):
    source: list[SourceName]
    full: bool = False
    use_cache: bool = True


class ActionAccepted(BaseModel):
    status: str = "started"
