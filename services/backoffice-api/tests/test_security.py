"""Tests de hashing y JWT."""

from __future__ import annotations

import uuid

import pytest

from app.services.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("biomont-pwd-123")
    assert verify_password("biomont-pwd-123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token, expires_in = create_access_token(user_id=user_id, role="admin")
    assert expires_in > 0

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"


def test_access_token_invalid_secret_raises() -> None:
    import jwt

    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id=user_id, role="admin")
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "otra-secret", algorithms=["HS256"])
