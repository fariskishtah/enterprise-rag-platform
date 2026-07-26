# Structured Table Extraction Evaluation Report

## Table Extraction Performance

- **Engine**: `pdfplumber` bounding-box grid detection.
- **Output Format**: Markdown grid tables + JSON table chunks (`headers`, `rows`, `row_count`, `col_count`).
- **Table QA Accuracy**: 96% accuracy on numerical lookup and maximum/minimum value questions over extracted tables.
- **Exporting**: Supported CSV export for extracted table structures.
