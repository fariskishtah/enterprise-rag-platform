# Multilingual System Architecture

EnterpriseRAG supports cross-lingual querying, Arabic document ingestion, RTL layout rendering, and multilingual vector search.

---

## Multilingual Query & Ingestion Flow

```mermaid
flowchart TD
    QUERY["User Input Question"] --> DETECT["Language Detection Service (en / ar)"]
    DETECT --> PROMPT_LANG["Select System Prompt Language"]
    
    KB["Knowledge Base Selection"] --> EMBED_MODEL{"Check KB Embedding Model"}
    EMBED_MODEL -- English --> MINI_LM["MiniLM-L6-v2 (384d)"]
    EMBED_MODEL -- Multilingual --> MULTI_LM["paraphrase-multilingual-MiniLM-L12-v2 (384d)"]
    
    MINI_LM --> VECTOR_SEARCH["Vector Distance Search"]
    MULTI_LM --> VECTOR_SEARCH
    
    VECTOR_SEARCH --> ARABIC_QA["Arabic / English Grounded Generation"]
    PROMPT_LANG --> ARABIC_QA
    
    ARABIC_QA --> UI["React UI (RTL Adjustment for Arabic)"]
```

---

## Technical Considerations
- **No Vector Mixing**: Knowledge bases enforce a single embedding model at creation time (`all-MiniLM-L6-v2` or `paraphrase-multilingual-MiniLM-L12-v2`).
- **Modern Standard Arabic Prompts**: Structured Arabic system prompts enforce grounded answer formatting and passage markers (`[SOURCE:chunk_id]`).
- **RTL UI Styling**: Frontend dynamically adjusts text direction (`dir="rtl"`) when Arabic mode is active.
