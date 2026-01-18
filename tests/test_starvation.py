from __future__ import annotations

from pathlib import Path

import pytest

from oka.core.apply import apply_action_items, wait_for_quiet


def test_wait_for_quiet_starvation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    obsidian = vault / ".obsidian"
    obsidian.mkdir(parents=True)

    calls = {"count": 0}

    def fake_latest(_: Path) -> float:
        calls["count"] += 1
        return float(calls["count"])

    monkeypatch.setattr("oka.core.apply._latest_mtime", fake_latest)

    quiet, waited = wait_for_quiet(vault, max_wait_sec=0, window_sec=0)
    assert quiet is False
    assert waited >= 0


def test_starvation_returns_11(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n", encoding="utf-8")

    def fake_wait(_: Path, __: int, window_sec: int = 2) -> tuple[bool, int]:
        return False, 3

    monkeypatch.setattr("oka.core.apply.wait_for_quiet", fake_wait)

    action_items = {
        "items": [
            {
                "id": "act_0001",
                "type": "add_frontmatter_fields",
                "risk_class": "A",
                "target_path": "note.md",
                "payload": {"fields": {"keywords": ["alpha"]}},
                "dependencies": [],
            }
        ]
    }

    result = apply_action_items(
        vault_path=vault,
        base_dir=tmp_path,
        run_id="run_starve",
        action_items=action_items,
        yes=True,
        wait_sec=1,
        force=True,
        max_wait_sec=1,
        offline_lock=False,
        offline_lock_marker=".nosync",
        offline_lock_cleanup=True,
    )

    assert result.return_code == 11
    assert result.starvation is True


def test_offline_lock_marker_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n", encoding="utf-8")

    def fake_wait(_: Path, __: int, window_sec: int = 2) -> tuple[bool, int]:
        return False, 1

    monkeypatch.setattr("oka.core.apply.wait_for_quiet", fake_wait)

    action_items = {
        "items": [
            {
                "id": "act_0001",
                "type": "append_related_links_section",
                "risk_class": "A",
                "target_path": "note.md",
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
        run_id="run_lock",
        action_items=action_items,
        yes=True,
        wait_sec=1,
        force=True,
        max_wait_sec=1,
        offline_lock=True,
        offline_lock_marker=".nosync",
        offline_lock_cleanup=True,
    )

    assert result.return_code == 0
    assert result.offline_lock is True
    assert not (vault / ".nosync").exists()
