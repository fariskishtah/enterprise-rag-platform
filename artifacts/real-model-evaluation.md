# Real local model evaluation

Result: 3/3 passed

- Generation: `Qwen/Qwen2.5-0.5B-Instruct`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Device: `mps`
- Model weights: local cache only
- Document processing + first embedding load: 4159.4 ms

| Question | Answer | Support | Pass | Total latency |
| --- | --- | --- | --- | --- |
| How many remote days are employees allowed per week? | Employees may work remotely for up to three days per week. | fully_supported | PASS | 2951.7 ms |
| How much is the home-office allowance and when is it available? | The home-office allowance is GBP 600 and becomes available after 30 days of employment. | fully_supported | PASS | 1058.8 ms |
| Who is the CEO? | The supplied documents do not contain enough information to answer this question. | missing_answer | PASS | 45.1 ms |
