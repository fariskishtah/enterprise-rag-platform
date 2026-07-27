# Public demo video and screenshot plan

Target length: **90–120 seconds**. Use only non-sensitive fixture content and a short,
licensed Arabic MP3/MP4. Do not fabricate screenshots or claim a cloud benchmark that was
not measured.

## Recording script

| Time | Screen/action | Narration cue |
| --- | --- | --- |
| 0:00–0:08 | Public landing page | “EnterpriseRAG turns documents and recordings into grounded Arabic and English answers with inspectable evidence.” |
| 0:08–0:15 | Select **Try the demo**, show password-only login | “The public environment is protected by an expiring demo session and warns against sensitive uploads.” |
| 0:15–0:23 | Dashboard → **Knowledge** → create a knowledge base | “I’ll create a temporary, quota-controlled research workspace.” |
| 0:23–0:34 | **Add knowledge**, upload an English or Arabic PDF | “The intake validates the file, extracts its structure, chunks it, and builds the multilingual index.” |
| 0:34–0:48 | **Research chat**, ask an Arabic question | “The Arabic query retrieves across the indexed source and returns an answer in RTL.” |
| 0:48–0:57 | Expand the citation and page reference | “The answer stays connected to the exact supporting passage; citations still need human checking.” |
| 0:57–1:05 | Ask an unsupported question | “When evidence is missing, the intended behavior is an explicit insufficient-evidence response.” |
| 1:05–1:18 | Upload a short Arabic MP3/MP4 directly | “Direct media upload is the reliable path. faster-whisper produces a timestamped Arabic transcript locally.” |
| 1:18–1:29 | Media page: transcript, timestamp, summary/intelligence | “Transcript search, timestamps, chapters, and media intelligence remain grounded in the recording.” |
| 1:29–1:38 | Settings limits and one-heavy-request state | “On the 4 GB CPU host, uploads and queues are bounded and only one heavy model task runs at once.” |
| 1:38–1:50 | README architecture diagram and GitHub | “The full React, FastAPI, SQLite, Hugging Face, backup, cleanup, and AWS deployment design is documented on GitHub.” |

If CPU processing makes the take exceed 120 seconds, pre-process the fixture in the same
real demo environment, then record the navigation and results without implying that the
processing happened instantly.

## Screenshot checklist

- [ ] Landing desktop — 1440 × 1000, public-demo notice visible.
- [ ] Landing mobile — 390 × 844, hero and Try the demo action visible.
- [ ] Demo login — 1200 × 900, no password or cookie shown.
- [ ] Dashboard/workspace — 1440 × 1000, non-sensitive fixture names.
- [ ] Upload terminal success — 1440 × 1000, source status visible.
- [ ] Arabic answer — 1440 × 1000, RTL answer and citation visible.
- [ ] Unsupported question — 1440 × 1000, insufficient-evidence state visible.
- [ ] Document citation — 1440 × 1000, page/passage highlight.
- [ ] Direct media transcript — 1440 × 1000, Arabic timestamps visible.
- [ ] Media intelligence — 1440 × 1000, summary and one timestamp citation.
- [ ] Settings/limits — 1440 × 1000, queue and quota values.
- [ ] Architecture/GitHub — 1440 × 1000, Mermaid diagram and limitations.

Before publishing, inspect every image for passwords, tokens, cookies, local paths, personal
names, browser autofill, IP addresses, shell history, and private document content.
