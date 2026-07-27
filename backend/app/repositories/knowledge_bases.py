from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.services.lifecycle import mark_accessed


class KnowledgeBaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        name: str,
        description: str | None,
        expires_at: datetime | None = None,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            name=name.strip(),
            description=description,
            expires_at=expires_at,
        )
        self.session.add(knowledge_base)
        self.session.commit()
        self.session.refresh(knowledge_base)
        return knowledge_base

    def get(self, knowledge_base_id: str) -> KnowledgeBase | None:
        value = self.session.get(KnowledgeBase, knowledge_base_id)
        if value is not None:
            mark_accessed(value)
            self.session.commit()
        return value

    def get_with_document_count(self, knowledge_base_id: str) -> tuple[KnowledgeBase, int] | None:
        document_count = (
            select(func.count(Document.id))
            .where(Document.knowledge_base_id == KnowledgeBase.id)
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        statement = select(KnowledgeBase, document_count).where(
            KnowledgeBase.id == knowledge_base_id
        )
        row = self.session.execute(statement).one_or_none()
        if not row:
            return None
        mark_accessed(row[0])
        self.session.commit()
        return row[0], int(row[1])

    def list_with_document_counts(self) -> list[tuple[KnowledgeBase, int]]:
        document_count = (
            select(func.count(Document.id))
            .where(Document.knowledge_base_id == KnowledgeBase.id)
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        statement = select(KnowledgeBase, document_count).order_by(KnowledgeBase.created_at.desc())
        rows = self.session.execute(statement).all()
        for row in rows:
            mark_accessed(row[0])
        if rows:
            self.session.commit()
        return [(row[0], int(row[1])) for row in rows]
