# Optional LoRA/PEFT experiment

This educational experiment is never run by the FastAPI application and never changes
the production model. It uses a tiny synthetic grounding dataset and a deliberately small
causal model so the complete mechanics are visible.

It demonstrates base-model loading, dataset preparation, tokenization, `LoraConfig`,
training, adapter saving, `PeftModel.from_pretrained`, and before/after inference.

For a GPU-backed Colab or Kaggle session:

```bash
pip install -e 'backend[course]'
python course_demo/fine_tuning/train_lora.py --epochs 1
```

`sshleifer/tiny-gpt2` is useful for mechanics, not answer quality. For meaningful
instruction tuning, choose a licensed instruction model, review its target module names,
use a CUDA runtime, and perform a proper train/evaluation split.

Expected output structure:

```text
output/
├── adapter/
│   ├── adapter_config.json
│   ├── adapter_model.safetensors
│   └── tokenizer files
├── trainer/
└── comparison.json
```
