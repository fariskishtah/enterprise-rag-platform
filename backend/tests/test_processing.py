from pathlib import Path

from fastapi.testclient import TestClient

from app.document_processing.chunking import TextChunker
from app.document_processing.extraction import ExtractedSection
from tests.helpers import (
    create_knowledge_base,
    make_docx,
    make_encrypted_pdf,
    make_text_pdf,
    process_document,
    upload_bytes,
)


def test_processes_txt_with_metadata_and_deterministic_chunks(
    client: TestClient, storage_path: Path
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    content = (
        "Cooling systems require preventive maintenance every thirty days. "
        "A temperature above 85 degrees requires inspection. "
    ) * 5
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        "maintenance.txt",
        content.encode(),
        "text/plain",
    )

    processed = process_document(client, uploaded["id"])

    assert processed["status"] == "ready_for_chat"
    assert processed["character_count"] == len(content.strip())
    assert processed["chunk_count"] >= 2
    assert processed["indexed_chunk_count"] == processed["chunk_count"]
    assert processed["embedding_model"] == "local-hashing-128"
    assert processed["processing_attempts"] == 1
    assert processed["processing_error"] is None
    assert len(list(storage_path.rglob("*.txt"))) == 1

    extraction = client.get(f"/api/v1/documents/{uploaded['id']}/extraction").json()
    assert extraction["metadata"]["encoding"] == "utf-8"
    assert extraction["sections"][0]["metadata"]["source_kind"] == "text_section"

    first_chunks = client.get(
        f"/api/v1/documents/{uploaded['id']}/chunks?page=1&page_size=100"
    ).json()["items"]
    assert all(chunk["indexed_at"] for chunk in first_chunks)
    original_ids = [chunk["id"] for chunk in first_chunks]

    reprocessed = process_document(client, uploaded["id"])
    second_chunks = client.get(
        f"/api/v1/documents/{uploaded['id']}/chunks?page=1&page_size=100"
    ).json()["items"]
    assert reprocessed["processing_attempts"] == 2
    assert [chunk["id"] for chunk in second_chunks] == original_ids
    assert len(second_chunks) == len(original_ids)


def test_processes_pdf_and_preserves_page_number(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        "policy.pdf",
        make_text_pdf("Calibration is required every six months."),
        "application/pdf",
    )

    processed = process_document(client, uploaded["id"])
    extraction = client.get(f"/api/v1/documents/{uploaded['id']}/extraction").json()

    assert processed["status"] == "ready_for_chat"
    assert processed["page_count"] == 1
    assert extraction["sections"][0]["page_number"] == 1
    assert "Calibration" in extraction["sections"][0]["text"]


def test_processes_docx_and_preserves_heading_and_paragraphs(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        "operations.docx",
        make_docx(["Operations Guide", "Inspect vibration sensors before every shift."]),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    processed = process_document(client, uploaded["id"])
    extraction = client.get(f"/api/v1/documents/{uploaded['id']}/extraction").json()

    assert processed["status"] == "ready_for_chat"
    assert extraction["sections"][0]["heading"] == "Operations Guide"
    assert extraction["sections"][1]["metadata"]["source_kind"] == "docx_paragraph"


def test_empty_text_and_malformed_pdf_fail_safely(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    empty_text = upload_bytes(client, knowledge_base_id, "empty.txt", b"  \n\n ", "text/plain")
    malformed_pdf = upload_bytes(
        client,
        knowledge_base_id,
        "broken.pdf",
        b"%PDF-this-is-corrupt",
        "application/pdf",
    )

    empty_status = process_document(client, empty_text["id"])
    malformed_status = process_document(client, malformed_pdf["id"])

    assert empty_status["status"] == "failed"
    assert "No extractable text" in empty_status["processing_error"]
    assert malformed_status["status"] == "failed"
    assert "malformed" in malformed_status["processing_error"].lower()


def test_encrypted_pdf_is_rejected_during_processing(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        "encrypted.pdf",
        make_encrypted_pdf(),
        "application/pdf",
    )

    processed = process_document(client, uploaded["id"])

    assert processed["status"] == "failed"
    assert "password" in processed["processing_error"].lower()


def test_retry_failed_processing_is_bounded_and_duplicate_free(
    client: TestClient,
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    uploaded = upload_bytes(client, knowledge_base_id, "empty.txt", b" \n ", "text/plain")
    first = process_document(client, uploaded["id"])
    assert first["status"] == "failed"

    retry = client.post(f"/api/v1/documents/{uploaded['id']}/retry")
    assert retry.status_code == 202
    final = client.get(f"/api/v1/documents/{uploaded['id']}/processing").json()
    chunks = client.get(f"/api/v1/documents/{uploaded['id']}/chunks").json()

    assert final["status"] == "failed"
    assert final["processing_attempts"] == 2
    assert chunks["total"] == 0


def test_duplicate_document_is_prevented(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    content = b"One unique source."
    upload_bytes(client, knowledge_base_id, "first.txt", content, "text/plain")

    duplicate = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("renamed.txt", content, "text/plain")},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_document"
    assert client.get(f"/api/v1/knowledge-bases/{knowledge_base_id}/documents").json()["total"] == 1


def test_chunk_boundaries_overlap_and_metadata_are_preserved() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
    section = ExtractedSection(
        section_index=2,
        text=text,
        start_char=100,
        end_char=100 + len(text),
        page_number=7,
        heading="Limits",
        metadata={"source_kind": "pdf_page"},
    )
    chunker = TextChunker(chunk_size=24, chunk_overlap=6)

    chunks = chunker.chunk(
        document_id="doc",
        knowledge_base_id="kb",
        sections=[section],
    )

    assert len(chunks) > 1
    assert all(chunk.page_number == 7 for chunk in chunks)
    assert all(chunk.metadata["heading"] == "Limits" for chunk in chunks)
    assert chunks[1].start_char < chunks[0].end_char
    assert chunks[0].start_char >= 100
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunk_pagination_and_preview(client: TestClient) -> None:
    knowledge_base_id = create_knowledge_base(client)
    uploaded = upload_bytes(
        client,
        knowledge_base_id,
        "long.txt",
        ("sensor calibration protocol " * 80).encode(),
        "text/plain",
    )
    processed = process_document(client, uploaded["id"])
    assert processed["chunk_count"] > 2

    page = client.get(f"/api/v1/documents/{uploaded['id']}/chunks?page=2&page_size=2").json()
    preview = client.get(f"/api/v1/documents/{uploaded['id']}/preview?offset=5&limit=20").json()

    assert page["page"] == 2
    assert len(page["items"]) == 2
    assert preview["returned_characters"] == 20
    assert preview["truncated"] is True


def test_delete_document_removes_file_and_generated_content(
    client: TestClient, storage_path: Path
) -> None:
    knowledge_base_id = create_knowledge_base(client)
    uploaded = upload_bytes(
        client, knowledge_base_id, "delete.txt", b"delete this source", "text/plain"
    )
    process_document(client, uploaded["id"])
    assert list(storage_path.rglob("*.txt"))

    response = client.delete(f"/api/v1/documents/{uploaded['id']}")

    assert response.status_code == 204
    assert not list(storage_path.rglob("*.txt"))
    assert client.get(f"/api/v1/documents/{uploaded['id']}").status_code == 404
