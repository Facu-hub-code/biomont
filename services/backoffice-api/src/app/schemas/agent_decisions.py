from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse

AgentDecisionKind = Literal[
    "answered", "low_confidence", "no_match", "blocked", "error"
]


class AgentDecisionListItem(BaseModel):
    id: UUID
    message_id: UUID | None = None
    decision: AgentDecisionKind
    reasoning: str | None = None
    top_similarity: float | None = None
    system_prompt_version: int | None = None
    created_at: datetime
    conversation_id: UUID | None = None
    rtc_user_id: UUID | None = None
    rtc_name: str | None = None
    phone_e164: str | None = None
    message_preview: str | None = None


class AgentDecisionDetail(BaseModel):
    id: UUID
    message_id: UUID | None = None
    decision: AgentDecisionKind
    reasoning: str | None = None
    retrieved: list[dict[str, Any]] = Field(default_factory=list)
    top_similarity: float | None = None
    system_prompt_version: int | None = None
    graph_trace: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    message_content: str | None = None
    message_role: str | None = None
    conversation_id: UUID | None = None
    conversation_started_at: datetime | None = None
    rtc_user_id: UUID | None = None
    rtc_name: str | None = None
    phone_e164: str | None = None
    previous_user_message: str | None = None


AgentDecisionListResponse = PaginatedResponse[AgentDecisionListItem]
