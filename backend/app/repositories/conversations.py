from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import ChatMessage, ChatRole, ChatSession


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_session(self, knowledge_base_id: str, title: str) -> ChatSession:
        chat_session = ChatSession(
            knowledge_base_id=knowledge_base_id,
            title=title.strip()[:200],
        )
        self.session.add(chat_session)
        self.session.commit()
        self.session.refresh(chat_session)
        return chat_session

    def get_session(self, session_id: str) -> ChatSession | None:
        return self.session.get(ChatSession, session_id)

    def list_sessions(self, knowledge_base_id: str | None = None) -> list[ChatSession]:
        statement = select(ChatSession)
        if knowledge_base_id is not None:
            statement = statement.where(ChatSession.knowledge_base_id == knowledge_base_id)
        statement = statement.order_by(ChatSession.updated_at.desc())
        return list(self.session.scalars(statement).all())

    def add_message(
        self,
        *,
        chat_session: ChatSession,
        role: ChatRole,
        content: str,
        original_question: str | None = None,
        rewritten_query: str | None = None,
        citations: list[dict[str, object]] | None = None,
        model_metadata: dict[str, object] | None = None,
        verification: dict[str, object] | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=chat_session.id,
            role=role,
            content=content,
            original_question=original_question,
            rewritten_query=rewritten_query,
            citations=citations or [],
            model_metadata=model_metadata or {},
            verification=verification or {},
        )
        chat_session.updated_at = datetime.now(UTC)
        self.session.add_all([chat_session, message])
        self.session.commit()
        self.session.refresh(message)
        return message

    def recent_messages(self, session_id: str, limit: int) -> list[ChatMessage]:
        if limit <= 0:
            return []
        statement = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        return list(reversed(self.session.scalars(statement).all()))

    def all_messages(self, session_id: str) -> list[ChatMessage]:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return list(self.session.scalars(statement).all())

    def delete_session(self, chat_session: ChatSession) -> None:
        self.session.delete(chat_session)
        self.session.commit()
