# Model selection

The previous generator, `google/flan-t5-small`, was CPU-friendly but frequently copied
irrelevant chunks and had weak instruction following. The new preferred generator is
`Qwen/Qwen2.5-0.5B-Instruct`: still compact, but materially better at direct instructions,
short factual answers, and chat formatting.

`google/flan-t5-base` is the configured Hugging Face fallback. If neither model can load,
the application falls back to a deterministic local extractive generator and reports
that active model in answer metadata. This keeps local/offline deployments usable.

`ENTERPRISE_RAG_MODEL_DEVICE=auto` selects CUDA, then Apple MPS, then CPU. On the local
Apple Silicon validation machine, the same grounded Qwen cases improved from 14.5–29.6
seconds on CPU to 1.0–4.6 seconds on MPS. Explicit `cpu`, `mps`, and `cuda` values remain
available for controlled deployments. Int8 generation is only activated for compatible
CUDA execution.

MiniLM remains the embedding default. Retrieval quality now depends less on a single
embedding because lexical scoring and direct-relevance reranking protect exact names,
numbers, dates, approvals, and policy language.

faster-whisper Small with CPU int8 is the transcription default. Set the device,
compute type, language, thread count, and model through `ENTERPRISE_RAG_` variables.
Tiny is suitable for fast smoke tests; Small is recommended for product use.

## Generation APIs

- The custom engine calls tokenizer/model APIs and `model.generate()` directly. It gives
  the product precise control over device placement, token slicing, fallback behavior, and
  error translation.
- `transformers.pipeline()` packages tokenization, model execution, decoding, and task
  defaults into a concise Hugging Face interface. The course engine creates both text
  generation and summarization pipelines.
- LangChain `HuggingFacePipeline` wraps a Transformers pipeline as a Runnable/LLM, allowing
  it to participate in `prompt | llm | parser` LCEL chains.

All three expose inference over pretrained models; none is itself a fine-tuning method.

## Quantization

`MODEL_QUANTIZATION=none|4bit|8bit` controls generation loading. On compatible Linux/CUDA
hosts, `BitsAndBytesConfig` enables NF4 double-quantized 4-bit loading or 8-bit loading.
On CPU and Apple MPS, EnterpriseRAG records a fallback reason and loads without
BitsAndBytes. The local Mac validation therefore covers configuration/fallback only; the
real CUDA path is provided in `course_demo/notebooks/quantization_bitsandbytes.ipynb`.

The faster-whisper `int8` compute mode is separate from Transformers BitsAndBytes
quantization.
