"""Authentication routes for login, registration, and user session management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, get_runtime_settings
from app.core.config import Settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


class UserLoginRequest(BaseModel):
    email: str
    password: str


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


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegisterRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRead:
    existing = session.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists.",
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
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(
        subject=user.id, secret_key="demo-secret-key-change-in-prod", role=user.role
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.get("/me", response_model=UserRead)
def get_current_user_info() -> UserRead:
    return UserRead(
        id="dev-user-id",
        email="developer@enterprise-rag.local",
        full_name="Local Developer",
        role="admin",
        is_active=True,
    )
