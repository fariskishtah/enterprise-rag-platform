from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import ChatRole


class ChatSessionCreate(BaseModel):
    knowledge_base_id: str
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionList(BaseModel):
    items: list[ChatSessionRead]
    total: int


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: ChatRole
    content: str
    original_question: str | None
    rewritten_query: str | None
    citations: list[dict[str, Any]]
    model_metadata: dict[str, Any]
    verification: dict[str, Any]
    created_at: datetime


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead]
