# User Feedback System Architecture

The feedback system collects user ratings on generated answers and converts low-scoring responses into evaluation benchmark test cases.

---

## Feedback-to-Evaluation Pipeline

```mermaid
flowchart LR
    USER["User in Chat UI"] --> FEEDBACK["Click Helpful / Unhelpful & Select Category"]
    FEEDBACK --> STORE["Store Feedback Entry in DB"]
    STORE --> ANALYTICS["Feedback Analytics Page"]
    
    ANALYTICS --> CONVERT{"Convert Complaint to Eval Case?"}
    CONVERT -- Yes --> NEW_CASE["Create EvaluationCase Entry"]
    NEW_CASE --> DATASET["Add to Ground-Truth Benchmark Dataset"]
```

---

## Categorized Complaint Categories
- `helpful`: Answer was accurate and well-cited.
- `incorrect`: Answer contained factual inaccuracies.
- `incomplete`: Missing key details present in source document.
- `wrong_citation`: Citation pointed to irrelevant passage.
- `too_slow`: Request exceeded acceptable response latency.
- `other`: User comment feedback.
