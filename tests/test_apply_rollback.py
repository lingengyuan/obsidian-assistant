from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def _run_oka(args: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    pythonpath = str(repo_root / "src")
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    return subprocess.run(
        [sys.executable, "-m", "oka", *args],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_vault(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_vault = repo_root / "tests" / "fixtures" / "sample_vault"
    target = tmp_path / "vault"
    shutil.copytree(fixture_vault, target)
    return target


def _first_related_item(items: list[dict]) -> dict:
    for item in items:
        if item.get("type") == "append_related_links_section":
            return item
    raise AssertionError("no related link suggestions found")


def test_apply_idempotent(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = _run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    action_items = json.loads((tmp_path / "reports" / "action-items.json").read_text(encoding="utf-8"))
    item = _first_related_item(action_items["items"])
    target_path = item["target_path"]
    anchor = item["payload"]["anchor"]
    target_file = vault / target_path

    content = target_file.read_text(encoding="utf-8")
    assert content.count(anchor) == 1

    repeat = _run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert repeat.returncode == 0, repeat.stderr

    content_after = target_file.read_text(encoding="utf-8")
    assert content_after.count(anchor) == 1


def test_rollback_conflict(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = _run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    summary = json.loads((tmp_path / "reports" / "run-summary.json").read_text(encoding="utf-8"))
    run_id = summary["run_id"]

    action_items = json.loads((tmp_path / "reports" / "action-items.json").read_text(encoding="utf-8"))
    item = _first_related_item(action_items["items"])
    target_path = item["target_path"]
    target_file = vault / target_path
    target_file.write_text(target_file.read_text(encoding="utf-8") + "\nmanual change\n", encoding="utf-8")

    rollback = _run_oka(["rollback", run_id], cwd=tmp_path)
    assert rollback.returncode == 2, rollback.stderr

    conflict_diff = tmp_path / "reports" / "runs" / run_id / "conflicts" / f"{target_path}.diff"
    assert conflict_diff.exists()
