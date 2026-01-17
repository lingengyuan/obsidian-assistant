from __future__ import annotations

from pathlib import Path

from oka.core.apply import apply_action_items


def test_b1_rename_updates_links(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    notes = vault / "notes"
    notes.mkdir(parents=True)
    (notes / "old.md").write_text("# Old\n", encoding="utf-8")
    (notes / "other.md").write_text("Link to [[old]]\n", encoding="utf-8")

    action_items = {
        "items": [
            {
                "id": "act_0001",
                "type": "rename_note_and_update_links",
                "risk_class": "B1",
                "target_path": "notes/new.md",
                "payload": {"source_path": "notes/old.md", "target_path": "notes/new.md"},
                "dependencies": [],
            }
        ]
    }

    result = apply_action_items(
        vault_path=vault,
        base_dir=tmp_path,
        run_id="run_b1",
        action_items=action_items,
        yes=True,
        wait_sec=0,
        force=True,
        max_wait_sec=0,
        offline_lock=False,
        offline_lock_marker=".nosync",
        offline_lock_cleanup=True,
    )

    assert result.return_code == 0
    assert not (notes / "old.md").exists()
    assert (notes / "new.md").exists()
    assert "Link to [[new]]" in (notes / "other.md").read_text(encoding="utf-8")
