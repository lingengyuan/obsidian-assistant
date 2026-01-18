# vNext.3 Baseline GAP Report

## Spec source and interpretation

- ROADMAP/SPEC was not found in this repo. The baseline is derived from the roadmap and full development docs in `dev-docs/` (both filenames are non-ASCII).
- vNext.3 baseline is interpreted as the v1.0 to v1.3 milestones plus the stable output contracts and schemas.

## Inventory (concise)

src/
  oka/
    __main__.py
    cli/
      main.py
    core/
      apply.py
      config.py
      doctor.py
      git_utils.py
      i18n.py
      index.py
      pipeline.py
      scoring.py
      storage.py
      watch.py
  core/ (legacy)
    analyzer.py
    quality_scorer.py
    similarity.py
  exporters/ (legacy)
    exporter.py
    report_generator.py
  main.py (legacy CLI)
  quality.py (legacy CLI)
  search.py (legacy CLI)
  similar.py (legacy CLI)

tests/
  test_*.py (unit + integration-style coverage)
  fixtures/sample_vault/

scripts/
  bench.py
  build_binary.py
  entrypoint.py
  smoke_binary.py

config files:
  pyproject.toml
  requirements.txt
  requirements-build.txt
  config/set_env.sh
  config/.claude/settings.local.json
  run.sh

## CLI entrypoints and outputs

- CLI entrypoint: `oka` -> `oka.cli.main:main` (`pyproject.toml`).
- Module entrypoint: `python -m oka` -> `src/oka/__main__.py` -> `oka.cli.main:main`.
- Commands: `run`, `doctor`, `rollback`, `watch`.
- Output paths (cwd-relative): `reports/health.json`, `reports/action-items.json`, `reports/run-summary.json`, `reports/report.md`, `reports/runs/<run_id>/run-log.json`, `reports/runs/<run_id>/patches/`, `reports/runs/<run_id>/backups/`, `reports/runs/<run_id>/conflicts/`.
- Cache/locks: `cache/index.sqlite`, `locks/write-lease.json`, `locks/offline-lock.json`.

## GAP analysis (vNext.3 baseline)

### DONE

- CLI skeleton with `oka run`, `oka doctor`, `oka watch`, `oka rollback` implemented in `src/oka/cli/main.py`.
- Stable outputs: health/action-items/run-summary/report written by `src/oka/core/pipeline.py` and `src/oka/cli/main.py`.
- `--json` output and performance summary implemented in `src/oka/cli/main.py`.
- Explainable scoring with quantile normalization in `src/oka/core/scoring.py`.
- Recommendations and merge preview generation in `src/oka/core/pipeline.py`.
- Apply flow with write lease, quiet window, offline lock, atomic writes, conflicts, and rollback in `src/oka/core/apply.py`.
- Incremental SQLite index and fast-path in `src/oka/core/index.py` and `src/oka/core/pipeline.py`.
- Bench tooling in `scripts/bench.py`.

### TODO (with target module)

- Add `--dry-run` diff summary in the apply pipeline (`src/oka/cli/main.py`, `src/oka/core/apply.py`).
- Promote `add_frontmatter_fields` action items to Class A so they can be applied (`src/oka/core/pipeline.py`).
- Align `run-summary.json` schema to include sync and git sections (`src/oka/core/pipeline.py`, `src/oka/cli/main.py`).
- Align `run-log.json` schema to include top-level git metadata (`src/oka/core/apply.py`).
- Add doctor checks for plugin frontmatter field conflicts (`src/oka/core/doctor.py`).
- Implement config default layering with a defaults file (`src/oka/core/config.py`, new defaults file under `src/oka/config/`).
- Implement optional write-time normalization for encoding/line endings (`src/oka/core/apply.py`).
- Add explicit integration/perf test suites and golden regression diff harness (`tests/integration/`, `tests/perf/`).

## Proposed module map (short)

- v1.0 baseline: `src/oka/cli/main.py`, `src/oka/core/pipeline.py`, `src/oka/core/doctor.py`.
- v1.1 recommenders: `src/oka/core/pipeline.py`, `src/oka/core/scoring.py`.
- v1.2 apply/rollback: `src/oka/core/apply.py`, `src/oka/cli/main.py`.
- v1.3 incremental + bench: `src/oka/core/index.py`, `src/oka/core/pipeline.py`, `scripts/bench.py`.
- v1.4 pruning + partial rollback: `src/oka/core/storage.py`, `src/oka/core/apply.py`, `tests/`.
- v1.5 starvation/offline lock: `src/oka/core/apply.py`.
- v1.6 watch + fast path: `src/oka/core/watch.py`, `src/oka/core/pipeline.py`.
- v2.0 git policy + B1: `src/oka/core/git_utils.py`, `src/oka/core/apply.py`.
- v2.3 single-file dist: `scripts/build_binary.py`, `scripts/smoke_binary.py`, docs updates.
