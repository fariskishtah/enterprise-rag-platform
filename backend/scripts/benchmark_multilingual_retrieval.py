"""Benchmark a configured embedding model on a small Arabic/English fixture."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

from app.ai.providers.huggingface import HuggingFaceEmbeddingProvider

PASSAGES = [
    (
        "remote-en",
        "Employees may work remotely for three days each week with manager approval.",
    ),
    ("remote-ar", "يمكن للموظفين العمل عن بُعد ثلاثة أيام كل أسبوع بموافقة المدير."),
    ("leave-en", "Employees receive twenty paid vacation days per calendar year."),
    ("security-ar", "يجب تغيير كلمة المرور كل تسعين يوماً لحماية حسابات الشركة."),
]
QUERIES = [
    ("arabic_to_arabic", "كم يوماً يمكن للموظف العمل عن بُعد؟", "remote-ar"),
    ("arabic_to_english", "كم عدد أيام الإجازة المدفوعة؟", "leave-en"),
    ("english_to_arabic", "How often must the password be changed?", "security-ar"),
]


def _peak_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


def _directory_size_mb(path: Path) -> float:
    seen: set[tuple[int, int]] = set()
    total = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        stat = item.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity not in seen:
            seen.add(identity)
            total += stat.st_size
    return total / 1_000_000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()

    provider = HuggingFaceEmbeddingProvider(
        model_name=args.model,
        cache_path=args.cache,
        device="cpu",
        batch_size=8,
        query_cache_size=0,
    )
    started = time.perf_counter()
    passage_embeddings = provider.embed_documents([text for _, text in PASSAGES])
    cold_load_and_passage_seconds = time.perf_counter() - started

    query_results = []
    hits = 0
    query_latencies = []
    for name, query, expected in QUERIES:
        started = time.perf_counter()
        query_embedding = provider.embed_query(query)
        latency_ms = (time.perf_counter() - started) * 1000
        query_latencies.append(latency_ms)
        scores = passage_embeddings @ query_embedding
        order = np.argsort(scores)[::-1]
        top_id = PASSAGES[int(order[0])][0]
        hits += int(top_id == expected)
        query_results.append(
            {
                "case": name,
                "expected": expected,
                "top_result": top_id,
                "top_score": round(float(scores[order[0]]), 4),
                "expected_rank": int(
                    np.where(
                        order
                        == next(
                            index for index, value in enumerate(PASSAGES) if value[0] == expected
                        )
                    )[0][0]
                )
                + 1,
                "latency_ms": round(latency_ms, 2),
            }
        )

    model_cache = args.cache / f"models--{args.model.replace('/', '--')}"
    print(
        json.dumps(
            {
                "model": args.model,
                "cold_load_and_passage_seconds": round(cold_load_and_passage_seconds, 3),
                "mean_query_latency_ms": round(float(np.mean(query_latencies)), 2),
                "top_1_accuracy": round(hits / len(QUERIES), 3),
                "peak_rss_mb": round(_peak_rss_mb(), 1),
                "model_cache_mb": round(_directory_size_mb(model_cache), 1),
                "cases": query_results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
