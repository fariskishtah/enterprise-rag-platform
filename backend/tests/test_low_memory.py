import asyncio
import time
from threading import Event, Lock

import pytest
from starlette.testclient import TestClient

from app.ai.generation_queue import GenerationQueue
from app.core.config import Settings
from app.core.errors import GenerationQueueFullError
from app.core.security import get_password_hash
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


def test_runtime_profile_preserves_an_explicit_value_equal_to_the_class_default() -> None:
    settings = Settings(
        runtime_profile="low_memory",
        generation_max_new_tokens=256,
        max_context_characters=12000,
    )

    assert settings.generation_max_new_tokens == 256
    assert settings.max_context_characters == 12000


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
    assert settings.unload_transcription_model_after_use is True
    assert settings.warm_generation_model_on_startup is False
    assert settings.max_concurrent_heavy_operations == 1
    assert settings.heavy_queue_max_size == 2

    aliases = Settings.model_validate(
        {
            "ENTERPRISE_RAG_MAXIMUM_NEW_TOKENS": 88,
            "ENTERPRISE_RAG_MAXIMUM_CONTEXT_CHARACTERS": 2800,
        }
    )
    assert aliases.generation_max_new_tokens == 88
    assert aliases.max_context_characters == 2800


def test_production_defaults_to_fail_closed_demo_password_access() -> None:
    with pytest.raises(ValueError, match="strong session secret"):
        Settings(environment="production")

    settings = Settings(
        environment="production",
        session_secret="a-production-session-secret-that-is-long-enough",
        demo_password_hash=get_password_hash("a-long-production-demo-password"),
    )
    assert settings.access_mode == "demo_password"


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


def test_heavy_queue_is_bounded_and_reports_busy_without_unbounded_waiting() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=1, max_queue_size=1)

    async def queued_work() -> None:
        async with await queue.acquire():
            pass

    async def main() -> None:
        async with await queue.acquire():
            waiter = asyncio.create_task(queued_work())
            for _ in range(20):
                if queue.stats.queued == 1:
                    break
                await asyncio.sleep(0)
            with pytest.raises(GenerationQueueFullError):
                await queue.acquire()
        await waiter

    asyncio.run(main())


def test_generation_and_transcription_labels_share_one_non_overlapping_gate() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=1, max_queue_size=2)
    lock = Lock()
    active = 0
    maximum_active = 0
    order: list[str] = []

    def operation(label: str) -> None:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
            order.append(label)
        time.sleep(0.02)
        with lock:
            active -= 1

    async def run(label: str) -> None:
        slot = await queue.acquire()
        await queue.execute(slot, lambda: operation(label), timeout=1)

    async def main() -> None:
        await asyncio.gather(run("generation"), run("transcription"))

    asyncio.run(main())
    assert maximum_active == 1
    assert set(order) == {"generation", "transcription"}


def test_cancelled_heavy_request_retains_slot_until_worker_exits() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=0.02)
    worker_started = Event()
    release_worker = Event()

    def work() -> None:
        worker_started.set()
        release_worker.wait()

    async def main() -> None:
        slot = await queue.acquire()
        task = asyncio.create_task(queue.execute(slot, work, timeout=1))
        await asyncio.to_thread(worker_started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert queue.stats.active == 1
        release_worker.set()
        for _ in range(20):
            if queue.stats.active == 0:
                break
            await asyncio.sleep(0.005)
        assert queue.stats.active == 0

    asyncio.run(main())


def test_cancelled_queued_request_releases_queue_capacity() -> None:
    queue = GenerationQueue(max_concurrent=1, queue_timeout=1, max_queue_size=1)

    async def main() -> None:
        async with await queue.acquire():
            waiting = asyncio.create_task(queue.acquire())
            for _ in range(20):
                if queue.stats.queued == 1:
                    break
                await asyncio.sleep(0)
            assert queue.stats.queued == 1
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting
            assert queue.stats.queued == 0

        async with await queue.acquire(timeout=0.02):
            pass

    asyncio.run(main())


def test_manual_model_warmup_has_terminal_ready_state(client: TestClient) -> None:
    response = client.post("/api/v1/rag/warmup")
    configuration = client.get("/api/v1/rag/config")

    assert response.status_code == 202
    assert configuration.status_code == 200
    assert configuration.json()["warmup_status"] == "ready"


def test_document_processing_uses_shared_heavy_gate(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    document = upload_bytes(
        client,
        knowledge_base_id,
        "bounded-processing.txt",
        b"Document extraction and embedding share the heavy-operation gate.",
        "text/plain",
    )
    completed_before = client.app.state.generation_queue.stats.completed

    result = process_document(client, document["id"])

    assert result["status"] == "ready_for_chat"
    assert client.app.state.generation_queue.stats.completed == completed_before + 1


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
