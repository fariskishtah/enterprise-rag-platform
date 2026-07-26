from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_model_bundle(model: Any, tokenizer: Any, output_dir: Path) -> Path:
    """Save model and tokenizer files using the Hugging Face pretrained format."""

    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(destination)
    tokenizer.save_pretrained(destination)
    manifest = {
        "format": "huggingface_pretrained",
        "model_class": type(model).__name__,
        "tokenizer_class": type(tokenizer).__name__,
        "reload": "from_pretrained(local_directory, local_files_only=True)",
        "quantization_note": (
            "Adapter or dequantized saving may be required for BitsAndBytes models; "
            "verify the selected model's save_pretrained support."
        ),
    }
    (destination / "enterprise_rag_model_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return destination


def reload_model_bundle(
    model_dir: Path,
    *,
    local_files_only: bool = True,
    device: str = "cpu",
) -> tuple[Any, Any]:
    """Reload a saved causal or sequence-to-sequence model without network access."""

    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
    )

    source = model_dir.resolve()
    config = AutoConfig.from_pretrained(source, local_files_only=local_files_only)
    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=local_files_only)
    model_class = AutoModelForSeq2SeqLM if config.is_encoder_decoder else AutoModelForCausalLM
    model = model_class.from_pretrained(source, local_files_only=local_files_only)
    model.to(device)
    model.eval()
    return model, tokenizer
