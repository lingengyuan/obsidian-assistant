# Obsidian Assistant vNext.3 Implementation Plan (Final)

## 0. Spec Reference (MUST)
- Canonical SPEC: `docs/vnext3/SPEC.md`
- This implementation plan MUST not contradict SPEC.
- Any deviation MUST be documented by updating SPEC via PR.

## 1. Target Outcomes (What “Done” Means)
Deliver vNext.3 with:
1) One-command UX:
   - `oka run --vault <path>` generates reports (default read-only)
   - `oka run --vault <path> --apply` performs writes (Class A only), guarded by preview confirmation
   - `oka watch --vault <path>` keeps index warm; `run --apply` becomes near-instant
   - `oka rollback <run_id>` supports full + partial rollback (files/actions + intersection)
   - `oka doctor --vault <path>` diagnostics + safe fixes per SPEC
2) Safety:
   - Default read-only; writes only with `--apply`
   - Apply preview confirmation (global + per-file menu c/d/r/s/y/n)
   - Hash/base_hash checks + conflicts isolation
   - Git policy integration (dirty check + auto-commit optional/required per SPEC)
3) Observability:
   - `reports/runs/<run_id>/run-summary.json` (schema fixed; includes stages, met_sla, errors, degraded, fallbacks)
   - `reports/runs/<run_id>/run-log.json` (action-level logs + preview_decisions)
   - `reports/runs/<run_id>/conflicts/*` (typed conflicts)
4) Performance:
   - Incremental runs fast (cache hit high); throttled I/O; low memory
   - SLA measured as “target threshold” (NOT real percentile). `met_sla` = (actual <= target).
5) No LLM in core engine:
   - Dictionary bootstrap can be external/manual; tool remains deterministic.

---

## 2. Codex Operating Rules (Hard Constraints)
During this project:
- Human does ONLY:
  1) Paste the prompt to Codex
  2) Select reasoning level requested by the prompt
- Codex MUST do everything else:
  - create/modify files
  - run commands/tests
  - fix failures
  - produce artifacts
  - open PR(s)
- Codex MUST NOT ask for human assistance for running commands, editing files, or verifying outputs.
- Codex MUST keep outputs deterministic; golden tests must pass.

---

## 3. Reasoning Level Guide (What to Select in Codex)
Use exactly:
- **Low**: wiring, scaffolding, docs placement, CI plumbing, dependency additions, directory creation
- **Medium**: implementing deterministic logic with edge cases, CLI flows, schemas, unit/integration tests
- **High**: architectural changes affecting concurrency, indexing strategy, performance optimizations, race mitigation

Unless explicitly stated otherwise in a milestone, use **Medium**.

---

## 4. Repo Structure Targets (MUST exist by end)
- `docs/vnext3/SPEC.md` (canonical spec)
- `docs/vnext3/IMPLEMENTATION.md` (this file)
- `docs/vnext3/GAP.md` (gap tracking from Codex validation)
- `tests/integration/` (integration suite)
- `tests/perf/` (performance suite)
- `tests/fixtures/test_vault/` + `manifest.json`
- `tests/golden/` (golden outputs)
- dev tooling installed via extras: `pip install -e ".[dev]"`

---

## 5. Validation Gates (No Human Involvement)
At each milestone, Codex MUST run and pass:
- Unit: `pytest tests/ -q`
- Integration: `pytest tests/integration/ -q`
- Perf: `pytest tests/perf/ -q`
- Lint: `ruff check src tests`
- Format: `black --check src tests`
- Types: `mypy src`
- Coverage: `pytest --cov=src --cov-report=term-missing`
- CLI smoke: `python -m oka --help` and `python -m oka run --help`

If a directory does not exist yet (e.g. integration/perf in early milestones), the milestone prompt must create it and include minimal passing tests.

---

## 6. Milestones Overview
- **M0.2** Dev Tooling & Test Gates Bootstrap (fix missing ruff/black/mypy/pytest-cov; create integration/perf suites)
- **M0.3** Canonical Docs Placement (SPEC/IMPLEMENTATION/GAP wiring; ROADMAP pointer)
- **M0.4** Test Vault & Manifest (fixtures for edge cases)
- **M0.5** Golden Outputs Framework (deterministic outputs + golden comparison tests)
- **M1.0** P0 Delivery: Related block engine + reasoning output + preview framework
- **M1.1** P0 Delivery: run-summary/run-log schema finalization + conflicts typing
- **M1.2** P0 Delivery: rollback (full + partial + intersection) + rollback preview truncation rules
- **M1.3** P0 Delivery: watch backoff/self-heal + recovered tracking + debounce controls
- **M1.4** P0 Delivery: Git policy integration (dirty enforcement + auto-commit messages)
- **M2.0** P1 Enhancements: confidence_hint + preview_decisions enum + lazy stub ref tracking (auto)
- **M3.0** Scale Hardening: IO throttle tuning + benchmark command + regression thresholds
- **M4.0** CI: multi-OS matrix + artifacts upload + golden enforcement

---

# 7. Milestone Prompts (Paste into Codex)

> IMPORTANT: Each prompt is self-contained. Paste exactly, select the specified reasoning, then do nothing else.

---

## M0.2 — Dev Tooling & Test Gates Bootstrap
**Codex Reasoning:** Low

### Prompt (paste to Codex)
```md
## CONTEXT
You are implementing Obsidian Assistant vNext.3. Follow repository constraints: the human will only paste prompts and select reasoning; you must do all operations.

## TASK
1) Ensure the repo supports dev tooling via a single command:
   - `pip install -e ".[dev]"` installs ruff, black, mypy, pytest-cov (and any other needed dev deps).
   - Add/update pyproject.toml (preferred) or requirements extras accordingly.

2) Create missing test suite directories so validation gates do not fail:
   - Create `tests/integration/` and `tests/perf/` with minimal placeholder tests that pass.
   - Add README files inside each describing what belongs there.

3) Ensure the following commands pass locally:
   - pytest tests/ -q
   - pytest tests/integration/ -q
   - pytest tests/perf/ -q
   - ruff check src tests
   - black --check src tests
   - mypy src
   - pytest --cov=src --cov-report=term-missing

4) If any tool requires configuration (ruff/black/mypy), add minimal config to pyproject.toml.
   - Do NOT relax quality gates excessively; keep sane defaults.
   - Keep formatting deterministic.

## VALIDATION
Run all commands above and fix failures until green.

## OUTPUT
- Commit with message: chore(dev): bootstrap dev tooling and test gates
- Include summary in commit body: installed tools, created suites, and command outputs (brief).
````

---

## M0.3 — Canonical Docs Placement & Pointers

**Codex Reasoning:** Low

### Prompt

```md
## TASK
1) Ensure canonical spec path exists:
   - docs/vnext3/SPEC.md must exist (if currently elsewhere, move/copy into this location).
   - If there are older docs (e.g., 完整开发文档.md / Obsidian Assistant 路线图.md), keep them but mark as deprecated, pointing to docs/vnext3/SPEC.md.

2) Ensure docs/vnext3/IMPLEMENTATION.md exists (this file). If missing, create it and include milestone structure (even if incomplete for now).

3) Create docs/vnext3/GAP.md:
   - It must be a living checklist of gaps found by validation (schema TODOs, missing suites, etc.).
   - Seed it by running validation and writing what fails/what is missing.

4) Add root ROADMAP.md as a pointer only:
   - It must link to docs/vnext3/SPEC.md and docs/vnext3/IMPLEMENTATION.md and docs/vnext3/GAP.md.

## VALIDATION
- grep: only docs/vnext3/SPEC.md claims canonical status for vNext.3.
- ROADMAP.md exists and links correctly.

## OUTPUT
Commit message: docs(vnext3): add canonical spec pointers and gap tracking
```

---

## M0.4 — Test Vault Fixtures & Manifest

**Codex Reasoning:** Medium

### Prompt

```md
## CONTEXT
Implement vNext.3 tests using a deterministic test vault.

## TASK
1) Create `tests/fixtures/test_vault/` with ~50 markdown notes and subfolders:
   - Daily/ (10 daily notes, e.g. Daily/2026-01-01.md)
   - Notes/ (30 notes)
   - Projects/ (5 notes)
   - Archive/ (5 notes)
2) Cover edge cases (at least the below counts):
   - multiple_related_headings: 3
   - missing_anchor: 2
   - user_deleted_related_block: 2
   - hash_mismatch_simulation: 2 (prepare baseline + modified variant file if needed)
   - special_char_title_chars: 5 (include [], |, etc.)
   - chinese_only: 3
   - large_file_over_1mb: 2 (repeat content; must remain valid markdown)
   - empty_file: 2
   - yaml_frontmatter_invalid: 2 (for doctor/errors pipeline)
3) Add `tests/fixtures/test_vault/manifest.json` describing each file’s expected traits:
   - has_frontmatter, edge_case type, expected behavior notes
4) Add a unit test `tests/test_fixtures_manifest.py` that validates:
   - manifest references all files
   - counts meet requirements
   - paths are valid

## VALIDATION
- pytest tests/test_fixtures_manifest.py -q

## OUTPUT
Commit: test(fixtures): add deterministic test vault and manifest
```

---

## M0.5 — Golden Outputs Framework

**Codex Reasoning:** Medium

### Prompt

```md
## TASK
1) Create `tests/golden/` with initial golden files:
   - run-summary-cold-start.json
   - run-log-sample.json
   - reasoning-output-sample.txt
   - related-block-sample.md
2) Create a golden comparison helper:
   - stable normalization (e.g. ignore timestamps, run_id if needed)
   - strict schema checks for required fields
3) Add tests in `tests/integration/test_golden_outputs.py`:
   - runs `oka run --vault tests/fixtures/test_vault --dry-run` to generate outputs
   - compares outputs to golden with normalized diff
4) Ensure determinism:
   - If run_id is generated, normalize it in compare layer
   - Do not allow random ordering; sort lists deterministically

## VALIDATION
- pytest tests/integration/test_golden_outputs.py -q

## OUTPUT
Commit: test(golden): add golden outputs framework and deterministic comparisons
```

---

## M1.0 — P0: Related Block Engine + Reasoning Output + Preview Framework

**Codex Reasoning:** Medium

### Prompt

```md
## CONTEXT
Implement vNext.3 core “Related” capability strictly following docs/vnext3/SPEC.md.

## TASK (MUST)
1) Implement Related block contract engine:
   - Anchor-based block contract (<!-- oka:related:v1 -->)
   - Heading match: '## Related'
   - Anchor distance rule (<= 3 lines)
   - Multiple Related headings => conflict (do not auto-update)
   - Missing anchor => conflict (treat as user-managed)
   - User deleted block => interactive rebuild confirmation path
   - Hash mismatch => conflict + diff artifact
   - Replace range: from anchor line to next H2 or EOF; preserve heading line

2) Implement reasoning output (user-friendly):
   - Overall score + semantic label thresholds (Very High/High/Medium/Low)
   - Why recommended: breakdown (content_sim/link_overlap/path_tag_boost)
   - Shared keywords mapping to tags where possible (e.g. 数据库(#database))
   - Top evidence extraction MUST use “方案C” (shared keywords list) with deterministic ordering
   - N/A downgrade rules must be explicit and non-silent

3) Implement preview interaction framework:
   - Global summary prompt (y/n/preview)
   - Per-file menu: [c] new content, [d] diff, [r] reasoning, [s] skip, [y] apply, [n] abort
   - Record preview decisions in run-log with enum-like values

4) Tests:
   - Create unit tests covering all conflict types and idempotency
   - Add golden text test for reasoning output sample(s)

## VALIDATION
- pytest tests/ -q
- pytest tests/integration/ -q
- Update golden outputs if spec requires, but preserve determinism.

## OUTPUT
Commit: feat(vnext3): implement related block engine, reasoning, and preview flow
```

---

## M1.1 — P0: run-summary/run-log Schema Finalization + Typed Conflicts

**Codex Reasoning:** Medium

### Prompt

```md
## TASK
1) Finalize run-summary.json schema per SPEC:
   - timing_ms.total + timing_ms.stages (scan/parse/index actual/target/met)
   - sla: mode, target_ms, met_sla, note="target threshold (not percentile)"
   - cache stats: skipped files, hit rate
   - io throttle settings and observed counters
   - errors (active + recovered), degraded_files, fallbacks
   - conflicts summary: count + types map (e.g. multiple_related_headings, hash_mismatch, missing_anchor, user_deleted, anchor_too_far, base_hash_changed)

2) Finalize run-log.json schema:
   - actions list with action_id, file path, type, base_hash, before/after hashes
   - preview_decisions array with decision enum + timestamp + reason
   - support rollback intersection filtering later

3) Implement conflicts artifacts generation:
   - conflicts/<type>/<file>.diff with unified diff formatting
   - include “how to apply with system diff/patch” hint line in README inside conflicts/

4) Update integration tests to validate schema keys strictly.

## VALIDATION
- pytest tests/integration/ -q
- golden outputs updated only if necessary, with deterministic normalization.

## OUTPUT
Commit: feat(observability): finalize run summary/log schemas and typed conflicts
```

---

## M1.2 — P0: Rollback (Full + Partial + Intersection) + Rollback Preview Truncation

**Codex Reasoning:** Medium

### Prompt

```md
## TASK
1) Implement rollback commands:
   - Full: oka rollback <run_id>
   - Partial by files: --files "a.md,b.md"
   - Partial by actions: --actions "add_tags,append_related_block"
   - Combined filters MUST be intersection (files ∩ actions)
2) Rollback preview:
   - --preview required or default preview before execution
   - show intersection stats and list action_ids
   - truncation rule: show only changed keys; unchanged keys show counts; [d] shows full diff
3) Conflict handling:
   - base_hash mismatch => do not apply rollback; write conflicts artifact and continue
4) Tests:
   - unit tests for filtering intersection
   - integration test: apply -> rollback -> verify files restored
   - partial rollback test: keep related, rollback tags, etc.

## VALIDATION
- pytest tests/ -q
- pytest tests/integration/ -q

## OUTPUT
Commit: feat(rollback): add full and partial rollback with preview and conflict safety
```

---

## M1.3 — P0: Watch Backoff/Self-heal + Debounce + Recovered Tracking

**Codex Reasoning:** High (concurrency + long-running behavior)

### Prompt

```md
## TASK
1) Implement watch behavior:
   - maintain index incrementally
   - exponential backoff for parse failures with config defaults:
     initial_delay_sec=10, max_delay_sec=600, max_retries=5
   - skipped files recheck interval 3600 sec
   - if mtime/hash changes, allow immediate retry BUT with:
     immediate_retry_debounce_sec=5
     immediate_retry_max_concurrent=3
2) run-summary reporting:
   - errors.active and errors.recovered
   - first_failed_at, last_failed_at, recovered_at, total_failed_duration_sec
3) Ensure watch does not starve Obsidian:
   - apply IO throttling
   - limit CPU and memory where possible; document measurement method (psutil cpu_percent interval=10)
4) Tests:
   - integration: run watch for short window, modify file(s), verify index updated
   - deterministic: do not rely on flaky timing; use controlled file events or mocking where needed

## VALIDATION
- pytest tests/integration/ -q
- no flaky tests: run integration watch test multiple times in CI-friendly manner.

## OUTPUT
Commit: feat(watch): add backoff, debounce retries, and self-healing reporting
```

---

## M1.4 — P0: Git Policy Integration + Auto-commit Message Format

**Codex Reasoning:** Medium

### Prompt

```md
## TASK
1) Implement git policy options per SPEC:
   - require_clean (default)
   - allow_dirty
   - auto_stash (optional)
   - auto_commit (pre-apply checkpoint + post-apply summary)
2) Enforce:
   - if require_clean and dirty => block apply with actionable message
   - if auto_commit enabled => produce semantic commit messages including run_id, change counts, summary path, and rollback command
3) Tests:
   - mock git repo fixture with dirty status
   - verify behaviors per policy
   - ensure messages contain:
     "oka: checkpoint before apply [run:<id>]"
     "oka: apply ... [run:<id>]" + Summary path + "To rollback: oka rollback <run_id>"

## VALIDATION
- pytest tests/ -q
- integration apply flow under git repo fixture

## OUTPUT
Commit: feat(git): enforce git policy and add semantic auto-commit messages
```

---

## M2.0 — P1 Enhancements Bundle

**Codex Reasoning:** Medium

### Prompt

```md
## TASK
Implement the following P1 enhancements:
1) confidence_hint in dict suggestions:
   - based on co_occurring ratio with sample-size penalty:
     if keyword_freq < 3 => hint=0.60
     else ratio>=0.60 => 0.90+
     ratio in [0.35,0.60) => 0.75-0.89
     else => 0.60
     optional +0.05 if freq>=10 (cap 0.99)
   - add confidence_hint field to template
2) preview_decisions enum values:
   - applied, user_skipped, user_aborted, preview_timeout (if exists), auto_applied
3) rollback preview details:
   - show changed keys only; unchanged counts; [d] full diff
4) stub reference tracking lazy mode:
   - config: lazy_reference_tracking = auto/always/never
   - auto: vault_size < 5GB => realtime; >=5GB => lazy
   - in lazy mode, only compute stub reference counts during prune-stubs
5) Improve reasoning readability:
   - score labels + evidence section (still scheme C for evidence)
   - map shared keywords to tags if available

## VALIDATION
- unit + integration suites
- golden outputs updated if required (deterministically)

## OUTPUT
Commit: feat(p1): implement confidence hints, preview enums, rollback details, and lazy stub tracking
```

---

## M3.0 — Scale Hardening + Benchmark

**Codex Reasoning:** High

### Prompt

```md
## TASK
1) Add a benchmark command:
   - `oka benchmark --vault <path>` runs controlled runs and outputs benchmark report json
   - MUST clearly state: SLA in run-summary is target threshold, not percentile measurement
2) Add perf tests in tests/perf/:
   - cold-start run on fixture vault; assert met_sla true under target threshold in CI
   - incremental run speed: second run should be faster than first (relative assertion, not absolute ms)
3) IO throttling verification:
   - ensure throttle settings appear in run-summary and counters increase when throttling is active
4) Ensure all perf tests are deterministic and CI-safe.

## VALIDATION
- pytest tests/perf/ -q

## OUTPUT
Commit: perf: add benchmark command and CI-safe performance tests
```

---

## M4.0 — CI (GitHub Actions) + Artifacts

**Codex Reasoning:** Low

### Prompt

```md
## TASK
1) Add GitHub Actions workflow:
   - triggers on push and PR to main
   - matrix: OS ubuntu/macos/windows, Python 3.10/3.11/3.12
   - steps: install, pip install -e ".[dev]", run unit+integration+perf, ruff, black, mypy, coverage
2) Golden outputs enforcement:
   - fail if golden diffs occur unexpectedly (or require explicit update procedure)
3) On failure, upload artifacts:
   - run-summary.json, run-log.json, conflicts/ as workflow artifacts
4) Keep runtime reasonable.

## VALIDATION
- workflow yaml passes schema checks
- local run commands match CI steps

## OUTPUT
Commit: ci: add multi-platform test matrix with artifacts
```

---

# 8. Deliverables Checklist (Final Acceptance)

Codex must ensure:

* All validation commands pass locally
* CI green on PR
* Canonical docs present and linked:

  * docs/vnext3/SPEC.md
  * docs/vnext3/IMPLEMENTATION.md
  * docs/vnext3/GAP.md
  * ROADMAP.md points to them
* tests suites exist and pass:

  * unit/integration/perf
* golden outputs deterministic and enforced
* run-summary/run-log schemas stable and documented (in SPEC; referenced)

---

# 9. PR Strategy (Recommended)

Codex should open PRs in this order:

1. chore(dev): bootstrap dev tooling and test gates
2. docs(vnext3): add canonical spec pointers and gap tracking
3. test(fixtures): add deterministic test vault and manifest
4. test(golden): add golden outputs framework
5. feat(vnext3): related + reasoning + preview
6. feat(observability): schemas + conflicts
7. feat(rollback): rollback filters + preview
8. feat(watch): backoff + debounce + recovered
9. feat(git): git policy + auto-commit
10. feat(p1): enhancements
11. perf: benchmark + perf tests
12. ci: github actions

Each PR must include:

* tests passing
* references to SPEC sections implemented

---


