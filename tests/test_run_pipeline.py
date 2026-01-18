from __future__ import annotations

import json
from pathlib import Path

from cli_helpers import run_oka


def test_run_produces_reports(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = run_oka(["run", "--vault", str(vault_path)], cwd=tmp_path)
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
    action_payload = json.loads(action_items.read_text(encoding="utf-8"))
    json.loads(run_summary.read_text(encoding="utf-8"))

    items = action_payload.get("items", [])
    assert items, "expected action items to be generated"
    assert any(item.get("risk_class") == "A" for item in items)
    for item in items:
        reason = item.get("reason", {})
        assert "content_sim" in reason
        assert "title_sim" in reason
        assert "link_overlap" in reason
        assert "filters" in reason


def test_run_json_stdout(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = run_oka(["run", "--vault", str(vault_path), "--json"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert "action_items" in payload
    assert "run_summary" in payload


def test_incremental_hit_rate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    first = run_oka(["run", "--vault", str(vault_path)], cwd=tmp_path)
    assert first.returncode == 0, first.stderr

    second = run_oka(["run", "--vault", str(vault_path)], cwd=tmp_path)
    assert second.returncode == 0, second.stderr

    summary = json.loads(
        (tmp_path / "reports" / "run-summary.json").read_text(encoding="utf-8")
    )
    assert summary["cache"]["hit_rate"] > 0.7
    assert (
        summary["incremental"]["incremental_updated"] <= summary["io"]["scanned_files"]
    )
