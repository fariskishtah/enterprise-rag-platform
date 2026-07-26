# Custom RAG Engine Architecture

The default production RAG engine in EnterpriseRAG combines hybrid retrieval, direct relevance reranking, claim verification, and process concurrency management.

---

## Custom RAG Flow Diagram

```mermaid
flowchart TD
    Q["User Question + Session History"] --> REWRITE["Conversational Query Rewriter"]
    REWRITE --> STANDALONE["Standalone Query"]
    
    STANDALONE --> DENSE["Dense Cosine Search (Weight 0.45)"]
    STANDALONE --> LEXICAL["BM25 Lexical Fusion (Weight 0.30)"]
    
    DENSE --> MERGE["Reranking & Deduplication (Weight 0.25)"]
    LEXICAL --> MERGE
    
    MERGE --> CONTEXT["Context Builder (Max Chars Limit)"]
    CONTEXT --> QUEUE["Generation Queue Semaphore (max_concurrent=1)"]
    
    QUEUE --> PROMPT["Grounded System Prompt [UNTRUSTED Context]"]
    PROMPT --> LLM["Qwen2.5-0.5B Inference"]
    
    LLM --> VERIFY["Sentence-Level Claim Verifier"]
    VERIFY --> ANSWER["Grounded Answer + Citations + Support Status"]
```

---

## Technical Highlights
1. **Query Rewriter**: Converts conversational follow-up questions ("What were its main conclusions?") into standalone search queries.
2. **Hybrid Reranking**: Merges dense vector similarity with lexical term overlap and query coverage scores.
3. **Claim Verifier**: Compares each generated sentence against source chunks to assign support statuses (`fully_supported`, `partially_supported`, `unsupported`).
