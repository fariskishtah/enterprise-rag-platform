# Transcription

ffprobe validates that media contains audio/video streams and records duration/format.
ffmpeg extracts a mono 16 kHz PCM stream using a bounded, shell-free subprocess. Embedded
WebVTT subtitles are preferred. Public/YouTube adapters attempt official and generated
subtitles before legal public audio retrieval and local transcription.

faster-whisper loads lazily, caches under `backend/data/models/whisper`, detects language
unless forced, applies VAD, and persists start/end timestamps plus confidence derived
from segment log probability.

No-speech, invalid stream, unavailable model, timeout, and inaccessible public-source
errors have stable codes and retryable lifecycle records. Attempt temporary directories
are always removed.
