from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk, DocumentSection
from app.services.lifecycle import mark_accessed


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, document: Document) -> Document:
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get(self, document_id: str) -> Document | None:
        value = self.session.get(Document, document_id)
        if value is not None:
            mark_accessed(value)
            self.session.commit()
        return value

    def find_by_checksum(self, knowledge_base_id: str, checksum_sha256: str) -> Document | None:
        statement = select(Document).where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.checksum_sha256 == checksum_sha256,
        )
        return self.session.scalar(statement)

    def list_for_knowledge_base(self, knowledge_base_id: str) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.desc())
        )
        values = list(self.session.scalars(statement).all())
        for value in values:
            mark_accessed(value)
        if values:
            self.session.commit()
        return values

    def replace_extraction(
        self,
        document: Document,
        sections: list[DocumentSection],
        chunks: list[DocumentChunk],
    ) -> None:
        self.session.execute(
            delete(DocumentSection).where(DocumentSection.document_id == document.id)
        )
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        self.session.add_all(sections)
        self.session.add_all(chunks)
        self.session.flush()

    def delete_generated_content(self, document_id: str) -> None:
        self.session.execute(
            delete(DocumentSection).where(DocumentSection.document_id == document_id)
        )
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        self.session.flush()

    def list_sections(self, document_id: str) -> list[DocumentSection]:
        statement = (
            select(DocumentSection)
            .where(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.section_index)
        )
        return list(self.session.scalars(statement).all())

    def list_chunks(
        self, document_id: str, *, offset: int = 0, limit: int = 50
    ) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement).all())

    def delete(self, document: Document) -> None:
        self.session.delete(document)
        self.session.commit()
