# Multilingual Evaluation Report

## Test Results for Arabic & English Cross-Lingual RAG

| Evaluation Scenario | Source Document | Question Language | Correctness | Faithfulness | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Arabic Q&A over Arabic Doc** | Arabic Policy TXT | Arabic (`ar`) | **100%** | **98%** | Passed |
| **English Q&A over Arabic Doc** | Arabic Policy TXT | English (`en`) | **95%** | **96%** | Passed |
| **Arabic Q&A over English Doc** | Employee Handbook PDF | Arabic (`ar`) | **95%** | **95%** | Passed |
| **Arabic Unsupported Question** | Policy PDF | Arabic (`ar`) | **100%** (Not found returned) | **100%** | Passed |

---

## Supported Embedding Models
1. `sentence-transformers/all-MiniLM-L6-v2` (Default English)
2. `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Multilingual)
