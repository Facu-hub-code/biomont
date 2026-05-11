"""Funciones de seguridad: hashing argon2 y JWT.

No usar nada de esto fuera de capa `services` o tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.settings import BackofficeApiSettings, get_backoffice_settings

_HASHER = PasswordHasher()


def hash_password(plain: str) -> str:
    return _HASHER.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _HASHER.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    user_id: UUID,
    role: str,
    settings: BackofficeApiSettings | None = None,
) -> tuple[str, int]:
    cfg = settings or get_backoffice_settings()
    expires_in_seconds = cfg.jwt_expiration_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    token = jwt.encode(
        payload,
        cfg.jwt_secret.get_secret_value(),
        algorithm=cfg.jwt_algorithm,
    )
    return token, expires_in_seconds


def decode_access_token(
    token: str,
    settings: BackofficeApiSettings | None = None,
) -> dict:
    cfg = settings or get_backoffice_settings()
    return jwt.decode(
        token,
        cfg.jwt_secret.get_secret_value(),
        algorithms=[cfg.jwt_algorithm],
    )
