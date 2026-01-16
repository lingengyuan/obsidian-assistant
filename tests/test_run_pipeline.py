from __future__ import annotations

import json
import os
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


def test_run_produces_reports(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = _run_oka(["run", "--vault", str(vault_path)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    reports_dir = tmp_path / "reports"
    health = reports_dir / "health.json"
    action_items = reports_dir / "action-items.json"
    run_summary = reports_dir / "run-summary.json"
    report_md = reports_dir / "report.md"

    assert health.exists()
    assert action_items.exists()
    assert run_summary.exists()
    assert report_md.exists()

    json.loads(health.read_text(encoding="utf-8"))
    json.loads(action_items.read_text(encoding="utf-8"))
    json.loads(run_summary.read_text(encoding="utf-8"))


def test_run_json_stdout(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = _run_oka(["run", "--vault", str(vault_path), "--json"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert "action_items" in payload
    assert "run_summary" in payload
