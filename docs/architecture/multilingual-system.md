# Multilingual System Architecture

EnterpriseRAG supports cross-lingual querying, Arabic document ingestion, RTL layout rendering, and multilingual vector search.

---

## Multilingual Query & Ingestion Flow

```mermaid
flowchart TD
    QUERY["User Input Question"] --> DETECT["Language Detection Service (en / ar)"]
    DETECT --> PROMPT_LANG["Select System Prompt Language"]
    
    KB["Knowledge Base Selection"] --> EMBED_MODEL{"Check KB Embedding Model"}
    EMBED_MODEL -- Existing English index --> MINI_LM["MiniLM-L6-v2 (384d)"]
    EMBED_MODEL -- AWS multilingual --> MULTI_LM["multilingual-e5-small (384d)"]
    
    MINI_LM --> VECTOR_SEARCH["Vector Distance Search"]
    MULTI_LM --> VECTOR_SEARCH
    
    VECTOR_SEARCH --> ARABIC_QA["Arabic / English Grounded Generation"]
    PROMPT_LANG --> ARABIC_QA
    
    ARABIC_QA --> UI["React UI (RTL Adjustment for Arabic)"]
```

---

## Technical Considerations
- **No Vector Mixing**: Each indexed chunk records its embedding model. Retrieval fails with
  an explicit reindex requirement when the configured model differs.
- **E5 Prefixes**: `multilingual-e5-small` receives `query:` for queries and `passage:` for
  document/media chunks in both the custom and LangChain engines.
- **Language Selection**: Automatic detection answers Arabic questions in Arabic and English
  questions in English; users can override output with Arabic or English.
- **Grounded Prompts**: Prompts preserve names, dates, numbers, and citations, and return a
  localized not-found response when evidence is insufficient.
- **RTL UI Styling**: The frontend applies `dir="rtl"` only to primarily Arabic content,
  preserving readability for mixed Arabic/English answers.
