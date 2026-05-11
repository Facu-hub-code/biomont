from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SystemPromptCreate(BaseModel):
    content: str = Field(min_length=10)


class SystemPromptOut(BaseModel):
    id: UUID
    version: int
    content: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime
