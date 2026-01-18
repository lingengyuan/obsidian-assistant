from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
VAULT_SRC = REPO_ROOT / "tests" / "fixtures" / "test_vault"

sys.path.insert(0, str(REPO_ROOT))
from tools.golden_utils import (  # noqa: E402
    build_reasoning_sample,
    extract_related_block,
    json_dumps,
    normalize_json,
    summarize_conflicts,
)


def _run_cli(args: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    cmd = [sys.executable, "-m", "oka", *args]
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_text_equal(got: str, expected: str, label: str) -> None:
    if got == expected:
        return
    diff = list(
        _unified_diff(
            expected.splitlines(), got.splitlines(), fromfile="expected", tofile="got"
        )
    )
    raise AssertionError(f"{label} mismatch:\n" + "\n".join(diff))


def _unified_diff(
    expected: list[str], got: list[str], fromfile: str, tofile: str
) -> list[str]:
    import difflib

    return list(
        difflib.unified_diff(
            expected, got, fromfile=fromfile, tofile=tofile, lineterm=""
        )
    )


@pytest.mark.integration
def test_golden_regression(tmp_path: Path) -> None:
    assert GOLDEN_DIR.exists()
    assert VAULT_SRC.exists()

    vault_dir = tmp_path / "vault"
    work_dir = tmp_path / "work"
    shutil.copytree(VAULT_SRC, vault_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    _run_cli(["run", "--vault", str(vault_dir)], work_dir)
    cold_summary = _load_json(work_dir / "reports" / "run-summary.json")
    action_items = _load_json(work_dir / "reports" / "action-items.json")

    _run_cli(["run", "--vault", str(vault_dir)], work_dir)
    incremental_summary = _load_json(work_dir / "reports" / "run-summary.json")

    _run_cli(["run", "--vault", str(vault_dir), "--apply", "--yes"], work_dir)
    apply_summary = _load_json(work_dir / "reports" / "run-summary.json")
    run_id = apply_summary.get("run_id")
    run_log = _load_json(work_dir / "reports" / "runs" / str(run_id) / "run-log.json")

    normalized_cold = normalize_json(
        cold_summary, base_dir=work_dir, vault_dir=vault_dir
    )
    normalized_incremental = normalize_json(
        incremental_summary, base_dir=work_dir, vault_dir=vault_dir
    )
    normalized_run_log = normalize_json(run_log, base_dir=work_dir, vault_dir=vault_dir)

    expected_cold = GOLDEN_DIR / "run-summary-cold-start.json"
    expected_incremental = GOLDEN_DIR / "run-summary-incremental.json"
    expected_run_log = GOLDEN_DIR / "run-log-sample.json"

    _assert_text_equal(
        json_dumps(normalized_cold),
        expected_cold.read_text(encoding="utf-8"),
        "run-summary cold",
    )
    _assert_text_equal(
        json_dumps(normalized_incremental),
        expected_incremental.read_text(encoding="utf-8"),
        "run-summary incremental",
    )
    _assert_text_equal(
        json_dumps(normalized_run_log),
        expected_run_log.read_text(encoding="utf-8"),
        "run-log sample",
    )

    first_reason = next(
        (item for item in action_items.get("items", []) if item.get("reason")), None
    )
    assert first_reason is not None
    reasoning = build_reasoning_sample(first_reason)
    expected_reasoning = GOLDEN_DIR / "reasoning-output-sample.txt"
    _assert_text_equal(
        reasoning, expected_reasoning.read_text(encoding="utf-8"), "reasoning output"
    )

    related_items = [
        item
        for item in action_items.get("items", [])
        if item.get("type") == "append_related_links_section"
    ]
    related_items.sort(key=lambda item: str(item.get("target_path") or ""))
    related_item = related_items[0] if related_items else None
    assert related_item is not None
    related_block = related_item.get("payload", {}).get("markdown_block", "")
    expected_related = GOLDEN_DIR / "related-block-normal.md"
    _assert_text_equal(
        related_block, expected_related.read_text(encoding="utf-8"), "related block"
    )

    missing_anchor_path = None
    manifest = _load_json(VAULT_SRC / "manifest.json")
    for path, meta in manifest.items():
        if meta.get("expected_conflict") == "missing_anchor":
            missing_anchor_path = vault_dir / path
            break
    if missing_anchor_path:
        missing_block = extract_related_block(
            missing_anchor_path.read_text(encoding="utf-8")
        )
        expected_missing = GOLDEN_DIR / "related-block-missing-anchor.md"
        _assert_text_equal(
            missing_block,
            expected_missing.read_text(encoding="utf-8"),
            "missing anchor block",
        )

    conflicts_summary = summarize_conflicts(run_log.get("conflicts", []))
    conflicts_summary = normalize_json(
        conflicts_summary, base_dir=work_dir, vault_dir=vault_dir
    )
    expected_conflicts = GOLDEN_DIR / "conflicts-summary.json"
    _assert_text_equal(
        json_dumps(conflicts_summary),
        expected_conflicts.read_text(encoding="utf-8"),
        "conflicts summary",
    )
