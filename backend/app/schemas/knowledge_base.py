from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    document_count: int
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime
    expires_at: datetime | None
    is_protected: bool


class KnowledgeBaseList(BaseModel):
    items: list[KnowledgeBaseRead]
    total: int
