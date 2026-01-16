# Development Baseline

This document captures the current code structure, existing entrypoints, and the
scaffolded oka CLI used for ongoing development.

## Current code structure (legacy)

Source layout:

- `src/main.py` - Legacy CLI entrypoint for the original analyzer.
- `src/quality.py` - Legacy quality scoring CLI.
- `src/search.py` - Legacy search CLI.
- `src/similar.py` - Legacy similarity CLI.
- `src/core/` - Analyzer and scoring logic used by legacy commands.
- `src/exporters/` - Report and data export utilities.

These entrypoints remain available for now, but new work should target the `oka`
CLI and the v1+ contracts.

## Current outputs (legacy)

By default, legacy commands write outputs under `reports/` (overridable via
`REPORT_OUTPUT`):

- `reports/knowledge-report-YYYY-MM-DD.md`
- `reports/quality-report-YYYY-MM-DD.md`
- `reports/analysis-data-YYYY-MM-DD.json`
- `reports/notes-YYYY-MM-DD.csv`
- `reports/orphan-notes-YYYY-MM-DD.csv`
- `reports/tags-YYYY-MM-DD.csv`
- `reports/links-YYYY-MM-DD.csv` (optional via CSV types)

## oka CLI (scaffold)

The new CLI is a scaffold to align with the roadmap. It does not perform
analysis yet, but it is the canonical entrypoint for new development.

Run in-place without installation:

```bash
python -m oka --help
python -m oka run --help
python -m oka doctor --help
```

Install an editable console script for `oka`:

```bash
python -m pip install -e .
oka --help
```

## Directory contract (stable)

The v1+ outputs live under these directories. The CLI scaffold creates the
top-level directories but does not populate files yet.

```
reports/
  health.json
  report.md
  action-items.json
  run-summary.json
  runs/<run_id>/
    run-log.json
    patches/
    backups/
    conflicts/
      <file>.diff
      <file>.note
      HOWTO.txt
cache/
  index.sqlite
locks/
  write-lease.json
  offline-lock.json
```

## Tests and fixtures

Run the test suite:

```bash
pytest -q
```

Sample fixtures live under `tests/fixtures/sample_vault/`.
