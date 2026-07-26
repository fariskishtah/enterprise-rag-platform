from __future__ import annotations

from threading import Lock

from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.core.config import Settings


class ModelWarmupController:
    """Tracks one non-blocking, process-local model warm-up operation."""

    def __init__(self) -> None:
        self._status = "cold"
        self._lock = Lock()

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    def begin(self) -> bool:
        with self._lock:
            if self._status in {"loading", "ready"}:
                return False
            self._status = "loading"
            return True

    def run(
        self,
        embedding_provider: EmbeddingProvider,
        generation_provider: GenerationProvider,
        settings: Settings,
    ) -> None:
        try:
            embedding_provider.embed_query("EnterpriseRAG model warm-up")
            if settings.warm_generation_model_on_startup:
                generation_provider.generate(
                    "Reply with OK.",
                    temperature=0.0,
                    max_new_tokens=8,
                    top_k=1,
                    top_p=1.0,
                    repetition_penalty=1.0,
                    do_sample=False,
                )
        except Exception:
            with self._lock:
                self._status = "failed"
            return
        with self._lock:
            self._status = "ready"
