"""Validate course notebook JSON, required teaching sections, and Python syntax."""

from __future__ import annotations

import ast
import json
from pathlib import Path


def _python_source(lines: list[str]) -> str:
    values = list(lines)
    if values and values[0].lstrip().startswith("%%"):
        values = values[1:]
    return "".join(line for line in values if not line.lstrip().startswith(("%", "!")))


def main() -> None:
    project_root = Path(__file__).parents[2]
    notebooks = sorted((project_root / "course_demo").rglob("*.ipynb"))
    expected = {
        "huggingface_pipeline_demo.ipynb",
        "langchain_rag_demo.ipynb",
        "langchain_chains_and_parser.ipynb",
        "quantization_bitsandbytes.ipynb",
        "model_save_reload.ipynb",
        "lora_fine_tuning.ipynb",
        "streamlit_ngrok_demo.ipynb",
    }
    names = {path.name for path in notebooks}
    if names != expected:
        raise RuntimeError(f"Notebook set mismatch: expected {expected}, found {names}")

    for path in notebooks:
        notebook = json.loads(path.read_text(encoding="utf-8"))
        if notebook.get("nbformat") != 4:
            raise ValueError(f"{path} must use notebook format 4.")
        combined = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
        ).lower()
        for required in ("pip install", "expected output", "except "):
            if required not in combined:
                raise ValueError(f"{path} is missing required content: {required}")
        if "ngrok_authtoken='" in combined or 'ngrok_authtoken="' in combined:
            raise ValueError(f"{path} appears to contain a hardcoded ngrok token.")
        for index, cell in enumerate(notebook.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            source = _python_source(cell.get("source", []))
            if source.strip():
                ast.parse(source, filename=f"{path}:cell-{index}")
    print(f"Validated {len(notebooks)} course notebooks.")


if __name__ == "__main__":
    main()
