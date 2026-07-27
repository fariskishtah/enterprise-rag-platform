# Demo data guide

EnterpriseRAG includes an authenticated sample-workspace seeder at
`POST /api/v1/demo/seed`. There is no landing-page seed button in the current release.

The endpoint creates two clearly labeled UTF-8 TXT fixtures:

1. `Employee_Handbook_2026.txt` — remote-work, expense, and PTO sample policy passages.
2. `Arabic_Corporate_Policy.txt` — Arabic remote-work and leave sample passages.

It stores the real fixture files, creates real chunks and embeddings with the configured
embedding provider, and adds two unscored evaluation cases. It does not create fabricated
evaluation runs, feedback, benchmark values, PDF/OCR/DOCX results, or media transcripts.
The normal public-demo expiry policy applies to the seeded workspace.
