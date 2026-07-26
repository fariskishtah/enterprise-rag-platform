# EnterpriseRAG local performance summary

Measured on the local Apple Silicon development machine with cached model weights.

| Path | Result |
| --- | --- |
| Document processing + first MiniLM embedding load | 4,159.4 ms |
| First grounded Qwen answer on MPS | 2,951.7 ms total |
| Subsequent grounded Qwen answer on MPS | 1,058.8 ms total |
| Unsupported-question retrieval gate | 45.1 ms total; generation skipped |
| Deterministic hybrid policy questions | 3.5–6.5 ms total |
| faster-whisper Tiny first uncached run | 44.1 s |
| faster-whisper Tiny cached CPU int8 run | 2.5 s |
| Frontend production entry chunk | 214.63 kB / 67.89 kB gzip |
| Frontend route chunk range | 1.70–13.19 kB |
| Frontend production build | 1.15 s |

The pre-acceleration CPU Qwen measurements were 14.5–29.6 seconds for the two supported
policy questions. Hardware-aware MPS selection reduced those responses to approximately
1.0–3.0 seconds in the final cached run. Route-level code splitting reduced the entry
bundle from 275.12 kB (83.29 kB gzip) to 214.63 kB (67.89 kB gzip).
