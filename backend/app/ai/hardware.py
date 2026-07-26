"""Hardware selection for local embedding and generation models."""


def resolve_model_device(configured_device: str) -> str:
    requested = configured_device.strip().lower()
    if requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except (ImportError, AttributeError):
        pass
    return "cpu"
