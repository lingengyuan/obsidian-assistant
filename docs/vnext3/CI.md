# CI

This project runs a cross-platform CI matrix to validate the vNext.3 test gates.

## Workflow

Workflow file: `.github/workflows/test.yml`

Matrix:
- OS: ubuntu-latest, macos-latest, windows-latest
- Python: 3.10, 3.11, 3.12

Steps:
- Install dev dependencies via `pip install -e ".[dev]"`.
- Lint: `ruff check src tests`
- Format: `black --check src tests`
- Typecheck: `mypy src`
- Unit tests with coverage: `pytest tests/ -q --cov=oka --cov-report=term-missing --cov-fail-under=90`
- Integration tests: `pytest tests/integration/ -q`
- Perf tests: `pytest tests/perf/ -q`

## Artifacts

On failure, CI uploads:
- `reports/**` (pytest logs and coverage data)
- `.pytest-temp/**` (temp work dirs containing run-summary/run-log outputs)

Pytest uses `--basetemp=.pytest-temp` so integration outputs live under the repo and can be collected as artifacts.
