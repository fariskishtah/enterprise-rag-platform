"""Public-demo and account authentication routes."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, get_runtime_settings
from app.core.config import Settings
from app.core.errors import AppError
from app.core.middleware import client_fingerprint
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


class UserRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=72)
    full_name: str = ""


class UserLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=72)


class DemoLoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str


class UserRead(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool


class AccessConfiguration(BaseModel):
    mode: Literal["open", "demo_password", "accounts"]
    session_expiry_minutes: int


class SessionRead(BaseModel):
    mode: Literal["open", "demo_password", "accounts"]
    authenticated: bool
    expires_at: int | None = None
    role: str | None = None


def _auth_error(*, locked: bool = False) -> AppError:
    return AppError(
        status_code=429 if locked else 401,
        code="authentication_temporarily_locked" if locked else "invalid_credentials",
        message=(
            "Too many sign-in attempts. Wait before trying again."
            if locked
            else "The sign-in details are invalid."
        ),
    )


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    maximum_age = settings.session_expiry_minutes * 60
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=maximum_age,
        expires=maximum_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/config", response_model=AccessConfiguration)
def access_configuration(
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> AccessConfiguration:
    return AccessConfiguration(
        mode=settings.access_mode,
        session_expiry_minutes=settings.session_expiry_minutes,
    )


@router.get("/session", response_model=SessionRead)
def session_status(
    request: Request,
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> SessionRead:
    principal = getattr(request.state, "principal", None)
    return SessionRead(
        mode=settings.access_mode,
        authenticated=principal is not None,
        expires_at=int(principal["exp"]) if principal and "exp" in principal else None,
        role=str(principal.get("role")) if principal and principal.get("role") else None,
    )


@router.post("/demo/login", response_model=SessionRead)
def demo_login(
    payload: DemoLoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> SessionRead:
    if settings.access_mode != "demo_password":
        raise _auth_error()
    key = client_fingerprint(request)
    limiter = request.app.state.login_limiter
    if limiter.is_locked(key):
        raise _auth_error(locked=True)
    password_hash = settings.demo_password_hash or ""
    if not verify_password(payload.password, password_hash):
        raise _auth_error(locked=limiter.failure(key))
    limiter.success(key)
    token = create_access_token(
        "public-demo",
        settings.session_secret,
        timedelta(minutes=settings.session_expiry_minutes),
        role="demo",
        token_kind="demo",
    )
    _set_session_cookie(response, token, settings)
    claims_expiry = settings.session_expiry_minutes * 60
    return SessionRead(
        mode=settings.access_mode,
        authenticated=True,
        expires_at=int(time.time()) + claims_expiry,
        role="demo",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegisterRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> UserRead:
    if settings.access_mode != "accounts":
        raise AppError(
            status_code=404,
            code="registration_unavailable",
            message="Account registration is not available in this access mode.",
        )
    existing = session.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise AppError(
            status_code=409,
            code="account_conflict",
            message="An account with those details already exists.",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name or payload.email.split("@")[0],
        role=UserRole.USER,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: UserLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> TokenResponse:
    if settings.access_mode != "accounts":
        raise _auth_error()
    key = client_fingerprint(request)
    limiter = request.app.state.login_limiter
    if limiter.is_locked(key):
        raise _auth_error(locked=True)
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if (
        not user
        or not user.is_active
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise _auth_error(locked=limiter.failure(key))
    limiter.success(key)
    token = create_access_token(
        subject=user.id,
        secret_key=settings.session_secret,
        expires_delta=timedelta(minutes=settings.session_expiry_minutes),
        role=user.role,
        token_kind="account",
    )
    _set_session_cookie(response, token, settings)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.get("/me", response_model=UserRead)
def get_current_user_info(request: Request) -> UserRead:
    principal = getattr(request.state, "principal", {})
    role = str(principal.get("role", "admin"))
    return UserRead(
        id=str(principal.get("sub", "local-development")),
        email="demo@enterprise-rag.local",
        full_name="EnterpriseRAG Demo",
        role=role,
        is_active=True,
    )
