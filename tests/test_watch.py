from __future__ import annotations

import json
import shutil
from pathlib import Path

from cli_helpers import run_oka
from oka.core.index import IndexStore


def _copy_vault(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_vault = repo_root / "tests" / "fixtures" / "sample_vault"
    target = tmp_path / "vault"
    shutil.copytree(fixture_vault, target)
    return target


def test_watch_updates_cache(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = run_oka(["watch", "--vault", str(vault), "--once"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    cache_path = tmp_path / "cache" / "index.sqlite"
    assert cache_path.exists()

    index = IndexStore(cache_path)
    last_updated = index.get_meta("last_updated")
    index.close()
    assert last_updated is not None


def test_fast_path_when_cache_fresh(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    (tmp_path / "oka.toml").write_text(
        "[performance]\nfast_path_max_age_sec = 3600\n", encoding="utf-8"
    )

    result = run_oka(["watch", "--vault", str(vault), "--once"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    run = run_oka(["run", "--vault", str(vault)], cwd=tmp_path)
    assert run.returncode == 0, run.stderr

    summary_path = tmp_path / "reports" / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["fast_path"] is True
