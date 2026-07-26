import asyncio
from threading import Event

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


def test_aws_cpu_profile_uses_bounded_cpu_defaults_and_aliases() -> None:
    settings = Settings(runtime_profile="aws_cpu")
    assert settings.model_device == "cpu"
    assert settings.max_concurrent_generations == 1
    assert settings.generation_max_new_tokens == 96
    assert settings.max_context_characters == 3000
    assert settings.retrieval_top_k == 3
    assert settings.retrieval_candidate_pool == 12
    assert settings.generation_timeout_seconds == 120
    assert settings.summary_timeout_seconds == 180
    assert settings.generation_queue_timeout_seconds == 180
    assert settings.generation_do_sample is False
    assert settings.transcription_model_name == "base"
    assert settings.transcription_language == "auto"
    assert settings.transcription_compute_type == "int8"
    assert settings.transcription_cpu_threads == 2
    assert settings.transcription_num_workers == 1

    aliases = Settings.model_validate(
        {
            "ENTERPRISE_RAG_MAXIMUM_NEW_TOKENS": 88,
            "ENTERPRISE_RAG_MAXIMUM_CONTEXT_CHARACTERS": 2800,
        }
    )
    assert aliases.generation_max_new_tokens == 88
    assert aliases.max_context_characters == 2800


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


def test_timed_out_generation_keeps_slot_until_worker_actually_finishes() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=0.02)
    release_worker = Event()

    async def main() -> None:
        slot = await queue.acquire()
        with pytest.raises(TimeoutError):
            await queue.execute(slot, release_worker.wait, timeout=0.01)
        assert queue.stats.active == 1
        with pytest.raises(TimeoutError):
            await queue.acquire(timeout=0.01)

        release_worker.set()
        for _ in range(20):
            if queue.stats.active == 0:
                break
            await asyncio.sleep(0.005)
        assert queue.stats.active == 0

        async with await queue.acquire(timeout=0.02):
            pass

    asyncio.run(main())


def test_manual_model_warmup_has_terminal_ready_state(client: TestClient) -> None:
    response = client.post("/api/v1/rag/warmup")
    configuration = client.get("/api/v1/rag/config")

    assert response.status_code == 202
    assert configuration.status_code == 200
    assert configuration.json()["warmup_status"] == "ready"


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
