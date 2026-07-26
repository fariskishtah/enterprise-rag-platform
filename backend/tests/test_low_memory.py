import asyncio

import pytest
from starlette.testclient import TestClient

from app.ai.generation_queue import GenerationQueue
from app.core.config import Settings
from tests.helpers import create_knowledge_base, process_document, upload_bytes


def test_low_memory_profile_defaults() -> None:
    settings = Settings(runtime_profile="low_memory")
    assert settings.max_concurrent_generations == 1
    assert settings.max_context_characters == 4000
    assert settings.generation_max_new_tokens == 128
    assert settings.retrieval_top_k == 3
    assert settings.comparison_max_context_characters == 3000
    assert settings.generation_timeout_seconds == 45
    assert settings.langchain_force_wrapper is True


def test_generation_queue_stats_and_serialization() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=5)
    stats = queue.stats
    assert stats.active == 0
    assert stats.queued == 0

    async def run_task() -> None:
        async with await queue.acquire():
            await asyncio.sleep(0.01)

    async def main() -> None:
        await asyncio.gather(run_task(), run_task())

    asyncio.run(main())
    assert queue.stats.completed == 2
    assert queue.stats.active == 0


def test_generation_queue_timeout() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=0.05)

    async def main() -> None:
        await queue.acquire()
        with pytest.raises(asyncio.TimeoutError):
            await queue.acquire(timeout=0.05)

    asyncio.run(main())


def test_comparison_single_generation_call_via_api(client: TestClient) -> None:
    kb_id = create_knowledge_base(client)
    doc1 = upload_bytes(
        client, kb_id, "doc1.txt", b"Alpha feature details for monitoring.", "text/plain"
    )
    doc2 = upload_bytes(
        client, kb_id, "doc2.txt", b"Beta feature details for analysis.", "text/plain"
    )
    process_document(client, doc1["id"])
    process_document(client, doc2["id"])

    response = client.post(
        "/api/v1/intelligence/comparisons",
        json={"knowledge_base_id": kb_id, "document_ids": [doc1["id"], doc2["id"]]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["generation_calls"] == 1
    assert body["common_themes"]
    assert body["differences"]
