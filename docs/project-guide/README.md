# EnterpriseRAG practical project guide

This guide explains the repository as it exists now. It is written for a project owner who does not need to know every programming detail. Claims are tied to real files, routes, classes, or tests. Where the repository does not provide evidence, the guide says: **Not verified from the current codebase.**

## Start here

1. [Project overview](00-project-overview.md) — what the product does and how the parts fit together.
2. [Page-by-page guide](01-page-by-page-guide.md) — every frontend route, visible control, prerequisite, and manual test.
3. [Feature guide](02-feature-guide.md) — end-to-end flows for ingestion, search, RAG, media, evaluation, auth, operations, and course-only features.
4. [File map](03-file-map.md) — where to find the important code.
5. [API reference](04-api-reference.md) — all 60 backend operations, payloads, handlers, and test examples.
6. [Database guide](05-database-guide.md) — the 19 tables, relationships, lifecycle fields, and 4 migrations.
7. [Environment variables](06-environment-variables.md) — runtime, deployment, frontend, test, and course variables without secret values.
8. [Testing guide](07-testing-guide.md) — practical smoke, automated, security, backup, and deployment checks.
9. [Deployment guide](08-deployment-guide.md) — Docker, Nginx, AWS service files, persistence, backups, and the public request path.
10. [Limitations and risks](09-limitations-and-risks.md) — evidence-backed gaps and operating constraints.
11. [Current status](10-current-status.md) — fully implemented, configured, partial, experimental, placeholder, likely broken, and not-found classifications.

## Verified inventory

| Area | Count | How it was counted |
|---|---:|---|
| Frontend route patterns and aliases | 22 | Exact and dynamic paths in `frontend/src/App.tsx:110-164`; the unmatched 404 branch is not an extra route. |
| React page components | 15 | Files in `frontend/src/pages/`; one `LegalPage` serves three routes. |
| Backend API operations | 60 | FastAPI operations included through `backend/app/api/router.py:17-28`. |
| Database tables | 19 | SQLAlchemy `__tablename__` declarations in `backend/app/models/`. |
| Alembic migrations | 4 | `backend/migrations/versions/0001_...` through `0004_...`. |
| Automated test files | 30 | 20 backend `test_*.py`, 8 frontend unit-test files, and 2 Playwright specs. `backend/tests/conftest.py` is support code, not a test file. |
| Files in this guide | 12 | This README plus the 11 numbered documents above. |

## Reading conventions

- **Confirmed** means the behavior is present in the current code.
- **Configured** means the code exists but needs a model, binary, cookie, credential, or deployment setting.
- **Partial** means only part of the user flow exists.
- **Course-only** means it is under `course_demo/` and is not part of the React/FastAPI production workflow.
- Line references describe the current revision and may move after later edits.
- Example IDs such as `KB_ID` and `DOC_ID` are placeholders. Example secrets are intentionally fake.

## Recommended learning path

Read the overview first. Then use the pages in this order: landing and login, knowledge bases, source library, document detail, chat, video intelligence, compare and reports, evaluation, feedback, templates, settings. Keep the API and database guides open as references. Finish with deployment, limitations, and current status before operating a public instance.
