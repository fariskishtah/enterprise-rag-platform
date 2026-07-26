"""Measure the configured Qwen model under legacy and AWS CPU generation bounds."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import torch

from app.ai.providers.huggingface import HuggingFaceGenerationProvider


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
    parser.add_argument("--profile", choices=("legacy", "aws_cpu"), required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    args = parser.parse_args()

    aws_cpu = args.profile == "aws_cpu"
    if aws_cpu:
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
    provider = HuggingFaceGenerationProvider(
        model_name="Qwen/Qwen2.5-0.5B-Instruct",
        cache_path=args.cache,
        device="cpu",
        local_files_only=True,
        maximum_generation_seconds=60,
    )
    cases = [
        ("cold_english", "Answer briefly: How many days are in one week?"),
        ("warm_english", "Answer in English: What is the capital of Egypt?"),
        ("warm_arabic", "أجب بالعربية بإيجاز: ما عاصمة مصر؟"),
        (
            "short_summary",
            "Summarize in one sentence: The policy permits three remote-work days each week.",
        ),
    ]
    results = []
    for name, prompt in cases:
        started = time.perf_counter()
        output = provider.generate(
            prompt,
            temperature=0.0 if aws_cpu else 0.1,
            max_new_tokens=args.max_new_tokens,
            top_k=50,
            top_p=0.9,
            repetition_penalty=1.05,
            do_sample=not aws_cpu,
        )
        results.append(
            {
                "case": name,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "output_characters": len(output),
            }
        )

    model_cache = args.cache / "models--Qwen--Qwen2.5-0.5B-Instruct"
    print(
        json.dumps(
            {
                "profile": args.profile,
                "model": provider.model_name,
                "max_new_tokens": args.max_new_tokens,
                "peak_rss_mb": round(_peak_rss_mb(), 1),
                "model_cache_mb": round(_directory_size_mb(model_cache), 1),
                "cases": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
