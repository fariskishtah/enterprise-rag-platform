# Contributing to EnterpriseRAG

Thank you for your interest in contributing to EnterpriseRAG!

## Pull Request Guidelines
1. Fork the repository and create a feature branch (`git checkout -b feature/amazing-feature`).
2. Ensure code passes all pytest unit tests (`cd backend && .venv/bin/python -m pytest tests/`).
3. Ensure ruff linting passes (`cd backend && .venv/bin/ruff check app/ tests/`).
4. Ensure frontend builds cleanly (`cd frontend && npx tsc --noEmit && npm run build`).
5. Open a Pull Request against `main` using our PR template.
