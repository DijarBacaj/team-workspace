from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from team_workspace.dependencies import CurrentUser, SessionDep
from team_workspace.errors import AppError
from team_workspace.models import RefreshToken, User
from team_workspace.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenPair,
    UserPublic,
    UserRegister,
)
from team_workspace.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_subject,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
users_router = APIRouter(prefix="/users", tags=["users"])


async def issue_token_pair(session: SessionDep, user_id: UUID) -> TokenPair:
    access_token, expires_in = create_access_token(user_id)
    refresh_token, jti, expires_at = create_refresh_token(user_id)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_jti=jti,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(payload: UserRegister, session: SessionDep) -> User:
    email = str(payload.email).lower()
    existing_user = await session.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise AppError(
            409, "email_already_registered", "The email is already registered."
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "email_already_registered",
            "The email is already registered.",
        ) from exc
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: SessionDep) -> TokenPair:
    email = str(payload.email).lower()
    user = await session.scalar(select(User).where(User.email == email))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise AppError(401, "invalid_credentials", "The email or password is invalid.")
    return await issue_token_pair(session, user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenPair:
    token_payload = decode_token(payload.refresh_token, "refresh")
    user_id = token_subject(token_payload)
    stored_token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_jti == str(token_payload["jti"]),
            RefreshToken.user_id == user_id,
        )
    )
    user = await session.get(User, user_id)
    now = datetime.now(timezone.utc)
    expires_at = stored_token.expires_at if stored_token is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        stored_token is None
        or stored_token.revoked_at is not None
        or expires_at is None
        or expires_at <= now
    ):
        raise AppError(401, "invalid_refresh_token", "The refresh token is invalid.")
    if user is None or not user.is_active:
        raise AppError(401, "invalid_user", "The authenticated user is unavailable.")

    stored_token.revoked_at = now
    await session.flush()
    return await issue_token_pair(session, user.id)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest, session: SessionDep) -> MessageResponse:
    token_payload = decode_token(payload.refresh_token, "refresh")
    stored_token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_jti == str(token_payload["jti"]),
            RefreshToken.user_id == token_subject(token_payload),
        )
    )
    if stored_token is not None and stored_token.revoked_at is None:
        stored_token.revoked_at = datetime.now(timezone.utc)
        await session.commit()
    return MessageResponse(message="Logout completed.")


@users_router.get("/me", response_model=UserPublic)
async def current_user(user: CurrentUser) -> User:
    return user
