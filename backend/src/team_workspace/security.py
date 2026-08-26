from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from team_workspace.config import get_settings
from team_workspace.errors import AppError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: UUID) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: UUID) -> tuple[str, str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid4())
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti, expires_at


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise AppError(
            401, "invalid_token", "The token is invalid or expired."
        ) from exc

    if payload.get("type") != expected_type:
        raise AppError(401, "invalid_token", "The token type is invalid.")
    if not payload.get("sub") or not payload.get("jti"):
        raise AppError(401, "invalid_token", "The token payload is invalid.")
    return payload


def token_subject(payload: dict[str, Any]) -> UUID:
    try:
        return UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(401, "invalid_token", "The token subject is invalid.") from exc
