from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, get_runtime_settings
from app.core.config import Settings
from app.core.errors import NotFoundError, UploadValidationError
from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseList, KnowledgeBaseRead
from app.services.lifecycle import demo_expiry

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge bases"])


def to_read_model(knowledge_base: KnowledgeBase, document_count: int) -> KnowledgeBaseRead:
    return KnowledgeBaseRead(
        id=knowledge_base.id,
        name=knowledge_base.name,
        description=knowledge_base.description,
        document_count=document_count,
        created_at=knowledge_base.created_at,
        updated_at=knowledge_base.updated_at,
        last_accessed_at=knowledge_base.last_accessed_at,
        expires_at=knowledge_base.expires_at,
        is_protected=knowledge_base.is_protected,
    )


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> KnowledgeBaseRead:
    existing_count = session.scalar(select(func.count(KnowledgeBase.id))) or 0
    if existing_count >= settings.max_knowledge_bases:
        raise UploadValidationError(
            code="knowledge_base_quota_exceeded",
            message=(
                "The public demo knowledge-base limit has been reached. "
                "Use an existing collection, wait for expired demo data cleanup, "
                "or ask the operator to make capacity available."
            ),
        )
    repository = KnowledgeBaseRepository(session)
    knowledge_base = repository.create(
        name=payload.name,
        description=payload.description,
        expires_at=demo_expiry(settings.demo_data_retention_hours),
    )
    return to_read_model(knowledge_base, 0)


@router.get("", response_model=KnowledgeBaseList)
def list_knowledge_bases(
    session: Annotated[Session, Depends(get_db_session)],
) -> KnowledgeBaseList:
    rows = KnowledgeBaseRepository(session).list_with_document_counts()
    items = [to_read_model(knowledge_base, count) for knowledge_base, count in rows]
    return KnowledgeBaseList(items=items, total=len(items))


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(
    knowledge_base_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> KnowledgeBaseRead:
    row = KnowledgeBaseRepository(session).get_with_document_count(knowledge_base_id)
    if row is None:
        raise NotFoundError("Knowledge base")
    return to_read_model(*row)
