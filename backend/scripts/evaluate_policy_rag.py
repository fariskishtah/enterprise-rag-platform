"""Run the policy PDF through the real FastAPI surface and write evaluation artifacts."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai.providers.lightweight import (
    ExtractiveGenerationProvider,
    HashingEmbeddingProvider,
)
from app.core.config import Settings
from app.main import create_app

CASES = [
    (
        "How many remote days are employees allowed per week?",
        "Up to three days per week.",
    ),
    (
        "Which days are designated collaboration days?",
        "Tuesday and Thursday.",
    ),
    (
        "When can an employee request a fully remote arrangement?",
        "More than 120 kilometres from the assigned office, with approval.",
    ),
    (
        "Who must approve the fully remote arrangement?",
        "The department director and People Operations.",
    ),
    (
        "How much is the home-office allowance and when is it available?",
        "GBP 600 after 30 days of employment.",
    ),
    ("Who is the CEO?", "Not found."),
]


def main() -> None:
    backend_root = Path(__file__).parents[1]
    project_root = backend_root.parent
    artifacts = project_root / "artifacts"
    runtime = backend_root / "data" / "evaluation"
    artifacts.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    database = runtime / "policy-evaluation.db"
    database.unlink(missing_ok=True)
    settings = Settings(
        database_url=f"sqlite:///{database}",
        storage_path=runtime / "uploads",
        model_cache_path=backend_root / "data" / "models",
        chunk_size=220,
        chunk_overlap=36,
        similarity_threshold=0,
    )
    evaluations: list[dict[str, object]] = []
    with TestClient(
        create_app(
            settings,
            embedding_provider=HashingEmbeddingProvider(dimension=384),
            generation_provider=ExtractiveGenerationProvider(),
        )
    ) as client:
        knowledge_base = client.post(
            "/api/v1/knowledge-bases", json={"name": "Policy Evaluation"}
        ).json()
        pdf = backend_root / "tests" / "fixtures" / "remote_work_policy.pdf"
        with pdf.open("rb") as input_file:
            uploaded = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base['id']}/documents",
                files={"file": (pdf.name, input_file, "application/pdf")},
            ).json()
        client.post(f"/api/v1/documents/{uploaded['id']}/process")
        extraction = client.get(f"/api/v1/documents/{uploaded['id']}/extraction").json()
        chunks = client.get(f"/api/v1/documents/{uploaded['id']}/chunks").json()
        for question, expected in CASES:
            started = datetime.now(UTC)
            result = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base['id']}/ask",
                json={"question": question, "debug": True},
            ).json()
            evaluations.append(
                {
                    "question": question,
                    "expected": expected,
                    "generated_answer": result["answer"],
                    "retrieved_passages": result["retrieved_sources"],
                    "citations": result["citations"],
                    "support_status": result["support_status"],
                    "not_found": result["not_found"],
                    "pass": (
                        result["not_found"]
                        if expected == "Not found."
                        else bool(result["citations"]) and not result["not_found"]
                    ),
                    "latency_ms": result["response_time_ms"],
                    "started_at": started.isoformat(),
                }
            )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "document": {
            "id": uploaded["id"],
            "extracted_characters": extraction["character_count"],
            "page_count": extraction["page_count"],
            "chunks": chunks["total"],
        },
        "cases": evaluations,
        "passed": sum(bool(value["pass"]) for value in evaluations),
        "total": len(evaluations),
    }
    (artifacts / "policy-rag-evaluation.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    rows = [
        "# EnterpriseRAG policy evaluation",
        "",
        f"Result: {payload['passed']}/{payload['total']} passed",
        "",
        "| Question | Expected | Generated | Support | Pass | Latency |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows.extend(
        "| {question} | {expected} | {generated_answer} | {support_status} | "
        "{pass_value} | {latency_ms:.1f} ms |".format(
            **value,
            pass_value="PASS" if value["pass"] else "FAIL",
        )
        for value in evaluations
    )
    (artifacts / "policy-rag-evaluation.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"passed": payload["passed"], "total": payload["total"]}))


if __name__ == "__main__":
    main()
