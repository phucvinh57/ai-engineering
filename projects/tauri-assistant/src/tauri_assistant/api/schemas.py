from __future__ import annotations

from pydantic import BaseModel


class IngestRequest(BaseModel):
    force: bool = False


class ActionAccepted(BaseModel):
    status: str = "started"
