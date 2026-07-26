from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.langchain_engine.chains import CourseChainSuite
from app.ai.langchain_engine.document_pipeline import (
    DocumentIndexInput,
    LangChainDocumentPipeline,
)
from app.ai.langchain_engine.runtime import LangChainEngineRuntime
from app.ai.providers.huggingface import HuggingFaceGenerationProvider
from app.core.config import Settings


def _settings(
    *,
    model_name: str,
    temperature: float,
    top_k: int,
    top_p: float,
    max_new_tokens: int,
    repetition_penalty: float,
    do_sample: bool,
) -> Settings:
    runtime_root = PROJECT_ROOT / "course_demo" / ".runtime"
    return Settings(
        rag_engine="langchain",
        generation_model_name=model_name,
        storage_path=runtime_root / "uploads",
        langchain_index_path=runtime_root / "faiss",
        model_cache_path=BACKEND_ROOT / "data" / "models",
        generation_temperature=temperature,
        generation_top_k=top_k,
        generation_top_p=top_p,
        generation_max_new_tokens=max_new_tokens,
        generation_repetition_penalty=repetition_penalty,
        generation_do_sample=do_sample,
    )


def _langchain_runtime(settings: Settings) -> LangChainEngineRuntime:
    provider = HuggingFaceGenerationProvider(
        model_name=settings.generation_model_name,
        fallback_model_name=settings.generation_fallback_model_name,
        cache_path=settings.model_cache_path,
        device="cpu",
        local_files_only=settings.hf_local_files_only,
        quantization=settings.generation_quantization,
    )
    return LangChainEngineRuntime(
        settings=settings,
        generation_provider=provider,
        device="cpu",
    )


def _process_langchain_pdf(uploaded_file: Any, settings: Settings) -> dict[str, Any]:
    digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    runtime_dir = Path(tempfile.mkdtemp(prefix="enterprise-rag-course-"))
    document_path = runtime_dir / Path(uploaded_file.name).name
    document_path.write_bytes(uploaded_file.getvalue())
    pipeline = LangChainDocumentPipeline.from_settings(settings, device="cpu")
    count = pipeline.index_document(
        DocumentIndexInput(
            path=document_path,
            document_id=digest[:36],
            knowledge_base_id="streamlit-course-demo",
            source_filename=Path(uploaded_file.name).name,
            document_type="pdf",
        ),
        replace=True,
    )
    return {
        "pipeline": pipeline,
        "document_path": document_path,
        "chunk_count": count,
        "document_id": digest[:36],
    }


def _process_custom_pdf(uploaded_file: Any, api_url: str) -> dict[str, Any]:
    with httpx.Client(base_url=api_url, timeout=120.0) as client:
        knowledge_base = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Streamlit course demo"},
        )
        knowledge_base.raise_for_status()
        knowledge_base_id = knowledge_base.json()["id"]
        uploaded = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            files={
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    "application/pdf",
                )
            },
        )
        uploaded.raise_for_status()
        document = uploaded.json()
        processed = client.post(f"/api/v1/documents/{document['id']}/process")
        processed.raise_for_status()
    return {
        "knowledge_base_id": knowledge_base_id,
        "document_id": document["id"],
        "chunk_count": processed.json().get("chunk_count", 0),
    }


def _ask_custom(question: str, api_url: str, knowledge_base_id: str) -> dict[str, Any]:
    with httpx.Client(base_url=api_url, timeout=120.0) as client:
        response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/ask",
            json={"question": question, "debug": True},
        )
        response.raise_for_status()
        return response.json()


def _show_langchain_answer(
    question: str,
    pipeline: LangChainDocumentPipeline,
    settings: Settings,
) -> None:
    runtime = _langchain_runtime(settings)
    retriever = pipeline.retriever(
        "streamlit-course-demo",
        top_k=settings.retrieval_top_k,
    )
    suite = CourseChainSuite(
        llm=runtime.llm,
        retriever=retriever,
        parser_retries=settings.langchain_parser_retries,
    )
    state = suite.invoke(question=question)
    parsed = state["answer"]
    st.subheader("Grounded answer")
    st.write(parsed.answer)
    st.subheader("Citations")
    st.dataframe([citation.model_dump() for citation in parsed.citations])
    st.subheader("Retrieved chunks")
    for document in state["documents"]:
        with st.expander(str(document.metadata.get("chunk_id", "chunk"))):
            st.json(document.metadata)
            st.write(document.page_content)
    st.subheader("Parsed structured output")
    st.json(
        {
            "rewrite": state["rewrite"].model_dump(),
            "answer": parsed.model_dump(),
            "verification": state["verification"].model_dump(),
        }
    )


def main() -> None:
    st.set_page_config(
        page_title="EnterpriseRAG Course Demo", page_icon="📚", layout="wide"
    )
    st.title("EnterpriseRAG · Course Compatibility Demo")
    st.caption(
        "The React product remains primary. This is a separate Streamlit course surface."
    )

    with st.sidebar:
        engine = st.selectbox("RAG engine", ["langchain", "custom"])
        model_name = st.selectbox(
            "Generation model",
            ["Qwen/Qwen2.5-0.5B-Instruct", "google/flan-t5-base"],
        )
        temperature = st.slider("Temperature", 0.0, 2.0, 0.1, 0.05)
        generation_top_k = st.slider("Generation top_k", 0, 200, 50)
        top_p = st.slider("top_p", 0.05, 1.0, 0.9, 0.05)
        max_new_tokens = st.slider("max_new_tokens", 32, 1024, 256, 32)
        repetition_penalty = st.slider("Repetition penalty", 1.0, 3.0, 1.0, 0.05)
        do_sample = st.checkbox("Enable sampling", value=True)
        api_url = st.text_input("Custom-engine FastAPI URL", "http://localhost:8000")

    if do_sample and temperature <= 0:
        st.error("Temperature must be greater than zero when sampling is enabled.")
        st.stop()

    settings = _settings(
        model_name=model_name,
        temperature=temperature,
        top_k=generation_top_k,
        top_p=top_p,
        max_new_tokens=max_new_tokens,
        repetition_penalty=repetition_penalty,
        do_sample=do_sample,
    )
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded_file is not None and st.button("Process document", type="primary"):
        with st.spinner(f"Processing with the {engine} engine…"):
            if engine == "langchain":
                st.session_state.course_document = _process_langchain_pdf(
                    uploaded_file,
                    settings,
                )
            else:
                st.session_state.course_document = _process_custom_pdf(
                    uploaded_file, api_url
                )
            st.session_state.course_engine = engine
        st.success(
            f"Processed {st.session_state.course_document['chunk_count']} retrieval chunks."
        )

    document_state = st.session_state.get("course_document")
    if not document_state:
        st.info("Upload and process a PDF to begin.")
        return

    question = st.text_input("Ask a question about the document")
    ask_column, summary_column = st.columns(2)
    if ask_column.button("Ask", disabled=not question):
        with st.spinner("Retrieving and generating…"):
            if st.session_state.course_engine == "langchain":
                _show_langchain_answer(question, document_state["pipeline"], settings)
            else:
                result = _ask_custom(
                    question,
                    api_url,
                    document_state["knowledge_base_id"],
                )
                st.subheader("Grounded answer")
                st.write(result["answer"])
                st.subheader("Citations")
                st.dataframe(result["citations"])
                st.subheader("Retrieved chunks")
                st.json(result["retrieved_sources"])
                st.subheader("Parsed structured output")
                st.json(result)

    if summary_column.button(
        "Summarise document",
        disabled=st.session_state.course_engine != "langchain",
    ):
        pipeline = document_state["pipeline"]
        documents = pipeline.retrieve(
            "streamlit-course-demo",
            "Summarise the whole document",
            top_k=settings.retrieval_top_k,
        )
        runtime = _langchain_runtime(settings)
        suite = CourseChainSuite(
            llm=runtime.llm,
            retriever=pipeline.retriever(
                "streamlit-course-demo",
                top_k=settings.retrieval_top_k,
            ),
            parser_retries=settings.langchain_parser_retries,
        )
        summary = suite.summarize(documents)
        st.subheader("Structured summary")
        st.json(summary.model_dump())


if __name__ == "__main__":
    main()
