from app.ai.hardware import resolve_model_device


def test_explicit_model_device_is_preserved() -> None:
    assert resolve_model_device("CPU") == "cpu"
    assert resolve_model_device("mps") == "mps"


def test_auto_model_device_resolves_to_supported_runtime() -> None:
    assert resolve_model_device("auto") in {"cpu", "cuda", "mps"}
