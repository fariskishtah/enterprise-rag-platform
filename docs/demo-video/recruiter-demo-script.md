# Recruiter Demo Script (60-Second Elevator Pitch)

Targeted script for technical recruiters and hiring managers.

---

## 60-Second Pitch Script

*"Hi, I'm Faris, and I built **EnterpriseRAG**—a local-first multimodal knowledge intelligence platform designed to eliminate AI hallucinations across enterprise documents, video, and scanned media.*

*Unlike standard RAG prototypes that rely on third-party cloud APIs, EnterpriseRAG runs 100% locally using Qwen2.5-0.5B, sentence-transformers, faster-whisper, and FAISS.*

*Key engineering highlights:*
1. **Zero Hallucinations**: Sentence-level claim verifier checks every output against citations.
2. **Multimodal & Multilingual**: Supports scanned PDFs via OCR, structured tables via pdfplumber, video timestamp citations, and Arabic cross-lingual QA.
3. **8 GB RAM Optimizations**: Reduced multi-prompt Compare from 6 LLM calls to 1 single call (>80% latency reduction) and engineered a process concurrency queue to prevent OOM thrashing.
4. **Production Architecture**: Features an Evaluation Dashboard, User Feedback Analytics, JWT Authentication, and a multi-stage Docker setup deployable on Hugging Face Spaces.

*Check out the live code on GitHub and test the interactive demo on Hugging Face Spaces!"*
