from __future__ import annotations

import json
import shutil
from pathlib import Path

from cli_helpers import run_oka
from oka.core.apply import remove_anchor_block


def _copy_vault(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_vault = repo_root / "tests" / "fixtures" / "sample_vault"
    target = tmp_path / "vault"
    shutil.copytree(fixture_vault, target)
    for md_file in target.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        updated, _ = remove_anchor_block(content, "oka_related_v1")
        if updated != content:
            md_file.write_text(updated, encoding="utf-8")
    return target


def test_run_summary_apply_section(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    summary_path = tmp_path / "reports" / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    apply_section = summary.get("apply", {})

    assert "waited_sec" in apply_section
    assert "starvation" in apply_section
    assert "fallback" in apply_section
    assert "offline_lock" in apply_section
    assert apply_section["starvation"] is False
    assert apply_section["fallback"] == "none"
    assert apply_section["offline_lock"] is False
