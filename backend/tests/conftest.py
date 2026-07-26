from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.providers.lightweight import (
    ExtractiveGenerationProvider,
    HashingEmbeddingProvider,
)
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def client(tmp_path: Path, storage_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_path=storage_path,
        max_upload_bytes=1024 * 1024,
        cors_origins=["http://testserver"],
        chunk_size=160,
        chunk_overlap=32,
        similarity_threshold=0.0,
        retrieval_top_k=4,
    )
    with TestClient(
        create_app(
            settings,
            embedding_provider=HashingEmbeddingProvider(dimension=128),
            generation_provider=ExtractiveGenerationProvider(),
        )
    ) as test_client:
        yield test_client


@pytest.fixture
def knowledge_base_id(client: TestClient) -> str:
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Research Library", "description": "Validated source material"},
    )
    assert response.status_code == 201
    return response.json()["id"]
