from __future__ import annotations

import json
from pathlib import Path

from cli_helpers import run_oka


def test_partial_rollback_rejects_non_a(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("content", encoding="utf-8")

    run_id = "run_non_a"
    run_dir = tmp_path / "reports" / "runs" / run_id
    run_dir.mkdir(parents=True)
    run_log = {
        "version": "1",
        "run_id": run_id,
        "vault": str(vault),
        "changes": [
            {
                "action_id": "act_0001",
                "risk_class": "read-only",
                "target_path": "note.md",
                "anchors": ["oka_related_v1"],
                "frontmatter_keys": [],
            }
        ],
        "conflicts": [],
    }
    (run_dir / "run-log.json").write_text(json.dumps(run_log), encoding="utf-8")

    result = run_oka(["rollback", run_id, "--item", "act_0001"], cwd=tmp_path)
    assert result.returncode == 20
    assert "Class A" in (result.stdout + result.stderr)
