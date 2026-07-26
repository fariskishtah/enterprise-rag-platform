# Custom Engine vs LangChain Engine

This is a deterministic reproducible comparison. It does not claim that the small evaluation generator measures open-ended model quality.

| Metric | Custom | LangChain |
| --- | ---: | ---: |
| Correct policy cases | 6/6 | 6/6 |
| Average latency | 20.3 ms | 22.5 ms |
| Retrieval accuracy | 100% | 100% |
| Citation validity | 100% | 100% |
| Peak Python allocations | 3.7 MB | 9.4 MB |
| Reference implementation LOC | 590 | 717 |

| Question | Custom | LangChain | LangChain citations |
| --- | --- | --- | ---: |
| How many remote days are employees allowed per week? | PASS | PASS | 1 |
| Which days are designated collaboration days? | PASS | PASS | 1 |
| When can an employee request a fully remote arrangement? | PASS | PASS | 1 |
| Who must approve the fully remote arrangement? | PASS | PASS | 1 |
| How much is the home-office allowance and when is it available? | PASS | PASS | 1 |
| Who is the CEO? | PASS | PASS | 0 |

Retrieval uses the real deterministic policy PDF. Generation is deterministic so the comparison isolates engine behavior and remains suitable for CI.

Failure behavior: the custom engine uses support gates and post-processing; the LangChain engine uses validated Pydantic objects, bounded parser repair, and an explicit `not_found` field.
