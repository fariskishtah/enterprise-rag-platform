from __future__ import annotations

import hashlib
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar

import numpy as np

from app.ai.interfaces import EmbeddingProvider, GenerationProvider
from app.ai.quantization import QuantizationMode, resolve_quantization
from app.core.errors import ModelProviderError


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    _models: ClassVar[dict[tuple[str, str, str, bool], Any]] = {}
    _states: ClassVar[dict[tuple[str, str, str, bool], str]] = {}
    _query_cache: ClassVar[
        OrderedDict[tuple[tuple[str, str, str, bool], str], np.ndarray]
    ] = OrderedDict()
    _lock: ClassVar[Lock] = Lock()
    _query_cache_lock: ClassVar[Lock] = Lock()

    def __init__(
        self,
        *,
        model_name: str,
        cache_path: Path,
        device: str = "cpu",
        batch_size: int = 32,
        local_files_only: bool = False,
        query_cache_size: int = 128,
    ) -> None:
        self._model_name = model_name
        self.cache_path = cache_path
        self.device = device
        self.batch_size = batch_size
        self.local_files_only = local_files_only
        self.query_cache_size = query_cache_size

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        resolved_cache = str(self.cache_path.resolve())
        return any(
            key[0] == self._model_name
            and key[1] == resolved_cache
            and key[2] == self.device
            and key[3] == self.local_files_only
            for key in self._models
        )

    @property
    def load_status(self) -> str:
        key = self._cache_key()
        return "ready" if key in self._models else self._states.get(key, "cold")

    def _cache_key(self) -> tuple[str, str, str, bool]:
        return (
            self._model_name,
            str(self.cache_path.resolve()),
            self.device,
            self.local_files_only,
        )

    @property
    def _uses_e5_prefixes(self) -> bool:
        return self._model_name.lower().startswith("intfloat/multilingual-e5-")

    def _load_model(self) -> Any:
        key = self._cache_key()
        if key in self._models:
            return self._models[key]
        with self._lock:
            if key in self._models:
                return self._models[key]
            try:
                self._states[key] = "loading"
                from sentence_transformers import SentenceTransformer

                self.cache_path.mkdir(parents=True, exist_ok=True)
                model = SentenceTransformer(
                    self._model_name,
                    cache_folder=str(self.cache_path),
                    device=self.device,
                    local_files_only=self.local_files_only,
                )
            except Exception as exc:
                self._states[key] = "failed"
                raise ModelProviderError(
                    "The embedding model could not be loaded. Check the local model "
                    "configuration and available system memory."
                ) from exc
            self._models[key] = model
            self._states[key] = "ready"
            return model

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        try:
            prepared = [f"passage: {text}" for text in texts] if self._uses_e5_prefixes else texts
            values = self._load_model().encode(
                prepared,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError("Document embeddings could not be generated.") from exc
        return np.asarray(values, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        key = self._cache_key()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = (key, digest)
        if self.query_cache_size:
            with self._query_cache_lock:
                cached = self._query_cache.get(cache_key)
                if cached is not None:
                    self._query_cache.move_to_end(cache_key)
                    return cached.copy()
        prepared = f"query: {text}" if self._uses_e5_prefixes else text
        try:
            values = self._load_model().encode(
                [prepared],
                batch_size=1,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError("The query embedding could not be generated.") from exc
        result = np.asarray(values, dtype=np.float32)
        if result.shape[0] != 1:
            raise ModelProviderError("The query embedding could not be generated.")
        embedding = result[0]
        if self.query_cache_size:
            with self._query_cache_lock:
                self._query_cache[cache_key] = embedding.copy()
                self._query_cache.move_to_end(cache_key)
                while len(self._query_cache) > self.query_cache_size:
                    self._query_cache.popitem(last=False)
        return embedding


class HuggingFaceGenerationProvider(GenerationProvider):
    _models: ClassVar[dict[tuple[str, str, str, bool, str], tuple[Any, Any, Any, bool]]] = {}
    _states: ClassVar[dict[tuple[str, str, str, bool, str], str]] = {}
    _lock: ClassVar[Lock] = Lock()

    def __init__(
        self,
        *,
        model_name: str,
        cache_path: Path,
        device: str = "cpu",
        local_files_only: bool = False,
        fallback_model_name: str | None = None,
        quantization: QuantizationMode = "none",
        maximum_generation_seconds: float = 120.0,
    ) -> None:
        self._model_name = model_name
        self._active_model_name = model_name
        self.fallback_model_name = fallback_model_name
        self.cache_path = cache_path
        self.device = device
        self.local_files_only = local_files_only
        self.quantization = quantization
        self.maximum_generation_seconds = maximum_generation_seconds

    @property
    def model_name(self) -> str:
        return self._active_model_name

    @property
    def is_loaded(self) -> bool:
        resolved_cache = str(self.cache_path.resolve())
        configured_models = {self._model_name, self.fallback_model_name}
        return any(
            key[0] in configured_models
            and key[1] == resolved_cache
            and key[2] == self.device
            and key[3] == self.local_files_only
            and key[4] == self.quantization
            for key in self._models
        )

    @property
    def load_status(self) -> str:
        keys = [
            self._model_key(value)
            for value in (self._model_name, self.fallback_model_name)
            if value
        ]
        if any(key in self._models for key in keys):
            return "ready"
        if any(self._states.get(key) == "loading" for key in keys):
            return "loading"
        if keys and all(self._states.get(key) == "failed" for key in keys):
            return "failed"
        return "cold"

    def _model_key(self, model_name: str) -> tuple[str, str, str, bool, str]:
        return (
            model_name,
            str(self.cache_path.resolve()),
            self.device,
            self.local_files_only,
            self.quantization,
        )

    def _load_named_model(self, model_name: str) -> tuple[Any, Any, Any, bool]:
        key = self._model_key(model_name)
        if key in self._models:
            return self._models[key]
        with self._lock:
            if key in self._models:
                return self._models[key]
            try:
                self._states[key] = "loading"
                import torch
                from transformers import (
                    AutoConfig,
                    AutoModelForCausalLM,
                    AutoModelForSeq2SeqLM,
                    AutoTokenizer,
                )

                self.cache_path.mkdir(parents=True, exist_ok=True)
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    cache_dir=str(self.cache_path),
                    local_files_only=self.local_files_only,
                )
                config = AutoConfig.from_pretrained(
                    model_name,
                    cache_dir=str(self.cache_path),
                    local_files_only=self.local_files_only,
                )
                model_class = (
                    AutoModelForSeq2SeqLM if config.is_encoder_decoder else AutoModelForCausalLM
                )
                model_options: dict[str, Any] = {
                    "cache_dir": str(self.cache_path),
                    "local_files_only": self.local_files_only,
                }
                quantization_plan = resolve_quantization(
                    self.quantization,
                    device=self.device,
                )
                if quantization_plan.enabled:
                    model_options["quantization_config"] = quantization_plan.quantization_config
                    model_options["device_map"] = "auto"
                model = model_class.from_pretrained(model_name, **model_options)
                if "device_map" not in model_options:
                    model.to(self.device)
                model.eval()
            except Exception as exc:
                self._states[key] = "failed"
                raise ModelProviderError(
                    "The generation model could not be loaded. Check the local model "
                    "configuration and available system memory."
                ) from exc
            loaded = (tokenizer, model, torch, bool(config.is_encoder_decoder))
            self._models[key] = loaded
            self._states[key] = "ready"
            return loaded

    def _load_model(self) -> tuple[Any, Any, Any, bool]:
        try:
            loaded = self._load_named_model(self._model_name)
            self._active_model_name = self._model_name
            return loaded
        except ModelProviderError as preferred_error:
            if not self.fallback_model_name or self.fallback_model_name == self._model_name:
                raise
            try:
                loaded = self._load_named_model(self.fallback_model_name)
                self._active_model_name = f"{self.fallback_model_name} (fallback)"
                return loaded
            except ModelProviderError as fallback_error:
                raise preferred_error from fallback_error

    def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        top_k: int = 50,
        top_p: float = 0.9,
        repetition_penalty: float = 1.0,
        do_sample: bool | None = None,
    ) -> str:
        try:
            tokenizer, model, torch, is_encoder_decoder = self._load_model()
        except ModelProviderError:
            from app.ai.providers.lightweight import ExtractiveGenerationProvider

            self._active_model_name = "local-extractive-fallback"
            return ExtractiveGenerationProvider().generate(
                prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                do_sample=do_sample,
            )
        try:
            rendered_prompt = prompt
            if not is_encoder_decoder and hasattr(tokenizer, "apply_chat_template"):
                rendered_prompt = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
            inputs = tokenizer(
                rendered_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=4096 if not is_encoder_decoder else 1024,
            )
            inputs = {name: tensor.to(self.device) for name, tensor in inputs.items()}
            sampling_enabled = temperature > 0 if do_sample is None else do_sample
            generation_options: dict[str, Any] = {
                "max_new_tokens": max_new_tokens,
                "do_sample": sampling_enabled,
                "repetition_penalty": repetition_penalty,
                "max_time": self.maximum_generation_seconds,
            }
            if sampling_enabled:
                generation_options["temperature"] = temperature
                generation_options["top_k"] = top_k
                generation_options["top_p"] = top_p
            with torch.inference_mode():
                output = model.generate(**inputs, **generation_options)
            generated_tokens = (
                output[0] if is_encoder_decoder else output[0][inputs["input_ids"].shape[-1] :]
            )
            generated = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
        except Exception as exc:
            raise ModelProviderError(
                "The local generation model failed to produce a response."
            ) from exc
        if not generated:
            raise ModelProviderError("The local generation model returned an empty response.")
        return generated
