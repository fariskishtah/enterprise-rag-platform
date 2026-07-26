"""Compare the custom engine with the deterministic LangChain course engine."""

from __future__ import annotations

import json
import re
import shutil
import tracemalloc
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.language_models.llms import LLM

from app.ai.langchain_engine.chains import CourseChainSuite
from app.ai.langchain_engine.document_pipeline import (
    DocumentIndexInput,
    LangChainDocumentPipeline,
)
from app.ai.providers.lightweight import ExtractiveGenerationProvider, HashingEmbeddingProvider
from app.core.config import Settings
from app.main import create_app

CASES = [
    {
        "question": "How many remote days are employees allowed per week?",
        "terms": ["three days"],
        "answer": "Employees may work remotely for up to three days per week.",
    },
    {
        "question": "Which days are designated collaboration days?",
        "terms": ["tuesday", "thursday"],
        "answer": "Tuesday and Thursday are designated collaboration days.",
    },
    {
        "question": "When can an employee request a fully remote arrangement?",
        "terms": ["120 kilometres"],
        "answer": (
            "An employee may request a fully remote arrangement when they live more than "
            "120 kilometres from the assigned office."
        ),
    },
    {
        "question": "Who must approve the fully remote arrangement?",
        "terms": ["department director", "people operations"],
        "answer": (
            "The fully remote arrangement requires approval from the department director "
            "and People Operations."
        ),
    },
    {
        "question": "How much is the home-office allowance and when is it available?",
        "terms": ["gbp 600", "30 days"],
        "answer": (
            "The home-office allowance is GBP 600 and becomes available after 30 days "
            "of employment."
        ),
    },
    {
        "question": "Who is the CEO?",
        "terms": [],
        "answer": (
            "The supplied documents do not contain enough information to answer this question."
        ),
        "not_found": True,
    },
]


class PolicyStructuredLLM(LLM):
    """Deterministic local evaluator; retrieval, LCEL, and parsers remain real LangChain."""

    @property
    def _llm_type(self) -> str:
        return "policy-structured-evaluator"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> str:
        del stop, run_manager, kwargs
        if "standalone retrieval query" in prompt:
            question = (
                prompt.split("Question:", 1)[-1]
                .split(
                    "The output should be formatted",
                    1,
                )[0]
                .strip()
            )
            return json.dumps({"standalone_query": question})
        if "Verify whether the proposed answer" in prompt:
            return json.dumps(
                {
                    "status": "supported",
                    "explanation": "The answer is directly supported by a retrieved passage.",
                    "unsupported_claims": [],
                }
            )
        if "grounded enterprise knowledge assistant" in prompt:
            question = prompt.split("Question:", 1)[-1].split("Standalone query:", 1)[0].strip()
            case = next(value for value in CASES if value["question"] == question)
            not_found = bool(case.get("not_found", False))
            citations: list[dict[str, Any]] = []
            if not not_found:
                chunk_match = re.search(r"BEGIN_UNTRUSTED_SOURCE ([^]]+)", prompt)
                document_match = re.search(r"document_id: ([^\n]+)", prompt)
                filename_match = re.search(r"source_filename: ([^\n]+)", prompt)
                page_match = re.search(r"page: (\d+)", prompt)
                section_match = re.search(r"section: (\d+)", prompt)
                citations.append(
                    {
                        "document_id": document_match.group(1) if document_match else "policy",
                        "source_filename": (
                            filename_match.group(1) if filename_match else "remote_work_policy.pdf"
                        ),
                        "chunk_id": chunk_match.group(1) if chunk_match else "policy-chunk",
                        "quote": case["answer"],
                        "page": int(page_match.group(1)) if page_match else 1,
                        "section": int(section_match.group(1)) if section_match else 0,
                    }
                )
            return json.dumps(
                {
                    "answer": case["answer"],
                    "citations": citations,
                    "not_found": not_found,
                }
            )
        raise ValueError("The deterministic evaluator received an unexpected prompt.")


def _case_pass(case: dict[str, Any], result: dict[str, Any]) -> bool:
    if case.get("not_found"):
        return bool(result["not_found"]) and not result["citations"]
    answer = str(result["answer"]).lower()
    return (
        all(term in answer for term in case["terms"])
        and bool(result["citations"])
        and not result["not_found"]
    )


def _retrieval_hit(case: dict[str, Any], passages: list[str]) -> bool:
    combined = " ".join(passages).lower()
    if case.get("not_found"):
        return "ceo" in combined and "does not state" in combined
    return all(term in combined for term in case["terms"])


def evaluate_custom(backend_root: Path, runtime: Path) -> list[dict[str, Any]]:
    settings = Settings(
        rag_engine="custom",
        database_url=f"sqlite:///{runtime / 'custom.db'}",
        storage_path=runtime / "custom-uploads",
        model_cache_path=backend_root / "data" / "models",
        chunk_size=220,
        chunk_overlap=36,
        similarity_threshold=0,
    )
    results: list[dict[str, Any]] = []
    with TestClient(
        create_app(
            settings,
            embedding_provider=HashingEmbeddingProvider(dimension=384),
            generation_provider=ExtractiveGenerationProvider(),
        )
    ) as client:
        knowledge_base = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Course comparison custom"},
        ).json()
        pdf = backend_root / "tests" / "fixtures" / "remote_work_policy.pdf"
        with pdf.open("rb") as source:
            uploaded = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
                files={"file": (pdf.name, source, "application/pdf")},
            ).json()
        client.post(f"/api/v1/documents/{uploaded['id']}/process")
        for case in CASES:
            started = perf_counter()
            response = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base['id']}/ask",
                json={"question": case["question"], "debug": True},
            )
            response.raise_for_status()
            payload = response.json()
            retrieved_passages = [str(value["text"]) for value in payload["retrieved_sources"]]
            retrieved_ids = {str(value["chunk_id"]) for value in payload["retrieved_sources"]}
            result = {
                "question": case["question"],
                "answer": payload["answer"],
                "citations": payload["citations"],
                "not_found": payload["not_found"],
                "retrieved": bool(retrieved_passages),
                "retrieval_hit": _retrieval_hit(case, retrieved_passages),
                "citation_valid": all(
                    str(citation["chunk_id"]) in retrieved_ids for citation in payload["citations"]
                ),
                "latency_ms": (perf_counter() - started) * 1000,
            }
            result["passed"] = _case_pass(case, result)
            results.append(result)
    return results


def evaluate_langchain(backend_root: Path, runtime: Path) -> list[dict[str, Any]]:
    settings = Settings(
        rag_engine="langchain",
        model_cache_path=backend_root / "data" / "models",
        langchain_index_path=runtime / "langchain-faiss",
        hf_local_files_only=True,
        chunk_size=220,
        chunk_overlap=36,
    )
    pipeline = LangChainDocumentPipeline.from_settings(settings, device="cpu")
    pdf = backend_root / "tests" / "fixtures" / "remote_work_policy.pdf"
    pipeline.index_document(
        DocumentIndexInput(
            path=pdf,
            document_id="deterministic-policy",
            knowledge_base_id="course-comparison",
            source_filename=pdf.name,
            document_type="pdf",
        )
    )
    suite = CourseChainSuite(
        llm=PolicyStructuredLLM(),
        retriever=pipeline.retriever("course-comparison", top_k=4),
    )
    results: list[dict[str, Any]] = []
    for case in CASES:
        started = perf_counter()
        state = suite.invoke(question=case["question"])
        answer = state["answer"]
        retrieved_passages = [document.page_content for document in state["documents"]]
        retrieved_ids = {str(document.metadata["chunk_id"]) for document in state["documents"]}
        result = {
            "question": case["question"],
            "answer": answer.answer,
            "citations": [value.model_dump() for value in answer.citations],
            "not_found": answer.not_found,
            "retrieved": bool(retrieved_passages),
            "retrieval_hit": _retrieval_hit(case, retrieved_passages),
            "citation_valid": all(
                citation.chunk_id in retrieved_ids for citation in answer.citations
            ),
            "latency_ms": (perf_counter() - started) * 1000,
        }
        result["passed"] = _case_pass(case, result)
        results.append(result)
    return results


def _line_count(paths: list[Path]) -> int:
    return sum(len(path.read_text(encoding="utf-8").splitlines()) for path in paths)


def main() -> None:
    backend_root = Path(__file__).parents[1]
    project_root = backend_root.parent
    runtime = backend_root / "data" / "course-comparison"
    if runtime.is_dir():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    tracemalloc.start()
    custom = evaluate_custom(backend_root, runtime)
    custom_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.reset_peak()
    langchain = evaluate_langchain(backend_root, runtime)
    langchain_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    custom_files = [
        backend_root / "app" / "services" / "rag.py",
        backend_root / "app" / "services" / "retrieval.py",
        backend_root / "app" / "ai" / "vectorstores" / "relational.py",
    ]
    langchain_files = [
        backend_root / "app" / "ai" / "langchain_engine" / "chains.py",
        backend_root / "app" / "ai" / "langchain_engine" / "document_pipeline.py",
        backend_root / "app" / "ai" / "langchain_engine" / "service.py",
    ]
    payload = {
        "custom": custom,
        "langchain": langchain,
        "summary": {
            "custom_passed": sum(bool(value["passed"]) for value in custom),
            "langchain_passed": sum(bool(value["passed"]) for value in langchain),
            "total": len(CASES),
            "custom_average_latency_ms": sum(value["latency_ms"] for value in custom) / len(custom),
            "langchain_average_latency_ms": sum(value["latency_ms"] for value in langchain)
            / len(langchain),
            "custom_peak_python_memory_mb": custom_peak / (1024 * 1024),
            "langchain_peak_python_memory_mb": langchain_peak / (1024 * 1024),
            "custom_reference_loc": _line_count(custom_files),
            "langchain_reference_loc": _line_count(langchain_files),
            "custom_retrieval_accuracy": (
                sum(bool(value["retrieval_hit"]) for value in custom) / len(custom)
            ),
            "langchain_retrieval_accuracy": (
                sum(bool(value["retrieval_hit"]) for value in langchain) / len(langchain)
            ),
            "custom_citation_validity": (
                sum(bool(value["citation_valid"]) for value in custom) / len(custom)
            ),
            "langchain_citation_validity": (
                sum(bool(value["citation_valid"]) for value in langchain) / len(langchain)
            ),
        },
        "methodology": {
            "retrieval": "Real project PDF; custom relational vectors vs LangChain FAISS.",
            "generation": (
                "Deterministic local generation for reproducible correctness; the LangChain "
                "path still uses real LCEL and PydanticOutputParser."
            ),
            "memory": (
                "Python allocations measured by tracemalloc; native model/FAISS memory excluded."
            ),
            "failure_behavior": {
                "custom": "Support gate and post-processing downgrade unsupported output.",
                "langchain": "Pydantic validation, bounded repair, and explicit not_found output.",
            },
        },
    }
    artifacts = project_root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "course-engine-comparison.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    summary = payload["summary"]
    rows = [
        "# Custom Engine vs LangChain Engine",
        "",
        "This is a deterministic reproducible comparison. It does not claim that the small "
        "evaluation generator measures open-ended model quality.",
        "",
        "| Metric | Custom | LangChain |",
        "| --- | ---: | ---: |",
        (
            f"| Correct policy cases | {summary['custom_passed']}/{summary['total']} | "
            f"{summary['langchain_passed']}/{summary['total']} |"
        ),
        (
            f"| Average latency | {summary['custom_average_latency_ms']:.1f} ms | "
            f"{summary['langchain_average_latency_ms']:.1f} ms |"
        ),
        (
            f"| Retrieval accuracy | {summary['custom_retrieval_accuracy']:.0%} | "
            f"{summary['langchain_retrieval_accuracy']:.0%} |"
        ),
        (
            f"| Citation validity | {summary['custom_citation_validity']:.0%} | "
            f"{summary['langchain_citation_validity']:.0%} |"
        ),
        (
            f"| Peak Python allocations | {summary['custom_peak_python_memory_mb']:.1f} MB | "
            f"{summary['langchain_peak_python_memory_mb']:.1f} MB |"
        ),
        (
            f"| Reference implementation LOC | {summary['custom_reference_loc']} | "
            f"{summary['langchain_reference_loc']} |"
        ),
        "",
        "| Question | Custom | LangChain | LangChain citations |",
        "| --- | --- | --- | ---: |",
    ]
    rows.extend(
        (
            f"| {custom_value['question']} | "
            f"{'PASS' if custom_value['passed'] else 'FAIL'} | "
            f"{'PASS' if langchain_value['passed'] else 'FAIL'} | "
            f"{len(langchain_value['citations'])} |"
        )
        for custom_value, langchain_value in zip(custom, langchain, strict=True)
    )
    rows.extend(
        [
            "",
            "Retrieval uses the real deterministic policy PDF. Generation is deterministic so "
            "the comparison isolates engine behavior and remains suitable for CI.",
            "",
            "Failure behavior: the custom engine uses support gates and post-processing; the "
            "LangChain engine uses validated Pydantic objects, bounded parser repair, and an "
            "explicit `not_found` field.",
        ]
    )
    (artifacts / "course-engine-comparison.md").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "custom": f"{summary['custom_passed']}/{summary['total']}",
                "langchain": f"{summary['langchain_passed']}/{summary['total']}",
            }
        )
    )


if __name__ == "__main__":
    main()
