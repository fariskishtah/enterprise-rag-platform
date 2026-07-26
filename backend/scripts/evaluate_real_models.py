"""Evaluate the cached production embedding and generation models end to end."""

import json
import platform
import shutil
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

CASES = [
    {
        "question": "How many remote days are employees allowed per week?",
        "required_terms": ["three days"],
    },
    {
        "question": "How much is the home-office allowance and when is it available?",
        "required_terms": ["600", "30 days"],
    },
    {
        "question": "Who is the CEO?",
        "required_terms": [],
        "not_found": True,
    },
]


def main() -> None:
    backend_root = Path(__file__).parents[1]
    project_root = backend_root.parent
    artifacts = project_root / "artifacts"
    runtime = backend_root / "data" / "real-model-evaluation"
    if runtime.is_dir():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        database_url=f"sqlite:///{runtime / 'evaluation.db'}",
        storage_path=runtime / "uploads",
        model_cache_path=backend_root / "data" / "models",
        hf_local_files_only=True,
        chunk_size=220,
        chunk_overlap=36,
        similarity_threshold=0,
        generation_temperature=0,
        generation_do_sample=False,
        generation_max_new_tokens=96,
    )
    results: list[dict[str, object]] = []
    application = create_app(settings)
    with TestClient(application) as client:
        knowledge_base = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Real Model Policy Evaluation"},
        ).json()
        pdf = backend_root / "tests" / "fixtures" / "remote_work_policy.pdf"
        with pdf.open("rb") as input_file:
            uploaded = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
                files={"file": (pdf.name, input_file, "application/pdf")},
            ).json()
        processing_started = perf_counter()
        processed = client.post(f"/api/v1/documents/{uploaded['id']}/process")
        document_processing_ms = (perf_counter() - processing_started) * 1000
        if processed.status_code != 202:
            raise RuntimeError(processed.text)

        for case in CASES:
            response = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base['id']}/ask",
                json={"question": case["question"], "debug": True},
            )
            if response.status_code != 200:
                raise RuntimeError(response.text)
            answer = response.json()
            normalized = answer["answer"].lower()
            expected_not_found = bool(case.get("not_found", False))
            required_terms = [str(value).lower() for value in case["required_terms"]]
            passed = (
                answer["not_found"]
                if expected_not_found
                else not answer["not_found"]
                and all(term in normalized for term in required_terms)
                and bool(answer["citations"])
            )
            results.append(
                {
                    "question": case["question"],
                    "required_terms": required_terms,
                    "answer": answer["answer"],
                    "not_found": answer["not_found"],
                    "support_status": answer["support_status"],
                    "confidence": answer["confidence"],
                    "citations": answer["citations"],
                    "generation_model": answer["generation_model"],
                    "embedding_model": answer["debug"]["embedding_model"],
                    "timings_ms": answer["debug"]["timings_ms"],
                    "pass": passed,
                }
            )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "generation_model": settings.generation_model_name,
        "embedding_model": settings.embedding_model_name,
        "model_device": str(application.state.model_device),
        "cold_models_loaded_from_local_cache": True,
        "document_processing_and_first_embedding_ms": round(document_processing_ms, 3),
        "passed": sum(bool(value["pass"]) for value in results),
        "total": len(results),
        "cases": results,
    }
    (artifacts / "real-model-evaluation.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    rows = [
        "# Real local model evaluation",
        "",
        f"Result: {payload['passed']}/{payload['total']} passed",
        "",
        f"- Generation: `{payload['generation_model']}`",
        f"- Embeddings: `{payload['embedding_model']}`",
        f"- Device: `{payload['model_device']}`",
        "- Model weights: local cache only",
        (
            "- Document processing + first embedding load: "
            f"{payload['document_processing_and_first_embedding_ms']:.1f} ms"
        ),
        "",
        "| Question | Answer | Support | Pass | Total latency |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows.extend(
        "| {question} | {answer} | {support_status} | {pass_value} | {latency:.1f} ms |".format(
            **value,
            pass_value="PASS" if value["pass"] else "FAIL",
            latency=value["timings_ms"]["total"],
        )
        for value in results
    )
    (artifacts / "real-model-evaluation.md").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": payload["passed"], "total": payload["total"]}))


if __name__ == "__main__":
    main()
