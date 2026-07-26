from fastapi.testclient import TestClient

from tests.helpers import create_knowledge_base, process_document, upload_bytes

EXPECTED_CASES = [
    (
        "How many remote days are employees allowed per week?",
        ("up to three days",),
    ),
    (
        "Which days are designated collaboration days?",
        ("Tuesday", "Thursday"),
    ),
    (
        "When can an employee request a fully remote arrangement?",
        ("more than 120 kilometres", "assigned office"),
    ),
    (
        "Who must approve the fully remote arrangement?",
        ("department director", "People Operations"),
    ),
    (
        "How much is the home-office allowance and when is it available?",
        ("GBP 600", "after 30 days"),
    ),
]


def _prepare_policy(client: TestClient) -> tuple[str, str]:
    knowledge_base_id = create_knowledge_base(client, "Remote Work Policy")
    pdf = (
        __import__("pathlib").Path(__file__).parent / "fixtures" / "remote_work_policy.pdf"
    ).read_bytes()
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        "remote_work_policy.pdf",
        pdf,
        "application/pdf",
    )
    processed = process_document(client, uploaded["id"])
    assert processed["status"] == "ready_for_chat"
    assert processed["character_count"] > 400
    assert processed["chunk_count"] > 0
    assert processed["indexed_chunk_count"] == processed["chunk_count"]
    return knowledge_base_id, uploaded["id"]


def test_deterministic_policy_pdf_real_api_answer_quality(client: TestClient) -> None:
    knowledge_base_id, document_id = _prepare_policy(client)
    for question, expected_phrases in EXPECTED_CASES:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
            json={"question": question, "debug": True},
        )
        assert response.status_code == 200, response.text
        value = response.json()
        answer_lower = value["answer"].lower()
        assert all(phrase.lower() in answer_lower for phrase in expected_phrases)
        assert value["not_found"] is False
        assert value["citations"]
        assert value["citations"][0]["document_id"] == document_id
        citation_text = " ".join(item["passage"] for item in value["citations"]).lower()
        assert all(phrase.lower() in citation_text for phrase in expected_phrases)
        assert value["support_status"] in {
            "fully_supported",
            "partially_supported",
        }
        assert value["debug"]["retrieval_diagnostics"]["strategy"] == ("hybrid_dense_bm25_rerank")
        assert value["retrieved_sources"][0]["reranking_score"] >= 0
        sentences = [part.strip() for part in value["answer"].split(".") if part.strip()]
        assert len(sentences) == len(set(sentences))


def test_policy_unknown_answer_and_follow_up_context(client: TestClient) -> None:
    knowledge_base_id, _ = _prepare_policy(client)
    first = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "When can an employee request a fully remote arrangement?"},
    ).json()
    follow_up = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={
            "question": "What approvals does it need?",
            "session_id": first["session_id"],
            "debug": True,
        },
    ).json()
    assert "department director" in follow_up["answer"].lower()
    assert "people operations" in follow_up["answer"].lower()
    assert "fully remote arrangement" in follow_up["debug"]["rewritten_query"].lower()

    unknown = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "Who is the CEO?"},
    ).json()
    assert unknown["not_found"] is True
    assert unknown["citations"] == []
    assert "do not contain enough information" in unknown["answer"]
