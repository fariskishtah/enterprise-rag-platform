# Deployment Flow Architecture

The deployment pipeline automates static asset building, Docker container packaging, and Hugging Face Docker Space synchronization.

---

## Continuous Integration & Deployment Flow

```mermaid
flowchart LR
    DEV["Developer / Git Commit"] --> CI["GitHub Actions CI"]
    
    subgraph CI_STEPS ["CI Validation Steps"]
        PYTEST["Backend Pytest (65+ tests)"]
        RUFF["Ruff Lint & Format"]
        TSC["Frontend tsc & Vite Build"]
        DOCKER_BUILD["Docker Image Build Check"]
    end
    
    CI --> PYTEST
    CI --> RUFF
    CI --> TSC
    CI --> DOCKER_BUILD
    
    DOCKER_BUILD --> HF["Hugging Face Docker Space Sync"]
    HF --> SPACE_BUILD["Hugging Face Space Multi-Stage Build"]
    SPACE_BUILD --> LIVE["Space Active on Port 7860"]
```

---

## Environment Variable Checklist for Deployment
- `APP_RUNTIME_PROFILE=huggingface_demo`
- `RAG_ENGINE=custom`
- `ENTERPRISE_RAG_GENERATION_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct`
- `ENTERPRISE_RAG_EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2`
- `ENTERPRISE_RAG_MAX_CONCURRENT_GENERATIONS=1`
