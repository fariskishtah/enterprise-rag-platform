# LangChain & LCEL Course Engine Architecture

EnterpriseRAG features a fully compatible alternative engine built using **LangChain & LCEL (LangChain Expression Language)**.

---

## LCEL Orchestration Flow

```mermaid
flowchart TD
    INPUT["Question + Conversation History"] --> REWRITE_CHAIN["Query Rewrite Chain (PROMPT | LLM | PydanticParser)"]
    REWRITE_CHAIN --> RETRIEVER["LangChain FAISS Retriever"]
    RETRIEVER --> DOCS["List of LangChain Documents"]
    
    DOCS --> ANSWER_CHAIN["Grounded QA Chain (GROUNDED_PROMPT | LLM | GroundedAnswerParser)"]
    ANSWER_CHAIN --> VERIFY_CHAIN["Verification Chain (VERIFY_PROMPT | LLM | VerificationParser)"]
    
    VERIFY_CHAIN --> OUTPUT["RagAnswerRead Schema Output"]
```

---

## Low-Memory Shared Adapter Mode

When `langchain_force_wrapper=True` (default in `low_memory` profile), `LangChainEngineRuntime` instantiates `EnterpriseGenerationLLM` to wrap the existing `HuggingFaceGenerationProvider` instance instead of loading a duplicate HuggingFace pipeline.

```mermaid
flowchart LR
    SETTINGS["langchain_force_wrapper = True"] --> RUNTIME["LangChainEngineRuntime"]
    RUNTIME --> WRAPPER["EnterpriseGenerationLLM Adapter"]
    WRAPPER --> SHARED["Shared HuggingFaceGenerationProvider"]
    SHARED --> MODEL["Single Qwen Model Weight in Memory"]
```
