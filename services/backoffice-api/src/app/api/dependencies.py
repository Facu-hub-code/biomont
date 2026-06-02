"""Dependencies de FastAPI: autenticacion, RBAC, factories.

Estas son las unicas formas autorizadas de obtener pool/repos/servicios
dentro de los routers; cumple
`.cursor/rules/architecture-clean-fastapi.mdc`.
"""

from __future__ import annotations

from typing import Annotated, Iterable
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from biomont_common.db.document_product_repository import DocumentProductRepository
from biomont_common.db.pool import DatabasePool
from biomont_common.db.rag_repository import RagRepository

from app.db.analytics_repository import AnalyticsRepository
from app.db.audit_repository import AuditRepository
from app.db.bo_user_repository import BoUserRepository, BoUserRow
from app.db.conversation_admin_repository import ConversationAdminRepository
from app.db.document_repository import DocumentRepository
from app.db.product_admin_repository import ProductAdminRepository
from app.db.rtc_admin_repository import RtcAdminRepository
from app.db.agent_config_admin_repository import AgentConfigAdminRepository
from app.db.agent_decision_enrichment_repository import AgentDecisionEnrichmentRepository
from app.db.comparison_admin_repository import ComparisonAdminRepository
from app.db.dosing_admin_repository import DosingAdminRepository
from app.db.system_prompt_admin_repository import SystemPromptAdminRepository
from app.db.ticket_repository import TicketAdminRepository
from app.schemas.auth import CurrentUser
from app.services.agent_decision_enrichment import AgentDecisionEnrichmentService
from app.services.security import decode_access_token
from biomont_common.db.agent_decision_repository import AgentDecisionRepository


def get_pool(request: Request) -> DatabasePool:
    pool: DatabasePool = request.app.state.pool
    return pool


def get_bo_users(pool: Annotated[DatabasePool, Depends(get_pool)]) -> BoUserRepository:
    return BoUserRepository(pool)


def get_documents(pool: Annotated[DatabasePool, Depends(get_pool)]) -> DocumentRepository:
    return DocumentRepository(pool)


def get_rag(pool: Annotated[DatabasePool, Depends(get_pool)]) -> RagRepository:
    return RagRepository(pool)


def get_rtcs(pool: Annotated[DatabasePool, Depends(get_pool)]) -> RtcAdminRepository:
    return RtcAdminRepository(pool)


def get_prompts(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> SystemPromptAdminRepository:
    return SystemPromptAdminRepository(pool)


def get_agent_config(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> AgentConfigAdminRepository:
    return AgentConfigAdminRepository(pool)


def get_tickets(pool: Annotated[DatabasePool, Depends(get_pool)]) -> TicketAdminRepository:
    return TicketAdminRepository(pool)


def get_products(pool: Annotated[DatabasePool, Depends(get_pool)]) -> ProductAdminRepository:
    return ProductAdminRepository(pool)


def get_document_products(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> DocumentProductRepository:
    return DocumentProductRepository(pool)


def get_agent_decisions(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> AgentDecisionRepository:
    return AgentDecisionRepository(pool)


def get_agent_decision_enrichment(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> AgentDecisionEnrichmentService:
    return AgentDecisionEnrichmentService(AgentDecisionEnrichmentRepository(pool))


def get_audit(pool: Annotated[DatabasePool, Depends(get_pool)]) -> AuditRepository:
    return AuditRepository(pool)


def get_analytics(pool: Annotated[DatabasePool, Depends(get_pool)]) -> AnalyticsRepository:
    return AnalyticsRepository(pool)


def get_conversations(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> ConversationAdminRepository:
    return ConversationAdminRepository(pool)


def get_dosing(pool: Annotated[DatabasePool, Depends(get_pool)]) -> DosingAdminRepository:
    return DosingAdminRepository(pool)


def get_comparison(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> ComparisonAdminRepository:
    return ComparisonAdminRepository(pool)


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    bo_users: BoUserRepository = Depends(get_bo_users),
) -> CurrentUser:
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from exc

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    user_id = UUID(user_id_raw)
    user_row: BoUserRow | None = await bo_users.find_by_id(user_id)
    if user_row is None or not user_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive user"
        )
    return CurrentUser(
        id=user_row.id,
        email=user_row.email,
        name=user_row.name,
        role=user_row.role,  # type: ignore[arg-type]
    )


def require_roles(*roles: str):
    allowed = set(roles)

    async def _dep(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{current.role}' not allowed",
            )
        return current

    return _dep


def require_any(roles: Iterable[str]):
    return require_roles(*roles)
