"""Schemas REST para conversaciones y playground BO."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationSummaryOut(BaseModel):
    id: UUID
    rtc_user_id: UUID
    rtc_name: str
    phone_e164: str
    started_at: datetime
    last_message_at: datetime
    last_preview: str | None = None


class ConversationMessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime


class PlaygroundProxyIn(BaseModel):
    rtc_user_id: UUID
    text: str = Field(..., min_length=1, max_length=8000)


class PlaygroundProxyOut(BaseModel):
    decision: str
    reply_text: str
    ticket_id: str | None = None
