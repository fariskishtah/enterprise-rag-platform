import json
import os
from pathlib import Path
from time import perf_counter

import pytest

from app.media.transcription import FasterWhisperTranscriptionProvider


@pytest.mark.real_transcription
@pytest.mark.skipif(
    os.getenv("RUN_REAL_TRANSCRIPTION_TESTS") != "1",
    reason="Set RUN_REAL_TRANSCRIPTION_TESTS=1 to run faster-whisper locally.",
)
def test_real_faster_whisper_transcribes_local_speech_fixture() -> None:
    backend_root = Path(__file__).parents[1]
    project_root = backend_root.parent
    audio = project_root / "artifacts" / "whisper-speech.wav"
    assert audio.is_file(), "The local speech fixture is missing."
    provider = FasterWhisperTranscriptionProvider(
        model_name="tiny",
        cache_path=backend_root / "data" / "models" / "whisper",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
    )

    started = perf_counter()
    result = provider.transcribe(audio, language="en")
    elapsed = perf_counter() - started

    assert result.segments
    assert "atlas" in " ".join(value.text.lower() for value in result.segments)
    assert result.language == "en"
    artifact = {
        "model": provider.model_name,
        "language": result.language,
        "segments": [
            {
                "start": value.start,
                "end": value.end,
                "text": value.text,
                "confidence": value.confidence,
            }
            for value in result.segments
        ],
        "elapsed_seconds": round(elapsed, 3),
    }
    (project_root / "artifacts" / "real-transcription-result.json").write_text(
        json.dumps(artifact, indent=2),
        encoding="utf-8",
    )
