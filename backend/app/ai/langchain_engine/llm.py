from __future__ import annotations

from typing import Any

from langchain_core.language_models.llms import LLM
from langchain_huggingface import HuggingFacePipeline
from pydantic import ConfigDict, Field

from app.ai.interfaces import GenerationProvider
from app.ai.quantization import QuantizationMode, resolve_quantization
from app.core.config import Settings


class EnterpriseGenerationLLM(LLM):
    """LangChain LLM adapter around EnterpriseRAG's existing generation provider."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: Any = Field(exclude=True)
    model_name: str
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    top_k: int = Field(default=50, ge=0, le=1000)
    top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    max_new_tokens: int = Field(default=256, ge=1, le=4096)
    repetition_penalty: float = Field(default=1.0, ge=1.0, le=5.0)
    do_sample: bool = True
    device: str = "cpu"
    quantization_mode: QuantizationMode = "none"

    @property
    def _llm_type(self) -> str:
        return "enterprise-rag-generation-provider"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "max_new_tokens": self.max_new_tokens,
            "repetition_penalty": self.repetition_penalty,
            "do_sample": self.do_sample,
            "device": self.device,
            "quantization_mode": self.quantization_mode,
        }

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> str:
        del run_manager
        provider: GenerationProvider = self.provider
        generated = provider.generate(
            prompt,
            temperature=float(kwargs.get("temperature", self.temperature)),
            top_k=int(kwargs.get("top_k", self.top_k)),
            top_p=float(kwargs.get("top_p", self.top_p)),
            max_new_tokens=int(kwargs.get("max_new_tokens", self.max_new_tokens)),
            repetition_penalty=float(kwargs.get("repetition_penalty", self.repetition_penalty)),
            do_sample=bool(kwargs.get("do_sample", self.do_sample)),
        )
        if stop:
            stop_positions = [generated.find(value) for value in stop if value in generated]
            if stop_positions:
                generated = generated[: min(stop_positions)]
        return generated

    @classmethod
    def from_settings(
        cls,
        provider: GenerationProvider,
        settings: Settings,
    ) -> EnterpriseGenerationLLM:
        return cls(
            provider=provider,
            model_name=provider.model_name,
            temperature=settings.generation_temperature,
            top_k=settings.generation_top_k,
            top_p=settings.generation_top_p,
            max_new_tokens=settings.generation_max_new_tokens,
            repetition_penalty=settings.generation_repetition_penalty,
            do_sample=settings.generation_do_sample,
            device=str(getattr(provider, "device", settings.model_device)),
            quantization_mode=settings.generation_quantization,
        )


def _pipeline_device(device: str) -> int | str:
    normalized = device.lower()
    if normalized.startswith("cuda"):
        if ":" in normalized:
            return int(normalized.split(":", 1)[1])
        return 0
    if normalized == "cpu":
        return -1
    return normalized


def create_text_generation_pipeline(
    *,
    model_name: str,
    cache_path: str,
    device: str,
    local_files_only: bool,
    quantization: QuantizationMode,
) -> Any:
    """Create a direct ``transformers.pipeline`` for local text generation."""

    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        pipeline,
    )

    config = AutoConfig.from_pretrained(
        model_name,
        cache_dir=cache_path,
        local_files_only=local_files_only,
    )
    task = "text2text-generation" if config.is_encoder_decoder else "text-generation"
    model_kwargs: dict[str, Any] = {
        "cache_dir": cache_path,
        "local_files_only": local_files_only,
    }
    plan = resolve_quantization(quantization, device=device)
    if plan.enabled:
        model_kwargs["quantization_config"] = plan.quantization_config
        model_kwargs["device_map"] = "auto"
    model_class = AutoModelForSeq2SeqLM if config.is_encoder_decoder else AutoModelForCausalLM
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_path,
        local_files_only=local_files_only,
    )
    model = model_class.from_pretrained(model_name, **model_kwargs)
    arguments: dict[str, Any] = {}
    if not plan.enabled:
        arguments["device"] = _pipeline_device(device)
    return pipeline(
        task,
        model=model,
        tokenizer=tokenizer,
        **arguments,
    )


def create_summarization_pipeline(
    *,
    model_name: str,
    cache_path: str,
    device: str,
    local_files_only: bool,
) -> Any:
    """Create a direct Hugging Face ``pipeline('summarization')``."""

    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_path,
        local_files_only=local_files_only,
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        cache_dir=cache_path,
        local_files_only=local_files_only,
    )

    return pipeline(
        "summarization",
        model=model,
        tokenizer=tokenizer,
        device=_pipeline_device(device),
    )


def create_langchain_huggingface_pipeline(
    settings: Settings,
    *,
    device: str,
) -> HuggingFacePipeline:
    """Wrap the direct Transformers pipeline with LangChain HuggingFacePipeline."""

    generator = create_text_generation_pipeline(
        model_name=settings.generation_model_name,
        cache_path=str(settings.model_cache_path),
        device=device,
        local_files_only=settings.hf_local_files_only,
        quantization=settings.generation_quantization,
    )
    pipeline_kwargs: dict[str, Any] = {
        "max_new_tokens": settings.generation_max_new_tokens,
        "repetition_penalty": settings.generation_repetition_penalty,
        "do_sample": settings.generation_do_sample,
    }
    if settings.generation_do_sample:
        pipeline_kwargs.update(
            {
                "temperature": settings.generation_temperature,
                "top_k": settings.generation_top_k,
                "top_p": settings.generation_top_p,
            }
        )
    if getattr(generator, "task", None) == "text-generation":
        pipeline_kwargs["return_full_text"] = False
    return HuggingFacePipeline(
        pipeline=generator,
        pipeline_kwargs=pipeline_kwargs,
    )
