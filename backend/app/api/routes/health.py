from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness check")
def ready(session: Annotated[Session, Depends(get_db_session)]) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}
