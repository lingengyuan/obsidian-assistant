from __future__ import annotations

import os
import time
from pathlib import Path

from oka.core.storage import prune_run_logs


def _create_run(runs_dir: Path, name: str, age_sec: int, size_bytes: int) -> None:
    run_dir = runs_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = "x" * size_bytes
    (run_dir / "run-log.json").write_text(payload, encoding="utf-8")
    target_time = time.time() - age_sec
    os.utime(run_dir, (target_time, target_time))


def test_prune_run_logs_by_count(tmp_path: Path) -> None:
    runs_dir = tmp_path / "reports" / "runs"
    _create_run(runs_dir, "run_old", age_sec=3600, size_bytes=10)
    _create_run(runs_dir, "run_mid", age_sec=1800, size_bytes=10)
    _create_run(runs_dir, "run_new", age_sec=300, size_bytes=10)

    config = {
        "storage": {
            "reports_dir": "reports",
            "max_run_logs": 2,
            "max_run_days": 0,
            "max_total_mb": 0,
            "compress_runs": False,
            "auto_prune": True,
        }
    }
    summary = prune_run_logs(tmp_path, config)
    remaining = [entry for entry in runs_dir.iterdir() if entry.is_dir()]
    assert len(remaining) == 2
    assert summary["removed"] == 1


def test_prune_run_logs_with_compress(tmp_path: Path) -> None:
    runs_dir = tmp_path / "reports" / "runs"
    _create_run(runs_dir, "run_old", age_sec=90000, size_bytes=10)

    config = {
        "storage": {
            "reports_dir": "reports",
            "max_run_logs": 0,
            "max_run_days": 0,
            "max_total_mb": 0,
            "compress_runs": True,
            "auto_prune": True,
        }
    }
    summary = prune_run_logs(tmp_path, config)
    assert summary["compressed"] == 1
    assert (runs_dir / "run_old.zip").exists()
