# Golden Regression Outputs

This document describes the golden regression framework for vNext.3.

## Scope

Golden artifacts cover:

- `run-summary` (cold + incremental)
- `run-log` sample
- `conflicts` summary
- reasoning output sample
- related block samples

## Normalization rules

To avoid false diffs, the test harness normalizes unstable fields:

- `run_id` and any embedded run ID strings -> `<RUN_ID>`
- timestamps (`generated_at`, `started_at`, `ended_at`, etc.) -> `<TIMESTAMP>`
- path separators normalized to `/`
- absolute paths rewritten to `<BASE_DIR>` or `<VAULT>`
- timing fields ending in `_ms` are set to `0`

## Updating golden files

Golden files live under `tests/golden/`. To refresh them:

```bash
python tools/update_golden.py --yes
```

This script:

1) Copies `tests/fixtures/test_vault` to a temp directory
2) Runs `oka run` (cold), `oka run` (incremental), and `oka run --apply --yes`
3) Normalizes outputs and writes golden files

## CI behavior

Golden regression tests run as integration tests. Any change produces a unified diff in the test failure output, so updates must be intentional and reviewed.
