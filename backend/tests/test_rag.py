from fastapi.testclient import TestClient

from app.ai.providers.lightweight import HashingEmbeddingProvider
from app.db.session import session_scope
from app.services.retrieval import RetrievalService
from tests.helpers import (
    create_knowledge_base,
    process_document,
    upload_bytes,
)


def prepare_source(
    client: TestClient,
    *,
    knowledge_base_id: str,
    filename: str,
    content: str,
) -> dict[str, object]:
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        filename,
        content.encode(),
        "text/plain",
    )
    processed = process_document(client, uploaded["id"])
    assert processed["status"] == "ready_for_chat"
    return processed


def test_real_local_end_to_end_rag_pipeline_returns_grounded_citations(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    document = prepare_source(
        client,
        knowledge_base_id=knowledge_base_id,
        filename="maintenance.txt",
        content=(
            "The calibration schedule requires vibration sensors to be calibrated "
            "every six months. Calibration records are retained for two years."
        ),
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "What is the calibration schedule?", "debug": True},
    )

    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["not_found"] is False
    assert "six months" in answer["answer"]
    assert answer["citations"][0]["document_id"] == document["id"]
    assert answer["citations"][0]["chunk_id"]
    assert answer["retrieved_sources"][0]["score"] >= 0
    assert answer["verification"]["status"] in {
        "supported",
        "partially_supported",
    }
    assert answer["model_used"] == "local-extractive-integration"
    assert answer["debug"]["embedding_model"] == "local-hashing-128"
    assert answer["debug"]["final_context"]
    assert set(answer["debug"]["timings_ms"]) == {
        "query_rewrite",
        "retrieval",
        "generation",
        "total",
    }
    assert "token" not in str(answer["debug"]).lower()
    assert "secret" not in str(answer["debug"]).lower()


def test_vector_storage_persists_across_sessions(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    prepare_source(
        client,
        knowledge_base_id=knowledge_base_id,
        filename="durable.txt",
        content="Persistent vector storage retains compressor safety procedures.",
    )

    with session_scope(client.app.state.session_factory) as new_session:
        results, _ = RetrievalService(
            session=new_session,
            settings=client.app.state.settings,
            embedding_provider=HashingEmbeddingProvider(dimension=128),
        ).retrieve(
            knowledge_base_id=knowledge_base_id,
            query="compressor safety procedures",
            similarity_threshold=0.0,
        )

    assert results
    assert results[0].document_name == "durable.txt"


def test_retrieval_is_isolated_by_knowledge_base(client: TestClient) -> None:
    first_kb = create_knowledge_base(client, "Company A")
    second_kb = create_knowledge_base(client, "Company B")
    prepare_source(
        client,
        knowledge_base_id=first_kb,
        filename="alpha.txt",
        content="Alpha turbine pressure is limited to 40 PSI.",
    )
    prepare_source(
        client,
        knowledge_base_id=second_kb,
        filename="beta.txt",
        content="Beta reactor uses a confidential zirconium sequence.",
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{first_kb}/retrieve",
        json={"query": "zirconium sequence", "similarity_threshold": -1},
    )

    assert response.status_code == 200
    assert all(source["document_name"] == "alpha.txt" for source in response.json()["sources"])


def test_empty_retrieval_returns_not_found_without_generation(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    prepare_source(
        client,
        knowledge_base_id=knowledge_base_id,
        filename="temperature.txt",
        content="Temperature inspections occur weekly.",
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={
            "question": "What is the unrelated quantum finance policy?",
            "similarity_threshold": 0.999,
        },
    )

    assert response.status_code == 200
    answer = response.json()
    assert answer["not_found"] is True
    assert answer["citations"] == []
    assert answer["retrieval_quality"] == "no_results"
    assert "do not contain enough information" in answer["answer"]


def test_conversation_persistence_and_follow_up_query_rewriting(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    prepare_source(
        client,
        knowledge_base_id=knowledge_base_id,
        filename="method.txt",
        content=(
            "The inspection method uses thermal imaging. Its limitation is reduced "
            "accuracy through reflective surfaces."
        ),
    )
    first = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "What inspection method is used?"},
    ).json()

    follow_up_response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={
            "question": "What about its limitations?",
            "session_id": first["session_id"],
            "debug": True,
            "similarity_threshold": -1,
        },
    )

    assert follow_up_response.status_code == 200
    follow_up = follow_up_response.json()
    assert "What inspection method is used?" in follow_up["debug"]["rewritten_query"]
    session = client.get(f"/api/v1/chat-sessions/{first['session_id']}").json()
    assert len(session["messages"]) == 4
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][-1]["citations"]


def test_chat_session_cannot_cross_knowledge_bases(client: TestClient) -> None:
    first_kb = create_knowledge_base(client, "One")
    second_kb = create_knowledge_base(client, "Two")
    session = client.post(
        "/api/v1/chat-sessions",
        json={"knowledge_base_id": first_kb, "title": "Scoped"},
    ).json()

    response = client.post(
        f"/api/v1/knowledge-bases/{second_kb}/ask",
        json={"question": "Can this cross scope?", "session_id": session["id"]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "chat_session_knowledge_base_mismatch"


def test_rag_configuration_exposes_safe_model_settings(client: TestClient) -> None:
    response = client.get("/api/v1/rag/config")

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_overlap"] < body["chunk_size"]
    assert body["vector_store"] == "relational-float32"
    assert body["model_device"] == "local"
    assert body["model_warm"] is False
    assert set(body).isdisjoint({"api_key", "token", "secret"})
