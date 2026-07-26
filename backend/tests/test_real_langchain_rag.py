import json
from pathlib import Path
from typing import Any

from langchain_core.language_models.llms import LLM

from app.ai.langchain_engine.chains import CourseChainSuite
from app.ai.langchain_engine.document_pipeline import (
    DocumentIndexInput,
    LangChainDocumentPipeline,
)
from app.core.config import Settings


class RealRetrievalStructuredLLM(LLM):
    @property
    def _llm_type(self) -> str:
        return "real-retrieval-structured-test"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> str:
        del stop, run_manager, kwargs
        if "standalone retrieval query" in prompt:
            return json.dumps({"standalone_query": "compressor inspection interval"})
        if "Verify whether" in prompt:
            return json.dumps(
                {
                    "status": "supported",
                    "explanation": "The interval appears in the retrieved source.",
                    "unsupported_claims": [],
                }
            )
        return json.dumps(
            {
                "answer": "The compressor inspection interval is thirty days.",
                "citations": [
                    {
                        "document_id": "real-langchain-document",
                        "source_filename": "inspection.txt",
                        "chunk_id": (
                            prompt.split("[BEGIN_UNTRUSTED_SOURCE ", 1)[1].split("]", 1)[0]
                        ),
                        "quote": "The compressor inspection interval is thirty days.",
                        "page": None,
                        "section": 0,
                    }
                ],
                "not_found": False,
            }
        )


def test_real_huggingface_embeddings_faiss_retriever_lcel_and_parser(
    tmp_path: Path,
) -> None:
    backend_root = Path(__file__).parents[1]
    source = tmp_path / "inspection.txt"
    source.write_text(
        "The compressor inspection interval is thirty days. "
        "Technicians record vibration during each inspection.",
        encoding="utf-8",
    )
    settings = Settings(
        model_cache_path=backend_root / "data" / "models",
        langchain_index_path=tmp_path / "faiss",
        hf_local_files_only=True,
        chunk_size=128,
        chunk_overlap=16,
    )
    pipeline = LangChainDocumentPipeline.from_settings(settings, device="cpu")
    pipeline.index_document(
        DocumentIndexInput(
            path=source,
            document_id="real-langchain-document",
            knowledge_base_id="real-langchain-kb",
            source_filename=source.name,
            document_type="txt",
        )
    )
    suite = CourseChainSuite(
        llm=RealRetrievalStructuredLLM(),
        retriever=pipeline.retriever("real-langchain-kb", top_k=2),
    )
    state = suite.invoke(question="What is the compressor inspection interval?")
    assert "thirty days" in state["answer"].answer
    assert state["answer"].citations
    assert state["verification"].status == "supported"
    assert state["documents"][0].metadata["source_filename"] == "inspection.txt"
