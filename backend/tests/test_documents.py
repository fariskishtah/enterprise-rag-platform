import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient


def make_docx() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document><body>Knowledge</body></document>")
    return output.getvalue()


def test_upload_supported_documents_and_track_status(
    client: TestClient, knowledge_base_id: str, storage_path: Path
) -> None:
    samples = [
        ("notes.txt", b"Enterprise knowledge has a reliable source.", "text/plain", "txt"),
        ("paper.pdf", b"%PDF-1.4\nminimal test content", "application/pdf", "pdf"),
        (
            "brief.docx",
            make_docx(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        ),
    ]

    uploaded_ids: list[str] = []
    for filename, content, media_type, expected_type in samples:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={"file": (filename, content, media_type)},
        )
        assert response.status_code == 201
        body = response.json()
        uploaded_ids.append(body["id"])
        assert body["name"] == filename
        assert body["document_type"] == expected_type
        assert body["status"] == "uploaded"
        assert body["status_message"] == "Stored and ready for processing."
        assert len(body["checksum_sha256"]) == 64

    status_response = client.get(f"/api/v1/documents/{uploaded_ids[0]}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "uploaded"

    list_response = client.get(f"/api/v1/knowledge-bases/{knowledge_base_id}/documents")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 3
    assert len(list(storage_path.rglob("*.*"))) == 3


def test_document_count_is_reflected_on_knowledge_base(
    client: TestClient, knowledge_base_id: str
) -> None:
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("source.txt", b"A source document", "text/plain")},
    )
    assert response.status_code == 201

    knowledge_base = client.get(f"/api/v1/knowledge-bases/{knowledge_base_id}")
    assert knowledge_base.status_code == 200
    assert knowledge_base.json()["document_count"] == 1


def test_rejects_unsupported_document_type(client: TestClient, knowledge_base_id: str) -> None:
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("malware.exe", b"not executable", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_document_type"


def test_rejects_extension_spoofing(client: TestClient, knowledge_base_id: str) -> None:
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("fake.pdf", b"This is not a PDF", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pdf"


def test_rejects_unsupported_declared_mime_and_docx_compression_bomb(
    client: TestClient,
    knowledge_base_id: str,
) -> None:
    wrong_mime = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={"file": ("valid.pdf", b"%PDF-1.4\nvalid", "application/x-msdownload")},
    )
    assert wrong_mime.status_code == 415
    assert wrong_mime.json()["error"]["code"] == "unsupported_document_media_type"

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "A" * (512 * 1024))
    compressed_bomb = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
        files={
            "file": (
                "bomb.docx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert compressed_bomb.status_code == 422
    assert compressed_bomb.json()["error"]["code"] == "unsafe_docx_archive"


def test_rejects_oversized_upload(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'limited.db'}",
        storage_path=tmp_path / "limited-uploads",
        max_upload_bytes=8,
    )
    with TestClient(create_app(settings)) as limited_client:
        knowledge_base = limited_client.post(
            "/api/v1/knowledge-bases", json={"name": "Limited"}
        ).json()
        response = limited_client.post(
            f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
            files={"file": ("large.txt", b"more than eight bytes", "text/plain")},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"


def test_upload_to_missing_knowledge_base_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/knowledge-bases/missing/documents",
        files={"file": ("notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
