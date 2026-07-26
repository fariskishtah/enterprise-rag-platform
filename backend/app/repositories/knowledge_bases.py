from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, name: str, description: str | None) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(name=name.strip(), description=description)
        self.session.add(knowledge_base)
        self.session.commit()
        self.session.refresh(knowledge_base)
        return knowledge_base

    def get(self, knowledge_base_id: str) -> KnowledgeBase | None:
        return self.session.get(KnowledgeBase, knowledge_base_id)

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
        return (row[0], int(row[1])) if row else None

    def list_with_document_counts(self) -> list[tuple[KnowledgeBase, int]]:
        document_count = (
            select(func.count(Document.id))
            .where(Document.knowledge_base_id == KnowledgeBase.id)
            .correlate(KnowledgeBase)
            .scalar_subquery()
        )
        statement = select(KnowledgeBase, document_count).order_by(KnowledgeBase.created_at.desc())
        return [(row[0], int(row[1])) for row in self.session.execute(statement).all()]
