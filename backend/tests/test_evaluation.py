from fastapi.testclient import TestClient

from tests.helpers import create_knowledge_base


def test_evaluation_uses_heavy_gate_and_reports_measured_metrics(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    dataset = client.post(
        "/api/v1/evaluation/datasets",
        json={
            "knowledge_base_id": knowledge_base_id,
            "name": "Deterministic unsupported-answer check",
        },
    )
    assert dataset.status_code == 201
    case = client.post(
        "/api/v1/evaluation/cases",
        json={
            "dataset_id": dataset.json()["id"],
            "question": "What fact is absent from this empty knowledge base?",
            "is_supported": False,
        },
    )
    assert case.status_code == 201

    completed_before = client.app.state.generation_queue.stats.completed
    result = client.post(
        "/api/v1/evaluation/runs",
        params={"dataset_id": dataset.json()["id"]},
    )

    assert result.status_code == 200, result.text
    assert result.json()["correctness_rate"] == 1.0
    assert result.json()["faithfulness_rate"] == 1.0
    assert result.json()["citation_accuracy"] == 1.0
    assert client.app.state.generation_queue.stats.completed == completed_before + 1


def test_empty_feedback_analytics_do_not_claim_placeholder_success(
    client: TestClient,
) -> None:
    result = client.get("/api/v1/feedback/analytics")

    assert result.status_code == 200
    assert result.json()["total_feedback"] == 0
    assert result.json()["helpful_rate"] == 0.0


def test_demo_seed_creates_real_indexed_samples_without_fabricated_metrics(
    client: TestClient,
) -> None:
    completed_before = client.app.state.generation_queue.stats.completed

    result = client.post("/api/v1/demo/seed")

    assert result.status_code == 201, result.text
    knowledge_base_id = result.json()["knowledge_base_id"]
    documents = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents"
    ).json()["items"]
    assert len(documents) == 2
    assert all(value["status"] == "ready_for_chat" for value in documents)
    assert all(value["indexed_chunk_count"] > 0 for value in documents)
    assert client.get(f"/api/v1/documents/{documents[0]['id']}/content").status_code == 200
    assert client.get("/api/v1/evaluation/runs").json() == []
    assert client.get("/api/v1/feedback/analytics").json()["total_feedback"] == 0
    assert client.app.state.generation_queue.stats.completed == completed_before + 1
