"""Endpoints de autenticacion del backoffice."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from biomont_common.logging import get_logger

from app.api.dependencies import get_bo_users, get_current_user
from app.db.bo_user_repository import BoUserRepository
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.services.security import create_access_token, verify_password

_logger = get_logger("api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    bo_users: Annotated[BoUserRepository, Depends(get_bo_users)],
) -> TokenResponse:
    user = await bo_users.find_by_email(payload.email)
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        _logger.info(
            "auth_login_failed",
            action="login_failed",
            email_present=user is not None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    token, expires_in = create_access_token(user_id=user.id, role=user.role)
    _logger.info("auth_login_ok", action="login_ok", user_id=str(user.id))
    return TokenResponse(access_token=token, expires_in_seconds=expires_in)


@router.get("/me", response_model=CurrentUser)
async def me(
    current: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    return current
