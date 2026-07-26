from __future__ import annotations

import logging
from threading import Lock
from typing import Any

from app.ai.interfaces import GenerationProvider
from app.ai.langchain_engine.document_pipeline import LangChainDocumentPipeline
from app.ai.langchain_engine.llm import (
    EnterpriseGenerationLLM,
    create_langchain_huggingface_pipeline,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)


class LangChainEngineRuntime:
    """Lazy runtime resources used only when the course engine is selected."""

    def __init__(
        self,
        *,
        settings: Settings,
        generation_provider: GenerationProvider,
        device: str,
    ) -> None:
        self.settings = settings
        self.generation_provider = generation_provider
        self.device = device
        self._document_pipeline: LangChainDocumentPipeline | None = None
        self._llm: Any | None = None
        self._llm_backend = "not_loaded"
        self._llm_fallback_reason: str | None = None
        self._lock = Lock()

    @property
    def document_pipeline(self) -> LangChainDocumentPipeline:
        if self._document_pipeline is None:
            with self._lock:
                if self._document_pipeline is None:
                    self._document_pipeline = LangChainDocumentPipeline.from_settings(
                        self.settings,
                        device=self.device,
                    )
        return self._document_pipeline

    @property
    def llm(self) -> Any:
        if self._llm is None:
            with self._lock:
                if self._llm is None:
                    # In low-memory mode (or when explicitly configured), use
                    # the EnterpriseGenerationLLM wrapper which reuses the
                    # existing generation_provider instead of loading a
                    # completely separate HuggingFace pipeline.
                    if self.settings.langchain_force_wrapper:
                        self._llm = EnterpriseGenerationLLM.from_settings(
                            self.generation_provider,
                            self.settings,
                        )
                        self._llm_backend = "custom_provider_langchain_wrapper"
                        self._llm_fallback_reason = (
                            "Using shared generation provider (langchain_force_wrapper=True)"
                        )
                        logger.info(
                            "LangChain runtime: using shared generation provider "
                            "(avoids loading duplicate model)"
                        )
                    else:
                        try:
                            self._llm = create_langchain_huggingface_pipeline(
                                self.settings,
                                device=self.device,
                            )
                            self._llm_backend = "langchain_huggingface_pipeline"
                        except Exception as exc:
                            self._llm = EnterpriseGenerationLLM.from_settings(
                                self.generation_provider,
                                self.settings,
                            )
                            self._llm_backend = "custom_provider_langchain_wrapper"
                            self._llm_fallback_reason = (
                                f"HuggingFacePipeline could not initialize: {type(exc).__name__}"
                            )
        return self._llm

    @property
    def llm_backend(self) -> str:
        return self._llm_backend

    @property
    def llm_fallback_reason(self) -> str | None:
        return self._llm_fallback_reason
