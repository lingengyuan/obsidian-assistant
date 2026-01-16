from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List


def _run_oka(args: List[str]) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    pythonpath = str(repo_root / "src")
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    return subprocess.run(
        [sys.executable, "-m", "oka", *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_oka_help() -> None:
    result = _run_oka(["--help"])
    assert result.returncode == 0
    assert "oka" in result.stdout.lower()


def test_oka_run_help() -> None:
    result = _run_oka(["run", "--help"])
    assert result.returncode == 0
    assert "run" in result.stdout.lower()


def test_oka_doctor_help() -> None:
    result = _run_oka(["doctor", "--help"])
    assert result.returncode == 0
    assert "doctor" in result.stdout.lower()
