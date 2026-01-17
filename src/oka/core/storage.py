from __future__ import annotations

import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from oka.core.config import get_bool, get_int, get_str

DEFAULT_COMPRESS_AFTER_DAYS = 1


def _dir_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            try:
                total += (root_path / name).stat().st_size
            except OSError:
                continue
    return total


def _list_runs(runs_dir: Path) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    if not runs_dir.exists():
        return entries
    for entry in runs_dir.iterdir():
        if entry.is_dir():
            size = _dir_size(entry)
            mtime = entry.stat().st_mtime
            entries.append(
                {
                    "run_id": entry.name,
                    "path": entry,
                    "mtime": mtime,
                    "size": size,
                    "is_dir": True,
                    "is_zip": False,
                }
            )
        elif entry.is_file() and entry.suffix == ".zip":
            stat = entry.stat()
            entries.append(
                {
                    "run_id": entry.stem,
                    "path": entry,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "is_dir": False,
                    "is_zip": True,
                }
            )
    return entries


def _compress_run(entry: Dict[str, object], runs_dir: Path) -> bool:
    run_path = Path(entry["path"])
    if not run_path.is_dir():
        return False
    zip_path = runs_dir / f"{entry['run_id']}.zip"
    if zip_path.exists():
        return False
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in run_path.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(run_path))
    shutil.rmtree(run_path)
    return True


def prune_run_logs(base_dir: Path, config: Dict[str, Any]) -> Dict[str, object]:
    reports_dir = get_str(config, "storage", "reports_dir", "reports")
    runs_dir = base_dir / reports_dir / "runs"
    entries = _list_runs(runs_dir)
    if not entries:
        return {"removed": 0, "compressed": 0, "before_mb": 0.0, "after_mb": 0.0}

    auto_prune = get_bool(config, "storage", "auto_prune", True)
    if not auto_prune:
        return {"removed": 0, "compressed": 0, "before_mb": 0.0, "after_mb": 0.0}

    max_run_logs = get_int(
        config,
        "storage",
        "max_run_logs",
        get_int(config, "storage", "retention_runs", 50),
    )
    max_run_days = get_int(
        config,
        "storage",
        "max_run_days",
        get_int(config, "storage", "retention_days", 30),
    )
    max_total_mb = get_int(config, "storage", "max_total_mb", 0)
    compress_runs = get_bool(config, "storage", "compress_runs", False)

    before_bytes = sum(entry["size"] for entry in entries)
    now = time.time()
    to_remove: List[Dict[str, object]] = []

    if max_run_days > 0:
        cutoff = now - max_run_days * 86400
        to_remove.extend(entry for entry in entries if entry["mtime"] < cutoff)

    remaining = [entry for entry in entries if entry not in to_remove]
    remaining.sort(key=lambda item: item["mtime"], reverse=True)

    if max_run_logs > 0 and len(remaining) > max_run_logs:
        to_remove.extend(remaining[max_run_logs:])
        remaining = remaining[:max_run_logs]

    if max_total_mb > 0:
        total = sum(entry["size"] for entry in remaining)
        limit = max_total_mb * 1024 * 1024
        while remaining and total > limit:
            entry = remaining.pop()
            to_remove.append(entry)
            total -= entry["size"]

    removed = 0
    for entry in to_remove:
        path = Path(entry["path"])
        if entry["is_dir"]:
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        removed += 1

    compressed = 0
    if compress_runs:
        compress_after = now - DEFAULT_COMPRESS_AFTER_DAYS * 86400
        remaining = _list_runs(runs_dir)
        for entry in remaining:
            if entry["is_dir"] and entry["mtime"] < compress_after:
                if _compress_run(entry, runs_dir):
                    compressed += 1

    after_entries = _list_runs(runs_dir)
    after_bytes = sum(entry["size"] for entry in after_entries)
    return {
        "removed": removed,
        "compressed": compressed,
        "before_mb": round(before_bytes / (1024 * 1024), 2),
        "after_mb": round(after_bytes / (1024 * 1024), 2),
    }
