# Course compatibility layer

## Purpose and boundaries

EnterpriseRAG now supports `custom` and `langchain` engines. The existing custom FastAPI,
React, extraction, retrieval, reranking, media, model-provider, and verification code
remains the default production architecture. The LangChain package is an additive course
compatibility layer, not a relabeling of custom equivalents.

## Configuration

```bash
RAG_ENGINE=custom
RAG_ENGINE=langchain
MODEL_QUANTIZATION=none
MODEL_QUANTIZATION=4bit
MODEL_QUANTIZATION=8bit
```

The usual prefixed EnterpriseRAG variables remain available. Generation parameters are:

```bash
ENTERPRISE_RAG_GENERATION_TEMPERATURE=0.1
ENTERPRISE_RAG_GENERATION_TOP_K=50
ENTERPRISE_RAG_GENERATION_TOP_P=0.9
ENTERPRISE_RAG_GENERATION_MAX_NEW_TOKENS=256
ENTERPRISE_RAG_GENERATION_REPETITION_PENALTY=1.0
ENTERPRISE_RAG_GENERATION_DO_SAMPLE=true
```

Generation `top_k` is passed only to model sampling. Retrieval `top_k` remains a separate
setting.

## LangChain document and retrieval lifecycle

`LangChainDocumentPipeline` directly selects `PyPDFLoader`, `TextLoader`, or
`Docx2txtLoader`, augments metadata, runs `RecursiveCharacterTextSplitter`, embeds with
`HuggingFaceEmbeddings`, and writes a FAISS index for each knowledge base.

The class supports create, load, incremental replacement, full re-index, document-vector
deletion, retrieval, and process-restart reload. `manifest.json`, `index.faiss`, and
`index.pkl` are stored under the configured private index root. Loading permits local
pickle deserialization only because the files are generated inside that private root;
operators must not replace them with untrusted files.

When changing an existing deployment from custom to LangChain, reprocess or re-index its
documents once. Subsequent restarts load the persisted index.

## Structured LCEL

The course package defines Pydantic schemas for grounded answers, citations,
verification, summaries, comparisons, reports, and query rewrites. Each chain is built
with a direct `PromptTemplate | LLM | PydanticOutputParser` sequence. Parse failures enter
a bounded repair chain and surface a safe provider error if validation still fails.

The composed chain performs:

```text
question/history
  → QueryRewriteResult
  → VectorStoreRetriever
  → list[Document]
  → GroundedAnswer
  → VerificationResult
```

Dedicated structured summary, comparison, and report chains are also exposed.

## Three generation integrations

| Integration | Strength | Trade-off |
| --- | --- | --- |
| Direct `model.generate()` | Maximum control over tensors, device, token slicing, and fallback | More orchestration code |
| `transformers.pipeline()` | Concise standard task API for generation and summarization | Task defaults can hide details |
| LangChain `HuggingFacePipeline` | Runnable that composes directly with prompts and parsers | Adds LangChain abstraction and dependencies |

The course runtime prefers `HuggingFacePipeline`. If it cannot initialize, it records the
reason and uses `EnterpriseGenerationLLM`, a real LangChain `LLM` wrapper around the
existing local provider. This fallback remains inside the LangChain engine and does not
silently route to the custom RAG orchestration.

## Quantization and hardware

The quantization module directly creates `BitsAndBytesConfig`. Four-bit mode uses:

- `load_in_4bit=True`
- float16 compute
- NF4 quantization
- double quantization

Eight-bit mode uses `load_in_8bit=True`. BitsAndBytes is dependency-gated to compatible
Linux x86-64 environments. The current Apple/MPS environment cannot execute the CUDA
path, so local verification covers graceful fallback. The CUDA notebook measures
footprint, latency, output, and failures without claiming unsupported hardware results.

## Model persistence

`save_model_bundle()` directly calls `model.save_pretrained()` and
`tokenizer.save_pretrained()`, then records a small manifest. `reload_model_bundle()` uses
`AutoConfig`, the matching AutoModel class, `AutoTokenizer`, and
`local_files_only=True`. Quantized models can have architecture-specific save limitations;
adapter saving or dequantization may be required.

## Optional education and presentation

- `course_demo/fine_tuning/` is a tiny LoRA/PEFT mechanics experiment. It is never imported
  by the production application.
- `course_demo/streamlit_app/` is a presentation UI and does not replace React.
- `course_demo/ngrok/` requires an explicit command and environment token. Tests never
  expose a service.
- The seven notebooks are Colab-compatible, contain no secrets, and include guarded error
  paths and expected-output notes.

## Validation commands

```bash
backend/.venv/bin/ruff format --check backend course_demo
backend/.venv/bin/ruff check backend course_demo
backend/.venv/bin/pytest -q backend/tests

RUN_REAL_MODEL_TESTS=1 backend/.venv/bin/pytest -q backend/tests/test_real_huggingface_rag.py
backend/.venv/bin/pytest -q backend/tests/test_real_langchain_rag.py

npm --prefix frontend run typecheck
npm --prefix frontend run build

backend/.venv/bin/python -m json.tool course_demo/notebooks/langchain_rag_demo.ipynb
backend/.venv/bin/streamlit run course_demo/streamlit_app/app.py --server.headless=true
backend/.venv/bin/python backend/scripts/compare_rag_engines.py
```

## Remaining limitations

- Local FAISS is appropriate for the course engine and small single-node deployments, not
  tenant-scale distributed retrieval.
- BitsAndBytes execution requires a compatible CUDA environment and was not run on MPS.
- LoRA quality is not established by the tiny mechanics dataset.
- Compact local models can fail structured output; bounded repair cannot guarantee
  recovery from every malformed response.
- The Streamlit and ngrok surfaces are educational and do not add authentication.
