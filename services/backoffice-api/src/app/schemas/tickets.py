from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TicketStatus = Literal["open", "in_progress", "resolved", "wont_fix"]
TicketType = Literal["no_info", "low_confidence", "user_request"]


class TicketOut(BaseModel):
    id: UUID
    conversation_id: UUID | None
    message_id: UUID | None
    type: TicketType
    status: TicketStatus
    summary: str
    notes: str | None
    assigned_to: UUID | None
    created_at: datetime
    updated_at: datetime


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    notes: str | None = None
    assigned_to: UUID | None = None
