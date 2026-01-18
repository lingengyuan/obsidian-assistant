# vNext.3 Dev Setup

## Prereqs

- Python 3.8+ (3.11 recommended)
- Git

## Install

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

python -m pip install -e ".[dev]"
```

## Run CLI

```bash
python -m oka --help
python -m oka run --vault /path/to/vault
```

## Tests

```bash
pytest -q
pytest tests/integration/ -q
pytest tests/perf/ -q

$env:COVERAGE_FILE = "$env:TEMP\\coverage.phase0"
pytest --cov=src --cov-report=term-missing
```

## Lint and format

```bash
ruff check src tests
black --check src tests
```

## Type checking

```bash
mypy src
```

## Bench (optional)

```bash
python scripts/bench.py
```

## Phase0 gates (M0.1)

- Unit tests + smoke integration/perf + lint/typecheck + coverage.
- Golden regression diffs are introduced in M2 (not required in M0.1).
- `run-summary.json` and `run-log.json` are produced by `oka run` (not by smoke tests).
