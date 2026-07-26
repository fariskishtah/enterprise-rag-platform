from fastapi.testclient import TestClient

from app.ai.vectorstores.base import VectorSearchResult
from app.schemas.rag import ClaimSupportStatus, VerificationStatus
from app.services.verification import VerificationService
from tests.helpers import create_knowledge_base, process_document, upload_bytes


def processed_document(
    client: TestClient, knowledge_base_id: str, filename: str, content: str
) -> str:
    uploaded = upload_bytes(client, knowledge_base_id, filename, content.encode(), "text/plain")
    assert process_document(client, uploaded["id"])["status"] == "ready_for_chat"
    return uploaded["id"]


def test_document_summary_contains_references_and_verification(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    document_id = processed_document(
        client,
        knowledge_base_id,
        "study.txt",
        "The study observed a 12 percent reduction in downtime after sensor calibration.",
    )

    response = client.post(
        "/api/v1/intelligence/summaries",
        json={
            "knowledge_base_id": knowledge_base_id,
            "document_ids": [document_id],
            "kind": "whole_document",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "whole_document"
    assert body["citations"][0]["document_id"] == document_id
    assert body["verification"]["status"] in {
        "supported",
        "partially_supported",
    }


def test_key_points_and_section_summary_are_supported(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    document_id = processed_document(
        client,
        knowledge_base_id,
        "sections.txt",
        "First section covers motor safety.\n\nSecond section covers bearing wear.",
    )

    key_points = client.post(
        "/api/v1/intelligence/summaries",
        json={
            "knowledge_base_id": knowledge_base_id,
            "document_ids": [document_id],
            "kind": "key_points",
        },
    )
    section = client.post(
        "/api/v1/intelligence/summaries",
        json={
            "knowledge_base_id": knowledge_base_id,
            "document_ids": [document_id],
            "kind": "section",
            "section_index": 1,
        },
    )

    assert key_points.status_code == 200
    assert section.status_code == 200
    assert "bearing wear" in section.json()["content"]


def test_multi_document_comparison_has_structured_sections(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    first = processed_document(
        client,
        knowledge_base_id,
        "method-a.txt",
        "Method A uses acoustic monitoring and reports low installation cost.",
    )
    second = processed_document(
        client,
        knowledge_base_id,
        "method-b.txt",
        "Method B uses thermal monitoring and reports higher installation cost.",
    )

    response = client.post(
        "/api/v1/intelligence/comparisons",
        json={"knowledge_base_id": knowledge_base_id, "document_ids": [first, second]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    for field in (
        "common_themes",
        "differences",
        "contradictions",
        "methodologies",
        "conclusions",
        "limitations",
    ):
        assert body[field]
    assert {citation["document_id"] for citation in body["citations"]} == {
        first,
        second,
    }


def test_research_report_returns_structured_markdown(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    document_id = processed_document(
        client,
        knowledge_base_id,
        "risk.txt",
        "Bearing wear increases vibration risk. Monthly inspection reduces uncertainty.",
    )

    response = client.post(
        "/api/v1/intelligence/reports",
        json={
            "knowledge_base_id": knowledge_base_id,
            "document_ids": [document_id],
            "title": "Bearing Risk Review",
            "objective": "Assess bearing risk and inspection evidence.",
        },
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["title"] == "Bearing Risk Review"
    assert report["executive_summary"]
    assert report["findings"]
    assert report["risks_and_limitations"]
    assert report["markdown"].startswith("# Bearing Risk Review")
    assert "## Conclusions" in report["markdown"]
    assert report["cited_sources"]


def test_verification_detects_unsupported_statement() -> None:
    source = VectorSearchResult(
        chunk_id="chunk",
        document_id="doc",
        document_name="source.txt",
        text="The pump inspection interval is thirty days.",
        score=0.9,
        page_number=None,
        section_index=0,
        chunk_index=0,
        metadata={},
    )

    result = VerificationService().verify(
        "The reactor uses plutonium and must be inspected hourly.", [source]
    )

    assert result.status is VerificationStatus.UNSUPPORTED
    assert result.unsupported_statements


def test_verification_scopes_negation_to_the_matching_source_sentence() -> None:
    source = VectorSearchResult(
        chunk_id="chunk",
        document_id="document",
        document_name="policy.txt",
        text=(
            "The home-office allowance is GBP 600 and becomes available after "
            "30 days of employment. This policy does not state the CEO's name."
        ),
        score=0.9,
        page_number=None,
        section_index=0,
        chunk_index=0,
        metadata={},
    )

    result = VerificationService().verify(
        "The home-office allowance is GBP 600 and becomes available after 30 days.",
        [source],
    )

    assert result.claim_support is ClaimSupportStatus.FULLY_SUPPORTED
    assert result.contradiction_detected is False


def test_verification_detects_conflicting_numbers_in_matching_claims() -> None:
    source = VectorSearchResult(
        chunk_id="chunk",
        document_id="document",
        document_name="policy.txt",
        text="The home-office allowance is GBP 600 after 30 days of employment.",
        score=0.9,
        page_number=None,
        section_index=0,
        chunk_index=0,
        metadata={},
    )

    result = VerificationService().verify(
        "The home-office allowance is GBP 900 after 30 days of employment.",
        [source],
    )

    assert result.claim_support is ClaimSupportStatus.CONTRADICTION_DETECTED
    assert result.contradiction_detected is True


def test_document_selection_is_knowledge_base_scoped(client: TestClient) -> None:
    first_kb = create_knowledge_base(client, "First")
    second_kb = create_knowledge_base(client, "Second")
    foreign_document = processed_document(
        client, second_kb, "foreign.txt", "Foreign scoped content."
    )

    response = client.post(
        "/api/v1/intelligence/summaries",
        json={
            "knowledge_base_id": first_kb,
            "document_ids": [foreign_document],
            "kind": "whole_document",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_document_selection"
