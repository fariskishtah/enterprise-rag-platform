from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.ai.generation_queue import GenerationQueue
from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.core.config import Settings
from app.db.session import session_scope
from app.services.storage import LocalFileStorage


def get_db_session(request: Request) -> Iterator[Session]:
    with session_scope(request.app.state.session_factory) as session:
        yield session


def get_runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_file_storage(request: Request) -> LocalFileStorage:
    return request.app.state.file_storage


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    return request.app.state.embedding_provider


def get_generation_provider(request: Request) -> GenerationProvider:
    return request.app.state.generation_provider


def get_generation_queue(request: Request) -> GenerationQueue:
    return request.app.state.generation_queue
