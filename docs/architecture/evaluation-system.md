# Evaluation System Architecture

EnterpriseRAG includes an empirical evaluation pipeline to benchmark answer correctness, citation validity, faithfulness, and system latency.

---

## Evaluation Workflow

```mermaid
flowchart TD
    DATASET["Evaluation Dataset (Ground-Truth Test Cases)"] --> RUNNER["Evaluation Service Runner"]
    RUNNER --> RAG["Execute RAG Pipeline (Custom / LangChain)"]
    
    RAG --> METRICS["Calculate Metrics"]
    
    subgraph Metrics Calculation
        CORRECT["Answer Correctness (BLEU/ROUGE & Key Token Match)"]
        FAITHFUL["Faithfulness (Claim Verifier Support Ratio)"]
        CIT_ACC["Citation Accuracy (Expected vs Returned Chunks)"]
        LATENCY["Latency Metrics (Median, P95, Total ms)"]
    end
    
    METRICS --> STORE["Persist EvaluationRun & Results to DB"]
    STORE --> DASHBOARD["React Evaluation Dashboard UI"]
    DASHBOARD --> EXPORT["Export JSON / CSV / Markdown Reports"]
```

---

## Benchmark Metrics
- **Correctness**: Percentage of expected key facts present in generated answer.
- **Faithfulness**: Ratio of claims fully supported by citations.
- **Citation Accuracy**: Precision of citations relative to ground-truth passages.
- **P95 Latency**: 95th percentile response latency in milliseconds.
