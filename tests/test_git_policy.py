from __future__ import annotations

from pathlib import Path

from oka.core.apply import apply_action_items


def _simple_action() -> dict:
    return {
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


def test_git_policy_require_clean_blocks_dirty(monkeypatch, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("content\n", encoding="utf-8")

    monkeypatch.setattr("oka.core.apply.git_utils.is_git_repo", lambda _: True)
    monkeypatch.setattr("oka.core.apply.git_utils.is_clean", lambda _: False)

    result = apply_action_items(
        vault_path=vault,
        base_dir=tmp_path,
        run_id="run_git",
        action_items=_simple_action(),
        yes=True,
        wait_sec=0,
        force=True,
        max_wait_sec=0,
        offline_lock=False,
        offline_lock_marker=".nosync",
        offline_lock_cleanup=True,
        git_policy="require_clean",
        git_auto_commit=False,
    )

    assert result.return_code == 10


def test_git_auto_commit_records(monkeypatch, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("content\n", encoding="utf-8")

    commits: list[str] = []

    def fake_commit(_: Path, message: str, allow_empty: bool) -> str:
        commits.append(message)
        return f"commit_{len(commits)}"

    monkeypatch.setattr("oka.core.apply.git_utils.is_git_repo", lambda _: True)
    monkeypatch.setattr("oka.core.apply.git_utils.is_clean", lambda _: True)
    monkeypatch.setattr("oka.core.apply.git_utils.git_commit", fake_commit)

    result = apply_action_items(
        vault_path=vault,
        base_dir=tmp_path,
        run_id="run_git",
        action_items=_simple_action(),
        yes=True,
        wait_sec=0,
        force=True,
        max_wait_sec=0,
        offline_lock=False,
        offline_lock_marker=".nosync",
        offline_lock_cleanup=True,
        git_policy="require_clean",
        git_auto_commit=True,
    )

    assert result.return_code == 0
    assert result.git_info["pre_commit"] == "commit_1"
    assert result.git_info["post_commit"] == "commit_2"
    assert len(commits) == 2
