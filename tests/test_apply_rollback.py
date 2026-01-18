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


def _first_related_item(items: list[dict]) -> dict:
    for item in items:
        if item.get("type") == "append_related_links_section":
            return item
    raise AssertionError("no related link suggestions found")


def test_apply_idempotent(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    action_items = json.loads(
        (tmp_path / "reports" / "action-items.json").read_text(encoding="utf-8")
    )
    item = _first_related_item(action_items["items"])
    target_path = item["target_path"]
    anchor = item["payload"]["anchor"]
    target_file = vault / target_path

    content = target_file.read_text(encoding="utf-8")
    assert content.count(anchor) == 1

    repeat = run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert repeat.returncode == 0, repeat.stderr

    content_after = target_file.read_text(encoding="utf-8")
    assert content_after.count(anchor) == 1


def test_rollback_conflict(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    summary = json.loads(
        (tmp_path / "reports" / "run-summary.json").read_text(encoding="utf-8")
    )
    run_id = summary["run_id"]

    action_items = json.loads(
        (tmp_path / "reports" / "action-items.json").read_text(encoding="utf-8")
    )
    item = _first_related_item(action_items["items"])
    target_path = item["target_path"]
    target_file = vault / target_path
    target_file.write_text(
        target_file.read_text(encoding="utf-8") + "\nmanual change\n", encoding="utf-8"
    )

    rollback = run_oka(["rollback", run_id], cwd=tmp_path)
    assert rollback.returncode == 2, rollback.stderr

    conflict_diff = (
        tmp_path / "reports" / "runs" / run_id / "conflicts" / f"{target_path}.diff"
    )
    assert conflict_diff.exists()


def test_partial_rollback_item(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    summary = json.loads(
        (tmp_path / "reports" / "run-summary.json").read_text(encoding="utf-8")
    )
    run_id = summary["run_id"]
    action_items = json.loads(
        (tmp_path / "reports" / "action-items.json").read_text(encoding="utf-8")
    )
    item = _first_related_item(action_items["items"])
    target_path = item["target_path"]
    anchor = item["payload"]["anchor"]

    target_file = vault / target_path
    assert anchor in target_file.read_text(encoding="utf-8")

    rollback = run_oka(["rollback", run_id, "--item", item["id"]], cwd=tmp_path)
    assert rollback.returncode == 0, rollback.stderr

    content_after = target_file.read_text(encoding="utf-8")
    assert anchor not in content_after


def test_partial_rollback_file(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)

    result = run_oka(["run", "--vault", str(vault), "--apply", "--yes"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    summary = json.loads(
        (tmp_path / "reports" / "run-summary.json").read_text(encoding="utf-8")
    )
    run_id = summary["run_id"]
    action_items = json.loads(
        (tmp_path / "reports" / "action-items.json").read_text(encoding="utf-8")
    )
    item = _first_related_item(action_items["items"])
    target_path = item["target_path"]
    anchor = item["payload"]["anchor"]

    target_file = vault / target_path
    assert anchor in target_file.read_text(encoding="utf-8")

    rollback = run_oka(["rollback", run_id, "--file", target_path], cwd=tmp_path)
    assert rollback.returncode == 0, rollback.stderr

    content_after = target_file.read_text(encoding="utf-8")
    assert anchor not in content_after
