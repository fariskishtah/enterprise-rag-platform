from pathlib import Path

from app.ai.providers.huggingface import HuggingFaceGenerationProvider
from app.core.errors import ModelProviderError


def generation_provider(tmp_path: Path) -> HuggingFaceGenerationProvider:
    return HuggingFaceGenerationProvider(
        model_name="preferred/model",
        fallback_model_name="fallback/model",
        cache_path=tmp_path,
        local_files_only=True,
    )


def test_generation_model_load_uses_configured_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = generation_provider(tmp_path)
    sentinel = (object(), object(), object(), False)
    attempts: list[str] = []

    def load_named_model(model_name: str):
        attempts.append(model_name)
        if model_name == "preferred/model":
            raise ModelProviderError("preferred unavailable")
        return sentinel

    monkeypatch.setattr(provider, "_load_named_model", load_named_model)

    assert provider._load_model() is sentinel
    assert attempts == ["preferred/model", "fallback/model"]
    assert provider.model_name == "fallback/model (fallback)"


def test_generation_model_load_degrades_to_local_extraction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider = generation_provider(tmp_path)

    def fail_load(_: str):
        raise ModelProviderError("model unavailable")

    monkeypatch.setattr(provider, "_load_named_model", fail_load)
    answer = provider.generate(
        """
User question: What is the review interval?
[BEGIN_UNTRUSTED_SOURCE chunk-1]
Document: policy.txt
Location: paragraph 1
The review interval is thirty days.
[END_UNTRUSTED_SOURCE]
Grounded answer:
""".strip(),
        temperature=0,
        max_new_tokens=64,
    )

    assert "review interval is thirty days" in answer
    assert "[SOURCE:chunk-1]" in answer
    assert provider.model_name == "local-extractive-fallback"
