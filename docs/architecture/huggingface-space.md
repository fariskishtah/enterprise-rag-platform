# Hugging Face Docker Space Architecture

EnterpriseRAG packages the React 19 frontend and FastAPI backend into a single-container multi-stage Docker build for seamless deployment on Hugging Face Docker Spaces.

---

## Single-Container Space Architecture

```mermaid
flowchart TD
    subgraph Container ["Hugging Face Docker Space Container (Port 7860)"]
        subgraph Frontend ["React 19 Built Static Files"]
            HTML["index.html"]
            JS["JS / CSS Assets"]
        end

        subgraph Backend ["FastAPI Application (Uvicorn)"]
            STATIC["Static File Server (app/static)"]
            REST["REST API Endpoints (/api/v1/*)"]
            QUEUE["Generation Semaphore Queue (max=1)"]
            MODELS["Lazy Hugging Face Model Loader"]
        end

        HTML --> STATIC
        JS --> STATIC
        REST --> QUEUE --> MODELS
    end

    USER["Web Browser Client"] --> STATIC
    USER --> REST
```

---

## Key Container Optimizations
- **Multi-Stage Build**: Stage 1 builds React static assets with Node 20; Stage 2 runs minimal Python 3.11-slim runtime.
- **Port Mapping**: Binds directly to Hugging Face standard port `7860`.
- **Demo Profile**: Automatically defaults to `APP_RUNTIME_PROFILE=huggingface_demo`.
- **Ephemeral Storage Adapter**: Handles temporary file uploads with auto-cleanup and deterministic demo workspace seeding.
