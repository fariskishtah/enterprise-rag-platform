from __future__ import annotations

import re

import numpy as np
from fastapi.testclient import TestClient

from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.services.answer_processing import AnswerPostProcessor
from app.services.language import detect_language
from tests.helpers import create_knowledge_base, process_document, upload_bytes


class MultilingualFixtureEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "deterministic-multilingual-v1") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @staticmethod
    def _embed(text: str) -> np.ndarray:
        normalized = text.lower()
        if any(
            term in normalized
            for term in ("remote", "work from home", "عن بعد", "بُعد", "أسبوع", "العمل")
        ):
            return np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
        if any(term in normalized for term in ("atlas", "launch", "أطلس", "إطلاق")):
            return np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        return np.asarray([0.0, 0.0, 1.0], dtype=np.float32)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._embed(text) for text in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)


class CapturingMultilingualGenerationProvider(GenerationProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    @property
    def model_name(self) -> str:
        return "deterministic-multilingual-generator"

    def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        top_k: int = 50,
        top_p: float = 0.9,
        repetition_penalty: float = 1.0,
        do_sample: bool | None = None,
    ) -> str:
        del temperature, max_new_tokens, top_k, top_p, repetition_penalty, do_sample
        self.prompts.append(prompt)
        chunk_id = re.search(r"\[BEGIN_UNTRUSTED_SOURCE ([^\]]+)]", prompt)
        citation = f" [SOURCE:{chunk_id.group(1)}]" if chunk_id else ""
        if "Answer in Arabic" in prompt:
            return f"يسمح الدليل بالعمل عن بُعد ثلاثة أيام أسبوعياً.{citation}"
        return f"The evidence allows remote work three days per week.{citation}"


def _prepare_multilingual_sources(
    client: TestClient,
) -> tuple[str, CapturingMultilingualGenerationProvider]:
    embedding = MultilingualFixtureEmbeddingProvider()
    generation = CapturingMultilingualGenerationProvider()
    client.app.state.embedding_provider = embedding
    client.app.state.generation_provider = generation
    knowledge_base_id = create_knowledge_base(client, "Arabic and English policies")
    english = upload_bytes(
        client,
        knowledge_base_id,
        "remote-en.txt",
        b"Employees may work remotely for three days per week.",
        "text/plain",
    )
    arabic = upload_bytes(
        client,
        knowledge_base_id,
        "remote-ar.txt",
        "يسمح للموظفين بالعمل عن بُعد ثلاثة أيام أسبوعياً.".encode(),
        "text/plain",
    )
    process_document(client, english["id"])
    process_document(client, arabic["id"])
    return knowledge_base_id, generation


def test_arabic_language_detection_and_answer_post_processing_preserve_text() -> None:
    assert detect_language("ما سياسة العمل عن بُعد؟") == "ar"
    processed = AnswerPostProcessor().process(
        question="ما السياسة؟",
        raw_answer="تسمح السياسة بثلاثة أيام أسبوعياً. [SOURCE:chunk-ar]",
        sources=[],
        response_mode="concise",
        output_language="ar",
    )
    assert processed.visible_answer == "تسمح السياسة بثلاثة أيام أسبوعياً."
    assert processed.cited_chunk_ids == ["chunk-ar"]


def test_arabic_and_english_questions_use_requested_language_and_grounded_citations(
    client: TestClient,
) -> None:
    knowledge_base_id, generation = _prepare_multilingual_sources(client)

    arabic_over_mixed = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "كم يوماً يسمح بالعمل عن بُعد؟", "output_language": "auto"},
    )
    english_over_arabic = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "How many remote work days are allowed?", "output_language": "en"},
    )

    assert arabic_over_mixed.status_code == 200, arabic_over_mixed.text
    assert arabic_over_mixed.json()["output_language"] == "ar"
    assert "ثلاثة" in arabic_over_mixed.json()["answer"]
    assert arabic_over_mixed.json()["citations"]
    assert english_over_arabic.status_code == 200, english_over_arabic.text
    assert english_over_arabic.json()["output_language"] == "en"
    assert "three days" in english_over_arabic.json()["answer"]
    assert english_over_arabic.json()["citations"]
    assert "Use only facts in the source blocks" in generation.prompts[0]
    assert "Answer in Arabic" in generation.prompts[0]
    assert "Do not invent names, numbers, dates" in generation.prompts[0]


def test_unsupported_arabic_question_and_arabic_follow_up_are_terminal_and_localized(
    client: TestClient,
) -> None:
    knowledge_base_id, _generation = _prepare_multilingual_sources(client)
    first = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "ما سياسة العمل عن بُعد؟"},
    ).json()
    follow_up = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={
            "question": "وماذا عن الحد الأسبوعي؟",
            "session_id": first["session_id"],
            "debug": True,
        },
    )
    unsupported = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
        json={"question": "ما لون المركبة الموجودة على المريخ؟"},
    )

    assert follow_up.status_code == 200, follow_up.text
    assert "ما سياسة العمل" in follow_up.json()["debug"]["rewritten_query"]
    assert follow_up.json()["citations"]
    assert unsupported.status_code == 200, unsupported.text
    assert unsupported.json()["not_found"] is True
    assert unsupported.json()["output_language"] == "ar"
    assert unsupported.json()["answer"].startswith("لا تحتوي المستندات")
    assert unsupported.json()["citations"] == []


def test_arabic_summary_and_report_prompts_and_headings(client: TestClient) -> None:
    knowledge_base_id, generation = _prepare_multilingual_sources(client)
    document_id = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents"
    ).json()["items"][0]["id"]
    summary = client.post(
        "/api/v1/intelligence/summaries",
        json={
            "knowledge_base_id": knowledge_base_id,
            "document_ids": [document_id],
            "kind": "executive_summary",
            "output_language": "ar",
        },
    )
    report = client.post(
        "/api/v1/intelligence/reports",
        json={
            "knowledge_base_id": knowledge_base_id,
            "document_ids": [document_id],
            "title": "تقرير سياسة العمل",
            "objective": "تقييم سياسة العمل عن بُعد",
            "output_language": "ar",
        },
    )

    assert summary.status_code == 200, summary.text
    assert summary.json()["output_language"] == "ar"
    assert any("Answer in Arabic" in prompt for prompt in generation.prompts)
    assert report.status_code == 200, report.text
    assert report.json()["output_language"] == "ar"
    assert "## الملخص التنفيذي" in report.json()["markdown"]
    assert "## المخاطر والقيود" in report.json()["markdown"]


def test_embedding_model_change_requires_explicit_reindex(client: TestClient) -> None:
    knowledge_base_id, _generation = _prepare_multilingual_sources(client)
    client.app.state.embedding_provider = MultilingualFixtureEmbeddingProvider(
        "deterministic-multilingual-v2"
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/retrieve",
        json={"query": "remote work"},
    )
    configuration = client.get("/api/v1/rag/config")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "embedding_model_reindex_required"
    assert configuration.json()["embedding_reindex_required"] is True
