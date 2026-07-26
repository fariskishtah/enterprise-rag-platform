from fastapi.testclient import TestClient


def test_create_and_list_knowledge_bases(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Medical Research", "description": "Clinical research papers"},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Medical Research"
    assert created["description"] == "Clinical research papers"
    assert created["document_count"] == 0

    list_response = client.get("/api/v1/knowledge-bases")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == created["id"]


def test_get_missing_knowledge_base_uses_clear_error(client: TestClient) -> None:
    response = client.get("/api/v1/knowledge-bases/not-a-real-id")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "resource_not_found",
            "message": "Knowledge base was not found.",
        }
    }


def test_invalid_knowledge_base_request_uses_validation_schema(client: TestClient) -> None:
    response = client.post("/api/v1/knowledge-bases", json={"name": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
