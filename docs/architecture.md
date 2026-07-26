# Architecture

EnterpriseRAG separates API schemas, orchestration services, repositories, model
providers, and persistence adapters. Documents and media converge at a timestamp/page
aware `DocumentChunk`, so the same retrieval pipeline can answer across either source
type while citations retain their native location.

```text
Source intake
  ├─ DocumentProcessingService
  │    └─ extract → TextChunker → embeddings → RelationalVectorStore
  └─ MediaProcessingService
       └─ validate/fetch → subtitle or Whisper → transcript segments
          → timestamp chunks → embeddings → RelationalVectorStore

Question
  → QueryRewriteService
  → RetrievalService
       dense candidate pool
       → BM25-style lexical scores
       → weighted fusion/direct relevance
       → near-duplicate removal/source diversity
  → support gate + bounded context
  → grounded local generation
  → AnswerPostProcessor
  → used-citation selection
  → VerificationService
```

SQLite owns metadata, extracted text, vectors, conversations, media lifecycle, transcript
jobs/segments, summaries, chapters, attempts, and exports. Local filesystem storage owns
original binaries, transcript text, temporary media, and model caches.

Idempotency is based on checksums, deterministic IDs, and replace-before-write behavior.
Document retry removes sections/chunks/vectors. Media retry replaces segments, chapters,
summary records, document sections/chunks, and vectors.

The current local vector adapter calculates cosine similarity in process. `VectorStore`,
`EmbeddingProvider`, `GenerationProvider`, and `TranscriptionProvider` are explicit
interfaces for production adapters.

## Engine architecture

The default custom engine remains unchanged:

```text
upload
  → custom extractors
  → TextChunker
  → SentenceTransformer provider
  → RelationalVectorStore
  → hybrid retrieval/reranking
  → custom grounded prompt
  → direct model.generate()
  → custom post-processing/verification
```

`RAG_ENGINE=langchain` selects the additive course engine:

```text
upload
  → PyPDFLoader | TextLoader | Docx2txtLoader
  → RecursiveCharacterTextSplitter
  → HuggingFaceEmbeddings
  → per-knowledge-base persistent FAISS
  → VectorStoreRetriever
  → query rewrite LCEL
  → retrieval LCEL
  → PromptTemplate | HuggingFacePipeline | PydanticOutputParser
  → verification LCEL
  → validated API response
```

The LangChain runtime is lazy and exists only when selected. The custom SQL vectors are
still created, so selecting the course engine does not remove or replace primary product
data. FAISS metadata preserves source filename, page, section, chunk ID, document ID, and
knowledge-base ID.

Security boundaries:

- user filenames never form server paths;
- media commands use argument arrays and `shell=False`;
- URL DNS targets and redirects are validated against private networks;
- source text is delimited as untrusted prompt data;
- citations are selected and verified after generation;
- React never renders raw source HTML.
