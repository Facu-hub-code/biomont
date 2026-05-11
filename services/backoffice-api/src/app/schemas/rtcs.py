from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RtcUserCreate(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20, pattern=r"^\+?[0-9]+$")
    name: str = Field(min_length=1)
    enabled: bool = True
    country_isos: list[str] = Field(default_factory=list)


class RtcUserUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    country_isos: list[str] | None = None


class RtcUserOut(BaseModel):
    id: UUID
    phone_e164: str
    name: str
    enabled: bool
    country_isos: list[str]
    created_at: datetime
    updated_at: datetime
