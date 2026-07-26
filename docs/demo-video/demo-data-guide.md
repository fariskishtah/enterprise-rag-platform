# Demo Data Guide

EnterpriseRAG includes an automated demo workspace seeder accessible via `POST /api/v1/demo/seed` or the UI button **Load Demo Workspace**.

## Included Fixture Sources
1. **Employee Handbook PDF**: Standard corporate policy rules (remote work, PTO, expense limits).
2. **Methodology Comparison TXT**: Two contrasting engineering approaches (acoustic vs thermal monitoring).
3. **Scanned Inspection Report PDF**: Image-based PDF page exercising Tesseract OCR fallback.
4. **Financial Summary DOCX**: Multi-column table document exercising `pdfplumber` table extraction.
5. **Arabic Policy Document TXT**: Modern Standard Arabic policy for cross-lingual QA.
6. **Video Recording Fixture**: Short MP4 lecture with Whisper timestamp alignment.
