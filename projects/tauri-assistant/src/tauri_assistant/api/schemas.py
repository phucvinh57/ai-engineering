from __future__ import annotations

from typing import Literal
from pydantic import BaseModel
from tauri_assistant.sources import SOURCES

SourceName = Literal[*SOURCES]


class IngestRequest(BaseModel):
    source: list[SourceName]
    force: bool = False


class ActionAccepted(BaseModel):
    status: str = "started"
