"""Benchmark a faster-whisper model using an existing local media fixture."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

from app.media.transcription import FasterWhisperTranscriptionProvider


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
    parser.add_argument("--model", choices=("tiny", "base", "small"), required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--language", choices=("auto", "ar", "en"), default="auto")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()

    provider = FasterWhisperTranscriptionProvider(
        model_name=args.model,
        cache_path=args.cache,
        device="cpu",
        compute_type="int8",
        cpu_threads=args.threads,
        num_workers=1,
        beam_size=3,
    )
    started = time.perf_counter()
    result = provider.transcribe(args.media, language=args.language)
    elapsed = time.perf_counter() - started
    model_cache = args.cache / f"models--Systran--faster-whisper-{args.model}"
    print(
        json.dumps(
            {
                "model": args.model,
                "language": result.language,
                "elapsed_seconds": round(elapsed, 3),
                "peak_rss_mb": round(_peak_rss_mb(), 1),
                "model_cache_mb": round(_directory_size_mb(model_cache), 1),
                "segments": len(result.segments),
                "transcript": " ".join(segment.text for segment in result.segments),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
