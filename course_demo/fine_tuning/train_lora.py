from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


def generate(model: object, tokenizer: object, prompt: str, device: str) -> str:
    encoded = tokenizer(prompt, return_tensors="pt").to(device)
    output = model.generate(**encoded, max_new_tokens=48, do_sample=False)
    return tokenizer.decode(output[0], skip_special_tokens=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optional tiny LoRA course experiment."
    )
    parser.add_argument("--model", default="sshleifer/tiny-gpt2")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument(
        "--output", type=Path, default=Path("course_demo/fine_tuning/output")
    )
    args = parser.parse_args()

    dataset_path = Path(__file__).with_name("synthetic_rag_training.jsonl")
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.pad_token = tokenizer.eos_token
    base_model = AutoModelForCausalLM.from_pretrained(args.model)
    prompt = "Question: How should an answer use enterprise evidence?\nAnswer:"
    before = generate(base_model, tokenizer, prompt, "cpu")

    def tokenize(batch: dict[str, list[str]]) -> dict[str, object]:
        texts = [
            f"Question: {question}\nAnswer: {answer}{tokenizer.eos_token}"
            for question, answer in zip(batch["question"], batch["answer"], strict=True)
        ]
        return tokenizer(texts, truncation=True, padding="max_length", max_length=160)

    tokenized = dataset.map(tokenize, batched=True, remove_columns=dataset.column_names)
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["c_attn"],
    )
    model = get_peft_model(base_model, lora)
    training_args = TrainingArguments(
        output_dir=str(args.output / "trainer"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        use_cpu=True,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    trainer.train()

    adapter_dir = args.output / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    reloaded_base = AutoModelForCausalLM.from_pretrained(args.model)
    reloaded = PeftModel.from_pretrained(reloaded_base, adapter_dir)
    after = generate(reloaded, tokenizer, prompt, "cpu")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "comparison.json").write_text(
        json.dumps({"prompt": prompt, "before": before, "after": after}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
