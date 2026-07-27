# 06 — Environment variables

`Settings` reads `.env` and process variables with the `ENTERPRISE_RAG_` prefix (`backend/app/core/config.py:15-28`). Values below are code defaults before a runtime profile adjusts them. All backend settings require an application restart when changed, except that the *contents* of the configured YouTube cookie source are refreshed by modification time before use.

Never commit `.env`, hashes, tokens, cookies, user content, or production paths containing sensitive names. Safe examples below are placeholders, not current values.

## Application, authentication, and persistence

| Variable | Required / default | Purpose and reader | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_APP_NAME` | Optional; `EnterpriseRAG Pro` | FastAPI title; `config.py:30`, `main.py:98-101`. | `EnterpriseRAG Test` | Yes |
| `ENTERPRISE_RAG_APP_VERSION` | Optional; `0.5.0` | API version metadata. | `0.5.0` | Yes |
| `ENTERPRISE_RAG_API_PREFIX` | Optional; `/api/v1` | Prefix applied to all included routes. Frontend production assumes `/api/v1`. | `/api/v1` | Yes; changing also requires frontend/proxy alignment |
| `ENTERPRISE_RAG_ENVIRONMENT` | Optional; `development` | Environment label and production validation; `config.py:33,217-228`. | `development` | Yes |
| `ENTERPRISE_RAG_GIT_COMMIT` | Optional; none | Build provenance shown in operations/config; Compose/deploy supplies it. | `unknown` | Yes |
| `ENTERPRISE_RAG_ACCESS_MODE` | Optional locally; `open`. Production defaults to `demo_password` when not explicitly set. | `open`, shared `demo_password`, or `accounts`. | `demo_password` | Yes |
| `ENTERPRISE_RAG_DEMO_PASSWORD_HASH` | Required only for production `demo_password`; no default | Bcrypt hash for shared login. Read by auth route. | `<bcrypt-hash-generated-locally>` | Yes |
| `ENTERPRISE_RAG_SESSION_SECRET` | Development default is unsafe; production non-open requires 32+ chars | Signs cookie/bearer claims. | `<32+-character-random-secret>` | Yes; invalidates existing sessions |
| `ENTERPRISE_RAG_SESSION_EXPIRY_MINUTES` | Optional; `120` | Signed session lifetime. | `120` | Yes |
| `ENTERPRISE_RAG_COOKIE_SECURE` | Optional; `false` | Adds Secure to session cookie; should be true behind HTTPS. | `true` | Yes |
| `ENTERPRISE_RAG_SESSION_COOKIE_NAME` | Optional; `enterprise_rag_session` | Cookie key. | `enterprise_rag_session` | Yes; old cookies remain under old name |
| `ENTERPRISE_RAG_LOGIN_MAX_ATTEMPTS` | Optional; `5` | In-process shared/account login limit. | `5` | Yes |
| `ENTERPRISE_RAG_LOGIN_LOCKOUT_MINUTES` | Optional; `15` | Login lockout window. | `15` | Yes |
| `ENTERPRISE_RAG_DATABASE_URL` | Optional; `sqlite:///./data/enterprise_rag.db` | SQLAlchemy database URL. | `sqlite:///./data/guide-test.db` | Yes; migrate the target first |
| `ENTERPRISE_RAG_STORAGE_PATH` | Optional; `data/uploads` | Original/derived upload root and operation markers. | `data/guide-uploads` | Yes |
| `ENTERPRISE_RAG_MODEL_CACHE_PATH` | Optional; `data/models` | Embedding/generation/Whisper cache root. | `data/guide-models` | Yes |
| `ENTERPRISE_RAG_LANGCHAIN_INDEX_PATH` | Optional; `data/langchain_indexes` | Per-KB persistent FAISS indexes. | `data/guide-langchain-indexes` | Yes |
| `ENTERPRISE_RAG_CORS_ORIGINS` | Optional; JSON/list default `http://localhost:5173` | Browser origins allowed to call API with credentials. | `["http://localhost:5173"]` | Yes |

Production rules are enforced in `backend/app/core/config.py:217-228`; a weak session secret or invalid demo hash prevents startup instead of silently weakening access.

## Upload, media, quota, and retention limits

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_MAX_UPLOAD_MB` | Optional; `50` | Human-facing/document size limit; also derives bytes if byte setting is absent. | `25` | Yes |
| `ENTERPRISE_RAG_MAX_UPLOAD_BYTES` | Optional; `52428800` | Streaming document upload limit. | `26214400` | Yes |
| `ENTERPRISE_RAG_MAX_MEDIA_UPLOAD_BYTES` | Optional; `52428800` | Streaming direct media limit. | `26214400` | Yes |
| `ENTERPRISE_RAG_MAX_DOCUMENT_PAGES` | Optional; `300` | Rejects documents above page limit. | `100` | Yes |
| `ENTERPRISE_RAG_MAX_MEDIA_DURATION_MINUTES` | Optional; `30` | Human-facing duration and derives seconds if needed. | `10` | Yes |
| `ENTERPRISE_RAG_MAX_MEDIA_DURATION_SECONDS` | Optional; `1800` | Enforced media duration. | `600` | Yes |
| `ENTERPRISE_RAG_MAX_FILES_PER_KNOWLEDGE_BASE` | Optional; `25` | Combined collection source quota used by creation services. | `10` | Yes |
| `ENTERPRISE_RAG_MAX_KNOWLEDGE_BASES` | Optional; `5` | Public/demo collection quota. | `3` | Yes |
| `ENTERPRISE_RAG_MAX_CONCURRENT_UPLOADS` | Optional; `2` | Upload middleware slots. | `2` | Yes |
| `ENTERPRISE_RAG_MAX_CONCURRENT_HEAVY_OPERATIONS` | Optional; `1` | Actual generation/heavy queue concurrency in `main.py:183-188`. | `1` | Yes |
| `ENTERPRISE_RAG_REQUEST_BODY_LIMIT_MB` | Optional; `55` | Middleware declared request-body limit; coordinate with Nginx. | `30` | Yes |
| `ENTERPRISE_RAG_TEMP_FILE_RETENTION_HOURS` | Optional; `12` | Age before orphan/temp cleanup eligibility. | `12` | Yes |
| `ENTERPRISE_RAG_DEMO_DATA_RETENTION_HOURS` | Optional; `24`; `0` allowed | Expiry assigned to public-demo lifecycle records. | `24` | Yes |
| `ENTERPRISE_RAG_MEDIA_DOWNLOAD_TIMEOUT_SECONDS` | Optional; `120` | Remote media request/yt-dlp bound. | `120` | Yes |
| `ENTERPRISE_RAG_MEDIA_PROCESSING_TIMEOUT_SECONDS` | Optional; `1800` | Whole media processing bound. | `900` | Yes |
| `ENTERPRISE_RAG_YTDLP_COOKIES_FILE` | Optional; none | Read-only cookie source copied to private writable runtime file. | `/run/secrets/youtube-cookies.txt` | Path change: yes; source-content mtime change: no |

## Chunking, embeddings, retrieval, and RAG engine

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_CHUNK_SIZE` | Optional; `800` | Custom and LangChain text chunk size. | `800` | Yes; reprocess sources |
| `ENTERPRISE_RAG_CHUNK_OVERLAP` | Optional; `120` | Characters/tokens of adjacent overlap; must be less than size. | `120` | Yes; reprocess |
| `ENTERPRISE_RAG_EMBEDDING_MODEL_NAME` | Optional; `sentence-transformers/all-MiniLM-L6-v2` | Sentence-transformer/HuggingFaceEmbeddings ID. | `sentence-transformers/all-MiniLM-L6-v2` | Yes; reprocess/reindex |
| `ENTERPRISE_RAG_EMBEDDING_BATCH_SIZE` | Optional; `32`; AWS profile `8` if default | Embedding batch memory/performance. | `8` | Yes |
| `ENTERPRISE_RAG_HF_LOCAL_FILES_ONLY` | Optional; `false` | Forbid Hugging Face network lookup. | `true` | Yes |
| `ENTERPRISE_RAG_RAG_ENGINE` | Optional; `custom` | Select relational custom engine or LangChain/FAISS. | `custom` | Yes; reprocess for selected index |
| `RAG_ENGINE` | Alias for preceding setting | Unprefixed compatibility alias in `config.py:75-78`. | `langchain` | Yes |
| `ENTERPRISE_RAG_RETRIEVAL_TOP_K` | Optional; `5`; low/AWS `3` if default | Final number of passages. | `3` | Yes |
| `ENTERPRISE_RAG_RETRIEVAL_CANDIDATE_POOL` | Optional; `40`; low `20`, AWS `12` if default | Pre-rerank candidates. | `20` | Yes |
| `ENTERPRISE_RAG_SIMILARITY_THRESHOLD` | Optional; `0.2` | Minimum accepted dense/source score. | `0.2` | Yes |
| `ENTERPRISE_RAG_DENSE_SCORE_WEIGHT` | Optional; `0.45` | Hybrid dense contribution. | `0.45` | Yes |
| `ENTERPRISE_RAG_LEXICAL_SCORE_WEIGHT` | Optional; `0.30` | Word-overlap contribution. | `0.30` | Yes |
| `ENTERPRISE_RAG_RERANK_SCORE_WEIGHT` | Optional; `0.25` | Heuristic rerank contribution. | `0.25` | Yes |
| `ENTERPRISE_RAG_NEAR_DUPLICATE_THRESHOLD` | Optional; `0.88` | Suppresses very similar passages. | `0.88` | Yes |
| `ENTERPRISE_RAG_MINIMUM_QUERY_COVERAGE` | Optional; `0.16` | Minimum query-token coverage support gate. | `0.16` | Yes |
| `ENTERPRISE_RAG_MAXIMUM_SOURCES_PER_DOCUMENT` | Optional; `3` | Diversity cap per document. | `3` | Yes |
| `ENTERPRISE_RAG_CONVERSATION_HISTORY_MESSAGES` | Optional; `6`; low `4` | Recent messages used for rewrite/context. | `4` | Yes |
| `ENTERPRISE_RAG_QUERY_EMBEDDING_CACHE_SIZE` | Optional; `128` | In-process query-vector LRU size; `0` disables. | `128` | Yes |

## Generation model and parameters

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_GENERATION_MODEL_NAME` | Optional; `Qwen/Qwen2.5-0.5B-Instruct` | Primary local answer model ID. | `Qwen/Qwen2.5-0.5B-Instruct` | Yes |
| `ENTERPRISE_RAG_GENERATION_FALLBACK_MODEL_NAME` | Optional; `google/flan-t5-base` | Secondary model before extractive fallback. | `google/flan-t5-base` | Yes |
| `ENTERPRISE_RAG_MODEL_DEVICE` | Optional; `auto` | Resolves CUDA, MPS, or CPU; AWS profile forces CPU. | `cpu` | Yes |
| `ENTERPRISE_RAG_GENERATION_QUANTIZATION` | Optional; `none` | `none`, `4bit`, or `8bit`; BitsAndBytes only on supported CUDA. | `none` | Yes |
| `ENTERPRISE_RAG_MODEL_QUANTIZATION` | Alias | Legacy/course spelling for generation quantization. | `8bit` | Yes |
| `MODEL_QUANTIZATION` | Alias | Unprefixed compatibility alias. Legacy `int8` normalizes to `8bit`. | `none` | Yes |
| `ENTERPRISE_RAG_GENERATION_TEMPERATURE` | Optional; `0.1`; AWS `0.0` with sampling off | Randomness. Must be >0 when sampling. | `0.1` | Yes |
| `ENTERPRISE_RAG_GENERATION_TOP_K` | Optional; `50` | Sampling top-k. | `50` | Yes |
| `ENTERPRISE_RAG_GENERATION_TOP_P` | Optional; `0.9` | Nucleus sampling threshold. | `0.9` | Yes |
| `ENTERPRISE_RAG_GENERATION_MAX_NEW_TOKENS` | Optional; `256`; low `128`, AWS `96`, quality `512` | Maximum answer tokens. | `128` | Yes |
| `ENTERPRISE_RAG_MAXIMUM_NEW_TOKENS` | Alias | Course-compatible alias for preceding value. | `128` | Yes |
| `ENTERPRISE_RAG_GENERATION_REPETITION_PENALTY` | Optional; `1.0` | Penalizes repeated token patterns. | `1.05` | Yes |
| `ENTERPRISE_RAG_GENERATION_DO_SAMPLE` | Optional; `true`; AWS `false` | Sampling versus deterministic decoding. | `false` | Yes |
| `ENTERPRISE_RAG_LANGCHAIN_PARSER_RETRIES` | Optional; `1`; low/AWS `0` | Bounded structured-output repair attempts. | `0` | Yes |
| `ENTERPRISE_RAG_MAX_CONTEXT_CHARACTERS` | Optional; `12000`; low `4000`, AWS `3000` | Maximum prompt context. | `4000` | Yes |
| `ENTERPRISE_RAG_MAXIMUM_CONTEXT_CHARACTERS` | Alias | Course-compatible alias. | `4000` | Yes |

`ENTERPRISE_RAG_GENERATION_MAX_NEW_TOKENS` and `ENTERPRISE_RAG_MAXIMUM_NEW_TOKENS` are alternatives, not two independent controls. The same is true of the context and quantization aliases (`backend/app/core/config.py:79-122`).

## Transcription

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_TRANSCRIPTION_MODEL_NAME` | Optional; `small`; AWS/HF `base` | faster-whisper size: `tiny`, `base`, or `small`. | `base` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_DEVICE` | Optional/fixed schema; `cpu` | Transcription device. | `cpu` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_COMPUTE_TYPE` | Optional/fixed schema; `int8` | CTranslate2 compute type. | `int8` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_LANGUAGE` | Optional; `auto` | Default forced language (`auto`, `ar`, `en`). | `auto` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_CPU_THREADS` | Optional; `4`; AWS `2` | Whisper CPU threads. | `2` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_NUM_WORKERS` | Optional; `1` | faster-whisper workers. | `1` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_BEAM_SIZE` | Optional; `3` | Decode beam size. | `3` | Yes |

## Profiles, queues, timeouts, intelligence, verification, and model lifecycle

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_RUNTIME_PROFILE` | Optional; `balanced` | `low_memory`, `balanced`, `quality`, `aws_cpu`, or `huggingface_demo`; applies defaults in `config.py:231-278`. | `low_memory` | Yes |
| `APP_RUNTIME_PROFILE` | Alias | Unprefixed profile used by Dockerfile. | `huggingface_demo` | Yes |
| `ENTERPRISE_RAG_MAX_CONCURRENT_GENERATIONS` | Optional; `2`; profile-dependent | Exposed/profile compatibility generation value. The main queue is currently constructed from `MAX_CONCURRENT_HEAVY_OPERATIONS`. | `1` | Yes |
| `ENTERPRISE_RAG_HEAVY_QUEUE_MAX_SIZE` | Optional; `2` | Maximum waiting heavy jobs. | `2` | Yes |
| `ENTERPRISE_RAG_GENERATION_TIMEOUT_SECONDS` | Optional; `90`; profile-dependent | Bound a generation execution. | `120` | Yes |
| `ENTERPRISE_RAG_GENERATION_QUEUE_TIMEOUT_SECONDS` | Optional; `120`; profile-dependent | Time waiting for a heavy slot. | `180` | Yes |
| `ENTERPRISE_RAG_MODEL_LOAD_TIMEOUT_SECONDS` | Optional; `120` | Warm/model load bound. | `120` | Yes |
| `ENTERPRISE_RAG_RETRIEVAL_TIMEOUT_SECONDS` | Optional; `30` | Retrieval bound. | `30` | Yes |
| `ENTERPRISE_RAG_COMPARISON_MAX_CONTEXT_CHARACTERS` | Optional; `8000`; low/AWS smaller | Comparison context bound. | `3000` | Yes |
| `ENTERPRISE_RAG_COMPARISON_TIMEOUT_SECONDS` | Optional; `120`; profile-dependent | Whole comparison bound. | `90` | Yes |
| `ENTERPRISE_RAG_REPORT_TIMEOUT_SECONDS` | Optional; `180`; profile-dependent | Whole report bound. | `120` | Yes |
| `ENTERPRISE_RAG_REPORT_SECTION_TIMEOUT_SECONDS` | Optional; `60`; profile-dependent | Per report section bound. | `45` | Yes |
| `ENTERPRISE_RAG_SUMMARY_TIMEOUT_SECONDS` | Optional; `60`; profile-dependent | Summary bound. | `60` | Yes |
| `ENTERPRISE_RAG_INTELLIGENCE_MAX_NEW_TOKENS` | Optional; `256`; low `160`, quality `512` | Token limit for intelligence calls. | `160` | Yes |
| `ENTERPRISE_RAG_VERIFICATION_MODE` | Optional; `deterministic` | `deterministic`, `llm`, or `skip`. | `deterministic` | Yes |
| `ENTERPRISE_RAG_MODEL_IDLE_UNLOAD_SECONDS` | Optional; `0` | Idle model unload delay; zero disables. | `0` | Yes |
| `ENTERPRISE_RAG_LANGCHAIN_FORCE_WRAPPER` | Optional; `false`; low/AWS true | Reuse product generation provider instead of loading a duplicate LangChain pipeline. | `true` | Yes |
| `ENTERPRISE_RAG_WARM_MODELS_ON_STARTUP` | Optional; `false` | Start background warmup during lifespan. | `false` | Yes |
| `ENTERPRISE_RAG_WARM_GENERATION_MODEL_ON_STARTUP` | Optional; `true`; AWS/HF false | Whether warmup includes generation. | `false` | Yes |
| `ENTERPRISE_RAG_UNLOAD_TRANSCRIPTION_MODEL_AFTER_USE` | Optional; `false`; AWS/HF true | Release Whisper after each job. | `true` | Yes |
| `ENTERPRISE_RAG_TORCH_NUM_THREADS` | Optional; `2` | PyTorch CPU threads set during app creation. | `2` | Yes |
| `ENTERPRISE_RAG_TORCH_NUM_INTEROP_THREADS` | Optional; `1` | PyTorch inter-op threads. | `1` | Yes |
| `ENTERPRISE_RAG_TOKENIZER_PARALLELISM` | Optional; `false` | Sets tokenizer parallel behavior. | `false` | Yes |

## Rate limits and backups

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `ENTERPRISE_RAG_UPLOAD_RATE_LIMIT_PER_MINUTE` | Optional; `10` | In-process upload request rate. | `10` | Yes |
| `ENTERPRISE_RAG_GENERATION_RATE_LIMIT_PER_MINUTE` | Optional; `12` | Ask/intelligence/evaluation generation rate. | `12` | Yes |
| `ENTERPRISE_RAG_TRANSCRIPTION_RATE_LIMIT_PER_MINUTE` | Optional; `6` | Media processing/transcription request rate. | `6` | Yes |
| `ENTERPRISE_RAG_URL_IMPORT_RATE_LIMIT_PER_MINUTE` | Optional; `6` | Public URL import rate. | `6` | Yes |
| `ENTERPRISE_RAG_BACKUP_DIR` | Optional app default `backups`; AWS shell default `/home/ubuntu/enterprise-rag-backups`, container `/backups` | Operation marker and host backup destination, read by settings/Compose/scripts. | `/srv/enterprise-rag-backups` | App: yes; scripts read per invocation |
| `ENTERPRISE_RAG_BACKUP_RETENTION_DAYS` | Optional; `7` | Old verified backup retention. | `7` | App: yes; scripts read per invocation |

## Container, build, numerical runtime, and deployment script variables

These are read by Docker, libraries, or scripts rather than Pydantic settings.

| Variable | Required / default | Purpose and reader | Safe example | Restart/rebuild? |
|---|---|---|---|---|
| `HF_HOME` | Optional | Hugging Face cache root; Compose sets `/models/huggingface`. | `/models/huggingface` | Restart |
| `OMP_NUM_THREADS` | Optional/library default | OpenMP CPU thread bound in environment profiles. | `2` | Restart |
| `MKL_NUM_THREADS` | Optional/library default | MKL CPU thread bound. | `2` | Restart |
| `TOKENIZERS_PARALLELISM` | Optional; Docker `false` | Transformers tokenizer process setting. App also sets it for CPU. | `false` | Restart |
| `CUDA_VISIBLE_DEVICES` | Optional; Docker empty | Hides GPUs for CPU image/profile. | empty string | Restart |
| `DENO_DIR` | Optional; Docker `/tmp/enterprise-rag/deno-cache` | Writable Deno cache for yt-dlp challenges. | `/tmp/enterprise-rag/deno-cache` | Restart/path creation |
| `PYTHONUNBUFFERED` | Optional; Docker `1` | Immediate Python logs. | `1` | Restart |
| `PYTHONDONTWRITEBYTECODE` | Optional; Compose `1` | Avoid `.pyc` writes. | `1` | Restart |
| `PORT` | Dockerfile sets `7860` | Platform convention. Current `start-space.sh:15` starts Uvicorn on hard-coded 7860, so changing only `PORT` has no effect. | `7860` | No effective change unless startup script changes |
| `PYTORCH_INDEX_URL` | Build arg default CPU PyTorch index | Prevents production image from pulling CUDA wheels (`Dockerfile:42-48`). | `https://download.pytorch.org/whl/cpu` | Rebuild image |
| `ENTERPRISE_RAG_IMAGE_TAG` | Optional; Compose `latest` | Select built/deployed image tag. | `release-example` | Recreate container |
| `ENTERPRISE_RAG_IMAGE_ID` | Optional; deploy/backup derives it | Backup manifest and rollback provenance. | `unknown` | Script invocation only |
| `ENTERPRISE_RAG_COMPOSE_FILE` | Optional; scripts default AWS Compose path | Backup/restore alternate Compose file. | `/path/to/docker-compose.aws.yml` | Script invocation only |

## Frontend and browser tests

| Variable | Required / default | Purpose | Safe example | Restart/rebuild? |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | Optional in development; default `/api/v1` | Dev/test API origin. Production build intentionally ignores it (`frontend/src/api/client.ts:27-32`). | `http://127.0.0.1:8000/api/v1` | Restart dev server/rebuild dev bundle |
| `PLAYWRIGHT_BASE_URL` | Optional; config default local server | Target existing app, including Docker production smoke. | `http://127.0.0.1:7865` | New Playwright run |
| `PLAYWRIGHT_DEV_PORT` | Optional | Port for deterministic Vite/browser-test server. | `4173` | New run |
| `PLAYWRIGHT_PRODUCTION` | Optional; false | Select production smoke behavior/server expectations. | `1` | New run |
| `PLAYWRIGHT_DEMO_PASSWORD` | Required only when browser target uses demo password | Login secret passed to Playwright. Do not put it in tracked files. | `<test-password-from-secret-store>` | New run |

## Real tests and course demonstrations

| Variable | Required / default | Purpose | Safe example | Restart? |
|---|---|---|---|---|
| `RUN_REAL_MODEL_TESTS` | Optional; unset/false | Explicitly allows downloaded Hugging Face real-model tests in marker files. | `1` | New pytest run |
| `RUN_REAL_TRANSCRIPTION_TESTS` | Optional; unset/false | Explicitly allows real faster-whisper model/audio test. | `1` | New pytest run |
| `NGROK_AUTHTOKEN` | Required only for explicit course ngrok script | Authenticates `course_demo/ngrok/launch_tunnel.py`. Never used by production app. | `<token-from-ngrok-secret-store>` | New script run |

## Profile precedence and restart warning

Runtime profiles modify only values still equal to class defaults (`backend/app/core/config.py:231-287`). Explicit environment overrides should win. Because model providers, queues, middleware, paths, and the database engine are created in `create_app`, assume every `ENTERPRISE_RAG_*` setting needs a restart. Changing embedding/chunk/engine settings also requires reprocessing or reindexing existing sources; a restart alone is not enough.
