from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from difflib import unified_diff

from oka.core import git_utils
from oka.core.i18n import t

LINK_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


@dataclass
class ApplyResult:
    return_code: int
    conflicts: List[Dict[str, object]]
    changes: List[Dict[str, object]]
    waited_sec: int
    starvation: bool
    fallback: str
    offline_lock: bool
    git_info: Dict[str, object] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _hash_text(content: str) -> str:
    return _sha256_bytes(content.encode("utf-8"))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".oka.tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _latest_mtime(path: Path) -> Optional[float]:
    latest = None
    if not path.exists():
        return None
    for root, _, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            try:
                mtime = file_path.stat().st_mtime
            except OSError:
                continue
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def wait_for_quiet(
    vault_path: Path, max_wait_sec: int, window_sec: int = 2
) -> Tuple[bool, int]:
    obsidian_dir = vault_path / ".obsidian"
    if not obsidian_dir.exists():
        return True, 0

    start = time.monotonic()
    last_wait = 0
    while True:
        first = _latest_mtime(obsidian_dir)
        time.sleep(window_sec)
        second = _latest_mtime(obsidian_dir)
        if first == second:
            waited = int(time.monotonic() - start)
            return True, waited
        if max_wait_sec <= 0:
            return False, int(time.monotonic() - start)
        last_wait = int(time.monotonic() - start)
        if last_wait >= max_wait_sec:
            return False, last_wait
        if time.monotonic() - start >= max_wait_sec:
            return False, int(time.monotonic() - start)


def _offline_lock_path(vault_path: Path, marker: str) -> Path:
    return vault_path / marker


def create_offline_lock(vault_path: Path, marker: str) -> Optional[Path]:
    if not marker:
        return None
    marker_path = _offline_lock_path(vault_path, marker)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text("oka offline lock\n", encoding="utf-8")
    return marker_path


def remove_offline_lock(marker_path: Optional[Path]) -> None:
    if marker_path is None:
        return
    try:
        marker_path.unlink()
    except FileNotFoundError:
        pass


def _lock_stale(data: Dict[str, object]) -> bool:
    now = datetime.now(timezone.utc)
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            return expires < now
        except ValueError:
            return False
    created_at = data.get("created_at")
    ttl_sec = data.get("ttl_sec")
    if created_at and ttl_sec:
        try:
            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            ttl = int(ttl_sec)
            return created + timedelta(seconds=ttl) < now
        except ValueError:
            return False
    return False


def acquire_write_lease(locks_dir: Path, ttl_sec: int, force: bool) -> Tuple[bool, str]:
    locks_dir.mkdir(parents=True, exist_ok=True)
    lease_path = locks_dir / "write-lease.json"
    if lease_path.exists():
        try:
            data = json.loads(lease_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "existing lease unreadable"
        if _lock_stale(data):
            if force:
                lease_path.unlink(missing_ok=True)
            else:
                return False, "stale lease found (use --force to clear)"
        else:
            return False, "active lease found"

    started_at = _now_iso()
    expires_at = (datetime.utcnow() + timedelta(seconds=ttl_sec)).replace(microsecond=0).isoformat() + "Z"
    lease_data = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "created_at": started_at,
        "ttl_sec": ttl_sec,
        "expires_at": expires_at,
    }
    lease_path.write_text(json.dumps(lease_data, indent=2), encoding="utf-8")
    return True, "ok"


def release_write_lease(locks_dir: Path) -> None:
    lease_path = locks_dir / "write-lease.json"
    try:
        lease_path.unlink()
    except FileNotFoundError:
        pass


def _format_frontmatter_fields(fields: Dict[str, List[str]]) -> List[str]:
    lines: List[str] = []
    for key, values in fields.items():
        if not values:
            continue
        lines.append(f"{key}:")
        for value in values:
            safe = value.replace("\"", "\\\"")
            if ":" in safe or "#" in safe:
                safe = f"\"{safe}\""
            lines.append(f"  - {safe}")
    return lines


def _split_frontmatter_lines(lines: List[str]) -> Tuple[bool, int, int]:
    if not lines:
        return False, 0, 0
    if lines[0].strip() != "---":
        return False, 0, 0
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return True, 0, idx
    return False, 0, 0


def _frontmatter_keys(lines: List[str]) -> List[str]:
    keys: List[str] = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("-"):
            continue
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key:
                keys.append(key)
    return keys


def apply_frontmatter_fields(content: str, fields: Dict[str, List[str]]) -> Tuple[str, List[str]]:
    if not fields:
        return content, []
    lines = content.splitlines()
    has_frontmatter, start, end = _split_frontmatter_lines(lines)
    inserted_keys: List[str] = []

    if not has_frontmatter:
        new_lines = ["---"]
        new_lines.extend(_format_frontmatter_fields(fields))
        inserted_keys = list(fields.keys())
        new_lines.append("---")
        new_lines.extend(lines)
        return "\n".join(new_lines) + ("\n" if content.endswith("\n") else ""), inserted_keys

    fm_lines = lines[start + 1 : end]
    existing_keys = set(_frontmatter_keys(fm_lines))
    new_fields = {k: v for k, v in fields.items() if k not in existing_keys}
    if not new_fields:
        return content, []

    inserted_keys = list(new_fields.keys())
    updated_lines = lines[:end]
    updated_lines.extend(_format_frontmatter_fields(new_fields))
    updated_lines.extend(lines[end:])
    return "\n".join(updated_lines) + ("\n" if content.endswith("\n") else ""), inserted_keys


def remove_frontmatter_keys(content: str, keys: Sequence[str]) -> Tuple[str, List[str]]:
    if not keys:
        return content, []
    lines = content.splitlines()
    has_frontmatter, start, end = _split_frontmatter_lines(lines)
    if not has_frontmatter:
        return content, []

    to_remove = set(keys)
    kept_lines: List[str] = []
    removed: List[str] = []
    idx = start + 1
    while idx < end:
        line = lines[idx]
        stripped = line.strip()
        if stripped and not line.lstrip().startswith("-") and ":" in line:
            key = line.split(":", 1)[0].strip()
            if key in to_remove:
                removed.append(key)
                idx += 1
                while idx < end:
                    next_line = lines[idx]
                    if next_line.strip() == "":
                        idx += 1
                        continue
                    if next_line.lstrip().startswith("-") or next_line.startswith(" "):
                        idx += 1
                        continue
                    break
                continue
        kept_lines.append(line)
        idx += 1

    updated_lines = lines[: start + 1] + kept_lines + lines[end:]
    return "\n".join(updated_lines) + ("\n" if content.endswith("\n") else ""), removed


def append_anchor_block(content: str, anchor: str, block: str) -> Tuple[str, bool]:
    if anchor in content:
        return content, False
    separator = "" if content.endswith("\n") else "\n"
    return content + separator + block, True


def remove_anchor_block(content: str, anchor: str) -> Tuple[str, bool]:
    lines = content.splitlines()
    anchor_line = f"<!-- {anchor} -->"
    if anchor_line not in lines:
        return content, False
    idx = lines.index(anchor_line)
    start = idx
    if idx > 0 and lines[idx - 1].strip().lower().startswith("##"):
        start = idx - 1
    end = idx + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == "":
            end += 1
            break
        if line.lstrip().startswith("-"):
            end += 1
            continue
        break
    new_lines = lines[:start] + lines[end:]
    suffix = "\n" if content.endswith("\n") else ""
    return "\n".join(new_lines) + suffix, True


def _write_diff(path: Path, before: str, after: str, rel_path: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    diff_lines = unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=rel_path,
        tofile=rel_path,
    )
    path.write_text("".join(diff_lines), encoding="utf-8")


def _write_conflict_note(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message, encoding="utf-8")


def _ensure_howto(conflicts_dir: Path, lang: str) -> None:
    howto_path = conflicts_dir / "HOWTO.txt"
    if howto_path.exists():
        return
    howto_path.write_text(t(lang, "howto_conflicts"), encoding="utf-8")


def _relative_target(vault_path: Path, target_path: str) -> Path:
    return vault_path / target_path


def _summarize_items(items: List[Dict[str, object]]) -> Dict[str, object]:
    summary: Dict[str, object] = {"count": len(items), "files": {}, "items": []}
    for item in items:
        target = item.get("target_path", "")
        summary["files"][target] = summary["files"].get(target, 0) + 1
        summary["items"].append(
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "target_path": target,
                "confidence": item.get("confidence", 0.0),
            }
        )
    return summary


def _prompt_confirmation(summary: Dict[str, object], lang: str) -> bool:
    file_counts = summary["files"]
    top_files = sorted(file_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    print(f"\n{t(lang, 'apply_summary')}")
    print("-------------")
    print(t(lang, "apply_actions", count=summary["count"]))
    print(t(lang, "apply_files", count=len(file_counts)))
    if top_files:
        print(t(lang, "apply_top_files"))
        for path, count in top_files:
            print(f"- {path} ({count})")

    while True:
        answer = input(t(lang, "apply_prompt")).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer == "preview":
            print(f"\n{t(lang, 'apply_preview')}")
            print("-------")
            for item in summary["items"][:20]:
                print(
                    t(
                        lang,
                        "apply_preview_item",
                        id=item["id"],
                        type=item["type"],
                        target=item["target_path"],
                        confidence=item["confidence"],
                    )
                )
        else:
            print(t(lang, "apply_prompt_invalid"))


def _prompt_starvation_mode(lang: str) -> str:
    print(f"\n{t(lang, 'starvation_detected')}")
    print(t(lang, "starvation_mode_title"))
    print(t(lang, "starvation_option_append"))
    print(t(lang, "starvation_option_all"))
    print(t(lang, "starvation_option_abort"))

    while True:
        answer = input(t(lang, "starvation_choice")).strip().lower()
        if answer in ("append", "all", "abort"):
            return answer
        print(t(lang, "starvation_prompt_invalid"))


def _list_md_files(vault_path: Path) -> List[Path]:
    md_files: List[Path] = []
    for root, dirs, files in os.walk(vault_path):
        if ".obsidian" in dirs:
            dirs[:] = [d for d in dirs if d != ".obsidian"]
        root_path = Path(root)
        for name in files:
            if name.lower().endswith(".md"):
                md_files.append(root_path / name)
    return md_files


def _replace_links(content: str, rename_map: Dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        raw = match.group(1)
        target_part = raw
        suffix = ""
        if "|" in raw:
            target_part, suffix = raw.split("|", 1)
            suffix = "|" + suffix
        if "#" in target_part:
            target_part, anchor = target_part.split("#", 1)
            suffix = "#" + anchor + suffix
        target = target_part.strip()
        if target.lower().endswith(".md"):
            target = target[:-3]
        if target in rename_map:
            new_target = rename_map[target]
            return f"[[{new_target}{suffix}]]"
        return match.group(0)

    return LINK_PATTERN.sub(repl, content)


def _extract_b1_pairs(items: List[Dict[str, object]]) -> Tuple[List[Tuple[str, str]], List[str]]:
    pairs: List[Tuple[str, str]] = []
    errors: List[str] = []
    for item in items:
        payload = item.get("payload", {})
        source = payload.get("source_path") or item.get("source_path")
        target = payload.get("target_path") or item.get("target_path")
        if not source or not target:
            errors.append(item.get("id", "unknown"))
            continue
        pairs.append((str(source), str(target)))
    return pairs, errors


def _apply_b1_transaction(
    items: List[Dict[str, object]],
    vault_path: Path,
    run_dir: Path,
    lang: str,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    conflicts: List[Dict[str, object]] = []
    changes: List[Dict[str, object]] = []
    pairs, errors = _extract_b1_pairs(items)
    if errors:
        for action_id in errors:
            note_path = run_dir / "conflicts" / f"{action_id}.note"
            diff_path = run_dir / "conflicts" / f"{action_id}.diff"
            _write_conflict_note(note_path, t(lang, "conflict_b1_payload"))
            _write_conflict_note(diff_path, "")
            conflicts.append(
                {"target_path": action_id, "diff_path": str(diff_path), "note_path": str(note_path)}
            )
        return changes, conflicts

    rename_map: Dict[str, str] = {
        Path(source).stem: Path(target).stem for source, target in pairs
    }
    rename_path_map: Dict[Path, Path] = {
        vault_path / source: vault_path / target for source, target in pairs
    }

    for source_path, target_path in rename_path_map.items():
        if not source_path.exists():
            note_path = run_dir / "conflicts" / f"{source_path}.note"
            diff_path = run_dir / "conflicts" / f"{source_path}.diff"
            _write_conflict_note(note_path, t(lang, "conflict_b1_missing"))
            _write_conflict_note(diff_path, "")
            conflicts.append(
                {"target_path": str(source_path), "diff_path": str(diff_path), "note_path": str(note_path)}
            )
        if target_path.exists() and target_path != source_path:
            note_path = run_dir / "conflicts" / f"{target_path}.note"
            diff_path = run_dir / "conflicts" / f"{target_path}.diff"
            _write_conflict_note(note_path, t(lang, "conflict_b1_target_exists"))
            _write_conflict_note(diff_path, "")
            conflicts.append(
                {"target_path": str(target_path), "diff_path": str(diff_path), "note_path": str(note_path)}
            )

    if conflicts:
        return changes, conflicts

    md_files = _list_md_files(vault_path)
    base_contents: Dict[Path, str] = {}
    updated_contents: Dict[Path, str] = {}
    for path in md_files:
        base_content = _read_text(path)
        base_contents[path] = base_content
        updated = _replace_links(base_content, rename_map)
        updated_contents[path] = updated

    content_updates: Dict[Path, str] = {}
    remove_sources: List[Path] = []
    for source_path, target_path in rename_path_map.items():
        base_content = base_contents.get(source_path)
        if base_content is None:
            continue
        updated = updated_contents.get(source_path, base_content)
        content_updates[target_path] = updated
        remove_sources.append(source_path)

    for path, updated in updated_contents.items():
        if path in rename_path_map:
            continue
        if updated != base_contents[path]:
            content_updates[path] = updated

    for path, base_content in base_contents.items():
        if path not in content_updates and path not in rename_path_map:
            continue
        current_content = _read_text(path)
        if _hash_text(current_content) != _hash_text(base_content):
            diff_path = run_dir / "conflicts" / f"{path.relative_to(vault_path)}.diff"
            note_path = run_dir / "conflicts" / f"{path.relative_to(vault_path)}.note"
            _write_diff(diff_path, base_content, current_content, str(path))
            _write_conflict_note(
                note_path,
                t(lang, "conflict_b1_changed"),
            )
            conflicts.append(
                {"target_path": str(path), "diff_path": str(diff_path), "note_path": str(note_path)}
            )

    if conflicts:
        return changes, conflicts

    for path, content in content_updates.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, content)

    for source_path in remove_sources:
        if source_path.exists():
            try:
                source_path.unlink()
            except OSError:
                note_path = run_dir / "conflicts" / f"{source_path}.note"
                diff_path = run_dir / "conflicts" / f"{source_path}.diff"
                _write_conflict_note(note_path, t(lang, "conflict_b1_remove_failed"))
                _write_conflict_note(diff_path, "")
                conflicts.append(
                    {"target_path": str(source_path), "diff_path": str(diff_path), "note_path": str(note_path)}
                )

    for item in items:
        payload = item.get("payload", {})
        source = payload.get("source_path") or item.get("source_path")
        target = payload.get("target_path") or item.get("target_path")
        changes.append(
            {
                "action_id": item.get("id"),
                "action_type": item.get("type"),
                "risk_class": item.get("risk_class"),
                "source_path": source,
                "target_path": target,
                "affected_files": [str(path) for path in content_updates.keys()],
            }
        )

    return changes, conflicts


def apply_action_items(
    vault_path: Path,
    base_dir: Path,
    run_id: str,
    action_items: Dict[str, object],
    yes: bool,
    wait_sec: int,
    force: bool,
    max_wait_sec: int,
    offline_lock: bool,
    offline_lock_marker: str,
    offline_lock_cleanup: bool,
    git_policy: str = "require_clean",
    git_auto_stash: bool = False,
    git_auto_commit: bool = False,
    lang: str = "en",
    ttl_sec: int = 60,
) -> ApplyResult:
    git_info: Dict[str, object] = {
        "repo": False,
        "dirty": None,
        "policy": git_policy,
        "auto_stash": git_auto_stash,
        "auto_commit": git_auto_commit,
        "pre_commit": None,
        "post_commit": None,
    }
    stash_used = False
    if git_utils.is_git_repo(vault_path):
        git_info["repo"] = True
        dirty = not git_utils.is_clean(vault_path)
        git_info["dirty"] = dirty
        if git_policy == "require_clean" and dirty:
            print(t(lang, "git_dirty_require_clean"))
            return ApplyResult(
                return_code=10,
                conflicts=[],
                changes=[],
                waited_sec=0,
                starvation=False,
                fallback="none",
                offline_lock=False,
                git_info=git_info,
            )
        if git_policy == "auto_stash" and dirty:
            if git_utils.stash_push(vault_path):
                stash_used = True
                git_info["auto_stash"] = True
                dirty = False
                git_info["dirty"] = False
            else:
                print(t(lang, "git_stash_failed"))
                return ApplyResult(
                    return_code=20,
                    conflicts=[],
                    changes=[],
                    waited_sec=0,
                    starvation=False,
                    fallback="none",
                    offline_lock=False,
                    git_info=git_info,
                )
        if git_auto_commit and dirty:
            print(t(lang, "git_autocommit_requires_clean"))
            return ApplyResult(
                return_code=10,
                conflicts=[],
                changes=[],
                waited_sec=0,
                starvation=False,
                fallback="none",
                offline_lock=False,
                git_info=git_info,
            )
        if git_auto_commit:
            git_info["pre_commit"] = git_utils.git_commit(
                vault_path,
                f"oka pre-apply {run_id}",
                allow_empty=True,
            )
    wait_limit = 0
    if wait_sec > 0:
        if max_wait_sec > 0:
            wait_limit = min(wait_sec, max_wait_sec)
        else:
            wait_limit = 0

    window_sec = 1 if wait_limit <= 0 else 2
    quiet, waited_sec = wait_for_quiet(vault_path, wait_limit, window_sec=window_sec)
    starvation = not quiet
    fallback = "none"
    offline_lock_created = False
    offline_lock_path = None

    locks_dir = base_dir / "locks"
    ok, message = acquire_write_lease(locks_dir, ttl_sec, force)
    if not ok:
        print(t(lang, "write_lease_denied", message=message))
        return ApplyResult(
            return_code=12,
            conflicts=[],
            changes=[],
            waited_sec=waited_sec,
            starvation=starvation,
            fallback=fallback,
            offline_lock=offline_lock_created,
            git_info=git_info,
        )

    conflicts: List[Dict[str, object]] = []
    changes: List[Dict[str, object]] = []
    run_dir = base_dir / "reports" / "runs" / run_id
    patches_dir = run_dir / "patches"
    backups_dir = run_dir / "backups"
    conflicts_dir = run_dir / "conflicts"

    try:
        all_items = action_items.get("items", [])
        class_a_items = [
            item
            for item in all_items
            if item.get("risk_class") == "A"
            and item.get("type") in {"append_related_links_section", "add_frontmatter_fields"}
        ]
        b1_items = [
            item
            for item in all_items
            if item.get("risk_class") in {"B1", "B"}
            and item.get("type") == "rename_note_and_update_links"
        ]
        append_items = [
            item
            for item in class_a_items
            if item.get("type") == "append_related_links_section"
        ]
        applicable = class_a_items + b1_items

        if starvation:
            if b1_items:
                print(t(lang, "starvation_b1_disabled"))
                b1_items = []
                applicable = class_a_items
            if not yes:
                choice = _prompt_starvation_mode(lang)
                if choice == "abort":
                    print(t(lang, "starvation_abort"))
                    print(t(lang, "starvation_tip"))
                    return ApplyResult(
                        return_code=11,
                        conflicts=[],
                        changes=[],
                    waited_sec=waited_sec,
                    starvation=True,
                    fallback="abort",
                    offline_lock=offline_lock_created,
                    git_info=git_info,
                )
                if choice == "append":
                    applicable = append_items
                    fallback = "append_only"
                else:
                    fallback = "all_class_a"
            else:
                applicable = append_items
                fallback = "append_only"

            if offline_lock:
                offline_lock_path = create_offline_lock(vault_path, offline_lock_marker)
                offline_lock_created = offline_lock_path is not None
                fallback = "offline_lock" if fallback == "none" else fallback

        if not applicable:
            if starvation:
                print(t(lang, "starvation_no_applicable"))
                print(t(lang, "starvation_tip"))
                return ApplyResult(
                    return_code=11,
                    conflicts=[],
                    changes=[],
                    waited_sec=waited_sec,
                    starvation=True,
                    fallback=fallback or "none",
                    offline_lock=offline_lock_created,
                    git_info=git_info,
                )
                return ApplyResult(
                    return_code=0,
                    conflicts=[],
                    changes=[],
                    waited_sec=waited_sec,
                    starvation=False,
                    fallback="none",
                    offline_lock=offline_lock_created,
                    git_info=git_info,
                )

        summary = _summarize_items(applicable)
        if not yes:
            if not _prompt_confirmation(summary, lang):
                return ApplyResult(
                    return_code=0,
                    conflicts=[],
                    changes=[],
                    waited_sec=waited_sec,
                    starvation=starvation,
                    fallback=fallback,
                    offline_lock=offline_lock_created,
                    git_info=git_info,
                )

        if b1_items:
            b1_changes, b1_conflicts = _apply_b1_transaction(
                b1_items, vault_path, run_dir, lang
            )
            if b1_conflicts:
                conflicts.extend(b1_conflicts)
                _ensure_howto(conflicts_dir, lang)
                return ApplyResult(
                    return_code=2,
                    conflicts=conflicts,
                    changes=changes,
                    waited_sec=waited_sec,
                    starvation=starvation,
                    fallback=fallback,
                    offline_lock=offline_lock_created,
                    git_info=git_info,
                )
            changes.extend(b1_changes)

        for item in applicable:
            if item.get("type") == "rename_note_and_update_links":
                continue
            target_path = item.get("target_path") or ""
            if not target_path:
                continue
            file_path = _relative_target(vault_path, target_path)
            if not file_path.exists():
                note_path = conflicts_dir / f"{target_path}.note"
                diff_path = conflicts_dir / f"{target_path}.diff"
                _write_conflict_note(note_path, t(lang, "conflict_target_missing"))
                _write_conflict_note(diff_path, "")
                conflicts.append(
                    {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
                )
                continue

            base_content = _read_text(file_path)
            base_hash = _hash_text(base_content)

            new_content = base_content
            anchors: List[str] = []
            frontmatter_keys: List[str] = []
            if item.get("type") == "append_related_links_section":
                payload = item.get("payload", {})
                anchor = payload.get("anchor", "oka_related_v1")
                block = payload.get("markdown_block", "")
                new_content, changed = append_anchor_block(new_content, anchor, block)
                if changed:
                    anchors.append(anchor)
            elif item.get("type") == "add_frontmatter_fields":
                payload = item.get("payload", {})
                fields = payload.get("fields", {})
                new_content, inserted = apply_frontmatter_fields(new_content, fields)
                frontmatter_keys.extend(inserted)

            if new_content == base_content:
                continue

            before_content = _read_text(file_path)
            before_hash = _hash_text(before_content)
            if before_hash != base_hash:
                diff_path = conflicts_dir / f"{target_path}.diff"
                note_path = conflicts_dir / f"{target_path}.note"
                _write_diff(diff_path, base_content, before_content, target_path)
                _write_conflict_note(
                    note_path,
                    t(lang, "conflict_changed_apply"),
                )
                conflicts.append(
                    {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
                )
                continue

            _atomic_write(file_path, new_content)
            after_content = _read_text(file_path)
            after_hash = _hash_text(after_content)

            patch_path = patches_dir / f"{target_path}.patch"
            backup_path = backups_dir / f"{target_path}.bak"
            _write_diff(patch_path, before_content, after_content, target_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(before_content, encoding="utf-8")

            changes.append(
                {
                    "action_id": item.get("id"),
                    "action_type": item.get("type"),
                    "risk_class": item.get("risk_class"),
                    "target_path": target_path,
                    "base_hash": base_hash,
                    "before_hash": before_hash,
                    "after_hash": after_hash,
                    "patch_path": str(patch_path),
                    "backup_path": str(backup_path),
                    "anchors": anchors,
                    "frontmatter_keys": frontmatter_keys,
                    "dependencies": item.get("dependencies", []),
                }
            )

        if conflicts:
            _ensure_howto(conflicts_dir, lang)
    finally:
        if offline_lock_cleanup:
            remove_offline_lock(offline_lock_path)
        if stash_used:
            git_utils.stash_pop(vault_path)
        release_write_lease(locks_dir)

    return_code = 2 if conflicts else 0
    if git_info["repo"] and git_auto_commit and return_code == 0:
        git_info["post_commit"] = git_utils.git_commit(
            vault_path,
            f"oka apply {run_id}",
            allow_empty=True,
        )
    return ApplyResult(
        return_code=return_code,
        conflicts=conflicts,
        changes=changes,
        waited_sec=waited_sec,
        starvation=starvation,
        fallback=fallback,
        offline_lock=offline_lock_created,
        git_info=git_info,
    )


def write_run_log(
    base_dir: Path,
    run_id: str,
    vault_path: Path,
    changes: List[Dict[str, object]],
    conflicts: List[Dict[str, object]],
    apply_info: Optional[Dict[str, object]] = None,
) -> Path:
    run_dir = base_dir / "reports" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run-log.json"
    payload = {
        "version": "1",
        "run_id": run_id,
        "vault": str(vault_path),
        "started_at": apply_info.get("started_at") if apply_info else None,
        "ended_at": _now_iso(),
        "apply": apply_info or {},
        "changes": changes,
        "conflicts": conflicts,
    }
    log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return log_path


def _load_run_log(
    run_id: str, base_dir: Path, lang: str
) -> Tuple[Optional[Dict[str, object]], Path]:
    run_dir = base_dir / "reports" / "runs" / run_id
    log_path = run_dir / "run-log.json"
    if not log_path.exists():
        print(t(lang, "rollback_run_not_found", path=log_path))
        return None, run_dir
    data = json.loads(log_path.read_text(encoding="utf-8"))
    return data, run_dir


def _dependency_notice(changes: List[Dict[str, object]], lang: str) -> None:
    selected_ids = {change.get("action_id") for change in changes}
    missing: List[str] = []
    for change in changes:
        for dep in change.get("dependencies", []) or []:
            if dep not in selected_ids:
                missing.append(dep)
    if missing:
        unique = ", ".join(sorted(set(missing)))
        print(t(lang, "dependency_notice", deps=unique))


def _rollback_change_partial(
    change: Dict[str, object],
    vault_path: Path,
    run_dir: Path,
    conflicts: List[Dict[str, object]],
    lang: str,
) -> None:
    target_path = change.get("target_path") or ""
    file_path = Path(vault_path) / target_path
    if not target_path or not file_path.exists():
        note_path = run_dir / "conflicts" / f"{target_path}.note"
        diff_path = run_dir / "conflicts" / f"{target_path}.diff"
        _write_conflict_note(note_path, t(lang, "conflict_file_missing"))
        _write_conflict_note(diff_path, "")
        conflicts.append(
            {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
        )
        return

    current_content = _read_text(file_path)
    updated_content = current_content
    missing: List[str] = []

    anchors = change.get("anchors", []) or []
    for anchor in anchors:
        updated_content, removed = remove_anchor_block(updated_content, anchor)
        if not removed:
            missing.append(f"anchor:{anchor}")

    frontmatter_keys = change.get("frontmatter_keys", []) or []
    if frontmatter_keys:
        updated_content, removed_keys = remove_frontmatter_keys(updated_content, frontmatter_keys)
        removed_set = set(removed_keys)
        for key in frontmatter_keys:
            if key not in removed_set:
                missing.append(f"frontmatter:{key}")

    if missing or updated_content == current_content:
        note_path = run_dir / "conflicts" / f"{target_path}.note"
        diff_path = run_dir / "conflicts" / f"{target_path}.diff"
        if updated_content != current_content:
            _write_diff(diff_path, current_content, updated_content, target_path)
        else:
            _write_conflict_note(diff_path, "")
        detail = (
            t(lang, "rollback_missing_targets", targets=", ".join(missing))
            if missing
            else t(lang, "rollback_no_changes")
        )
        _write_conflict_note(note_path, detail)
        conflicts.append(
            {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
        )
        return

    _atomic_write(file_path, updated_content)


def _rollback_full(
    changes: List[Dict[str, object]],
    run_dir: Path,
    vault_path: Path,
    lang: str,
) -> ApplyResult:
    conflicts: List[Dict[str, object]] = []
    for change in changes:
        target_path = change.get("target_path")
        backup_path = Path(change.get("backup_path", ""))
        file_path = vault_path / (target_path or "")
        if change.get("risk_class") != "A":
            note_path = run_dir / "conflicts" / f"{target_path}.note"
            diff_path = run_dir / "conflicts" / f"{target_path}.diff"
            _write_conflict_note(note_path, t(lang, "conflict_b1_rollback"))
            _write_conflict_note(diff_path, "")
            conflicts.append(
                {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
            )
            continue

        if not file_path.exists() or not backup_path.exists():
            note_path = run_dir / "conflicts" / f"{target_path}.note"
            diff_path = run_dir / "conflicts" / f"{target_path}.diff"
            _write_conflict_note(note_path, t(lang, "conflict_missing_backup"))
            _write_conflict_note(diff_path, "")
            conflicts.append(
                {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
            )
            continue

        current_content = _read_text(file_path)
        current_hash = _hash_text(current_content)
        if current_hash != change.get("after_hash"):
            diff_path = run_dir / "conflicts" / f"{target_path}.diff"
            note_path = run_dir / "conflicts" / f"{target_path}.note"
            before_content = backup_path.read_text(encoding="utf-8")
            _write_diff(diff_path, before_content, current_content, target_path)
            _write_conflict_note(
                note_path,
                t(lang, "conflict_changed_rollback"),
            )
            conflicts.append(
                {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
            )
            continue

        backup_content = backup_path.read_text(encoding="utf-8")
        _atomic_write(file_path, backup_content)

    if conflicts:
        _ensure_howto(run_dir / "conflicts", lang)
    return ApplyResult(
        return_code=2 if conflicts else 0,
        conflicts=conflicts,
        changes=changes,
        waited_sec=0,
        starvation=False,
        fallback="none",
        offline_lock=False,
    )


def rollback_run(
    run_id: str,
    base_dir: Path,
    item_id: Optional[str] = None,
    target_path: Optional[str] = None,
    lang: str = "en",
) -> ApplyResult:
    if item_id and target_path:
        print(t(lang, "rollback_item_file_conflict"))
        return ApplyResult(
            return_code=20,
            conflicts=[],
            changes=[],
            waited_sec=0,
            starvation=False,
            fallback="none",
            offline_lock=False,
        )

    data, run_dir = _load_run_log(run_id, base_dir, lang)
    if data is None:
        return ApplyResult(
            return_code=20,
            conflicts=[],
            changes=[],
            waited_sec=0,
            starvation=False,
            fallback="none",
            offline_lock=False,
        )

    changes = data.get("changes", [])
    vault_path = Path(data.get("vault", "."))

    if item_id or target_path:
        if item_id:
            selected = [change for change in changes if change.get("action_id") == item_id]
            if not selected:
                print(t(lang, "rollback_no_action", action_id=item_id))
                return ApplyResult(
                    return_code=20,
                    conflicts=[],
                    changes=[],
                    waited_sec=0,
                    starvation=False,
                    fallback="none",
                    offline_lock=False,
                )
        else:
            selected = [change for change in changes if change.get("target_path") == target_path]
            if not selected:
                print(t(lang, "rollback_no_file", path=target_path))
                return ApplyResult(
                    return_code=20,
                    conflicts=[],
                    changes=[],
                    waited_sec=0,
                    starvation=False,
                    fallback="none",
                    offline_lock=False,
                )

        for change in selected:
            if change.get("risk_class") != "A":
                print(t(lang, "rollback_non_a"))
                return ApplyResult(
                    return_code=20,
                    conflicts=[],
                    changes=[],
                    waited_sec=0,
                    starvation=False,
                    fallback="none",
                    offline_lock=False,
                )

        _dependency_notice(selected, lang)
        conflicts: List[Dict[str, object]] = []
        for change in selected:
            _rollback_change_partial(change, vault_path, run_dir, conflicts, lang)

        if conflicts:
            _ensure_howto(run_dir / "conflicts", lang)
        return ApplyResult(
            return_code=2 if conflicts else 0,
            conflicts=conflicts,
            changes=selected,
            waited_sec=0,
            starvation=False,
            fallback="none",
            offline_lock=False,
        )

    return _rollback_full(changes, run_dir, vault_path, lang)
