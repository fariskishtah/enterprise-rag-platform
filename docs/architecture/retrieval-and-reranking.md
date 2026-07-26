# Retrieval & Reranking Architecture

EnterpriseRAG employs a multi-stage hybrid retrieval strategy to maximize recall while maintaining high precision.

---

## Retrieval & Reranking Pipeline

```mermaid
flowchart TD
    QUERY["Query Vector & Terms"] --> POOL["Candidate Pool Selection (top 40 chunks)"]
    
    POOL --> DENSE_SCORE["Dense Cosine Score (0.45)"]
    POOL --> LEXICAL_SCORE["BM25 Lexical Score (0.30)"]
    POOL --> COVERAGE_SCORE["Query Term Coverage (0.25)"]
    
    DENSE_SCORE --> COMBINED["Score Fusion & Reranking"]
    LEXICAL_SCORE --> COMBINED
    COVERAGE_SCORE --> COMBINED
    
    COMBINED --> DEDUP["Near-Duplicate Filter (Threshold 0.88)"]
    DEDUP --> SOURCE_CAP["Per-Document Source Cap (Max 3/doc)"]
    SOURCE_CAP --> FINAL["Final Top-K Context Passages"]
```

---

## Score Formula

$$\text{Final Score} = (0.45 \times \text{Dense Score}) + (0.30 \times \text{Lexical Score}) + (0.25 \times \text{Query Coverage})$$

Chunks scoring below `similarity_threshold` (default 0.2) are pruned before context assembly.
