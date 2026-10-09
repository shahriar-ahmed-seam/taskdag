# Contributing to TaskDAG

Thank you for your interest in contributing to TaskDAG. We maintain rigorous engineering, mathematical, and code hygiene standards.

## Code of Conduct

All contributors are expected to uphold professional, respectful collaboration.

## Multi-Agent GitHub Engineering Workflow

We enforce an issue-driven branch and pull request lifecycle:

1. File a GitHub Issue describing the problem, architectural need, and acceptance criteria.
2. Branch from `main` using descriptive prefixes (`feat/...`, `fix/...`, `docs/...`).
3. Write clean, modular code with complete test coverage.
4. Verify tests and linting:
   ```bash
   pytest -v
   ruff check src tests examples
   ```
5. Submit a GitHub Pull Request referencing the issue number with technical summary and verification output.

## Documentation Standards

- Zero emojis permitted in documentation, commit messages, or source code comments.
- Use RFC-style precise technical terminology.
- Provide mathematical formulations in standard LaTeX syntax when defining metrics.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```
