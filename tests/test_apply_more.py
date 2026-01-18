from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from oka.core.apply import (
    _lock_stale,
    acquire_write_lease,
    apply_action_items,
    rollback_run,
)


def test_lock_stale_expires_at() -> None:
    expires_at = (datetime.utcnow() - timedelta(seconds=5)).isoformat() + "Z"
    assert _lock_stale({"expires_at": expires_at}) is True


def test_acquire_write_lease_force(tmp_path: Path) -> None:
    locks_dir = tmp_path / "locks"
    locks_dir.mkdir()
    lease_path = locks_dir / "write-lease.json"
    lease_path.write_text(
        json.dumps(
            {"expires_at": (datetime.utcnow() - timedelta(seconds=5)).isoformat() + "Z"}
        ),
        encoding="utf-8",
    )
    ok, _ = acquire_write_lease(locks_dir, ttl_sec=1, force=True)
    assert ok is True


def test_apply_missing_file_conflict(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    action_items = {
        "items": [
            {
                "id": "act_0001",
                "type": "append_related_links_section",
                "risk_class": "A",
                "target_path": "missing.md",
                "payload": {
                    "anchor": "oka_related_v1",
                    "markdown_block": "## Related\n",
                },
                "dependencies": [],
            }
        ]
    }
    result = apply_action_items(
        vault_path=vault,
        base_dir=tmp_path,
        run_id="run_missing",
        action_items=action_items,
        yes=True,
        wait_sec=0,
        force=True,
        max_wait_sec=0,
        offline_lock=False,
        offline_lock_marker=".nosync",
        offline_lock_cleanup=True,
    )
    assert result.return_code == 2
    conflict_note = (
        tmp_path / "reports" / "runs" / "run_missing" / "conflicts" / "missing.md.note"
    )
    assert conflict_note.exists()


def test_partial_rollback_missing_anchor(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "note.md"
    target.write_text("# Note\n", encoding="utf-8")

    run_id = "run_anchor"
    run_dir = tmp_path / "reports" / "runs" / run_id
    run_dir.mkdir(parents=True)
    log = {
        "version": "1",
        "run_id": run_id,
        "vault": str(vault),
        "changes": [
            {
                "action_id": "act_0001",
                "risk_class": "A",
                "target_path": "note.md",
                "anchors": ["oka_related_v1"],
                "frontmatter_keys": [],
            }
        ],
        "conflicts": [],
    }
    (run_dir / "run-log.json").write_text(json.dumps(log), encoding="utf-8")

    result = rollback_run(run_id, tmp_path, item_id="act_0001")
    assert result.return_code == 2
    conflict_note = run_dir / "conflicts" / "note.md.note"
    assert conflict_note.exists()
