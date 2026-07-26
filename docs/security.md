# EnterpriseRAG Security Architecture & Threat Model

EnterpriseRAG is designed with a defense-in-depth security model to safeguard enterprise content, prevent prompt injection attacks, and secure containerized deployments.

---

## 1. Threat Model & Risk Analysis

| Threat | Target | Mitigation Strategy |
| :--- | :--- | :--- |
| **Indirect Prompt Injection** | Untrusted uploaded PDFs/DOCXs | Enclose extracted passages in `[BEGIN_UNTRUSTED_SOURCE]` blocks with system instructions forbidding execution of embedded commands. |
| **Server-Side Request Forgery (SSRF)** | Media URL Ingestion (`/media/from-url`) | Validate URL schemes (`http`, `https`), block private subnets (127.0.0.1, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), and enforce timeouts. |
| **Insecure Direct Object Reference (IDOR)** | Knowledge base & document endpoints | Scope database queries strictly by authenticated `user_id` on every API route. |
| **Resource Exhaustion (DoS)** | Local Inference / GPU memory | Enforce maximum file upload sizes (15 MB text / 500 MB video), route timeouts, and process-wide `GenerationQueue` semaphores. |
| **JWT Token Abuse** | API Authentication | Short-lived HS256 JWT bearer tokens with password hashing via `bcrypt`. |

---

## 2. Implemented Security Controls

1. **Context Boundary Enforcement**:
   ```text
   [BEGIN_UNTRUSTED_SOURCE doc1-chunk2]
   document_id: doc1
   page: 2
   <Extracted text content>
   [END_UNTRUSTED_SOURCE]
   ```
2. **File Checksum Verification**: SHA-256 digest computation upon upload to prevent duplicate processing and tamper detection.
3. **Container Isolation**: Non-root runtime configuration in single-container Hugging Face Docker Space.
