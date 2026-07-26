from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

QuantizationMode = Literal["none", "4bit", "8bit"]


@dataclass(frozen=True)
class QuantizationPlan:
    requested_mode: QuantizationMode
    effective_mode: QuantizationMode
    quantization_config: Any | None
    reason: str | None = None

    @property
    def enabled(self) -> bool:
        return self.quantization_config is not None


def resolve_quantization(
    mode: QuantizationMode,
    *,
    device: str,
) -> QuantizationPlan:
    """Build a real BitsAndBytesConfig when CUDA support is available.

    BitsAndBytes is intentionally optional on macOS. MPS and CPU requests fall back to
    unquantized loading instead of claiming that CUDA-only quantization is active.
    """

    if mode == "none":
        return QuantizationPlan(mode, "none", None)
    if not device.lower().startswith("cuda"):
        return QuantizationPlan(
            mode,
            "none",
            None,
            f"{mode} BitsAndBytes loading requires CUDA; device '{device}' uses fallback.",
        )
    try:
        import bitsandbytes  # noqa: F401
        import torch
        from transformers import BitsAndBytesConfig
    except (ImportError, ModuleNotFoundError) as exc:
        return QuantizationPlan(
            mode,
            "none",
            None,
            f"{mode} was requested but BitsAndBytes is unavailable: {exc}",
        )

    if mode == "4bit":
        config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    else:
        config = BitsAndBytesConfig(load_in_8bit=True)
    return QuantizationPlan(mode, mode, config)
