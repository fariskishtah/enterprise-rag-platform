import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.helpers import create_knowledge_base, process_document, upload_bytes


@pytest.mark.real_models
@pytest.mark.skipif(
    os.getenv("RUN_REAL_MODEL_TESTS") != "1",
    reason="Set RUN_REAL_MODEL_TESTS=1 to run downloaded local models.",
)
def test_real_huggingface_models_complete_end_to_end_rag(
    tmp_path: Path,
) -> None:
    model_cache = Path(__file__).parents[1] / "data" / "models"
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'real-model.db'}",
        storage_path=tmp_path / "uploads",
        model_cache_path=model_cache,
        hf_local_files_only=True,
        generation_model_name="Qwen/Qwen2.5-0.5B-Instruct",
        generation_fallback_model_name="google/flan-t5-base",
        chunk_size=256,
        chunk_overlap=32,
        similarity_threshold=-1,
        generation_temperature=0,
        generation_do_sample=False,
        generation_max_new_tokens=64,
    )
    with TestClient(create_app(settings)) as client:
        knowledge_base_id = create_knowledge_base(client, "Real Model Integration")
        uploaded = upload_bytes(
            client,
            knowledge_base_id,
            "inspection.txt",
            (
                b"The compressor inspection interval is thirty days. "
                b"Technicians record pressure and vibration during every inspection."
            ),
            "text/plain",
        )
        processed = process_document(client, uploaded["id"])
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
            json={
                "question": "What is the compressor inspection interval?",
                "similarity_threshold": -1,
            },
        )

    assert processed["status"] == "ready_for_chat"
    assert processed["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["answer"].strip()
    assert answer["citations"]
    assert answer["model_used"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert answer["not_found"] is False
