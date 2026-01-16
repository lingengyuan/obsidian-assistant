from __future__ import annotations

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


def test_doctor_reports_encoding_and_line_endings(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = _run_oka(["doctor", "--vault", str(vault_path)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    stdout = result.stdout
    assert "Encoding:" in stdout
    assert "Line endings:" in stdout
    assert "utf8_bom=" in stdout
    assert "crlf=" in stdout
