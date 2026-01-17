from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from difflib import unified_diff


@dataclass
class ApplyResult:
    return_code: int
    conflicts: List[Dict[str, object]]
    changes: List[Dict[str, object]]
    waited_sec: int
    starvation: bool
    fallback: str
    offline_lock: bool


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
    if idx > 0 and lines[idx - 1].strip().lower() == "## related":
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


def _ensure_howto(conflicts_dir: Path) -> None:
    howto_path = conflicts_dir / "HOWTO.txt"
    if howto_path.exists():
        return
    howto_path.write_text(
        "Conflicts generated by oka.\n\n"
        "Apply diff manually:\n"
        "  patch -p0 < <file>.diff\n"
        "  git apply <file>.diff\n",
        encoding="utf-8",
    )


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


def _prompt_confirmation(summary: Dict[str, object]) -> bool:
    file_counts = summary["files"]
    top_files = sorted(file_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    print("\nApply Summary")
    print("-------------")
    print(f"Actions: {summary['count']}")
    print(f"Files affected: {len(file_counts)}")
    if top_files:
        print("Top files:")
        for path, count in top_files:
            print(f"- {path} ({count})")

    while True:
        answer = input("Apply changes? [y/n/preview]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer == "preview":
            print("\nPreview")
            print("-------")
            for item in summary["items"][:20]:
                print(
                    f"{item['id']} {item['type']} -> {item['target_path']} (conf {item['confidence']:.2f})"
                )
        else:
            print("Please answer y, n, or preview.")


def _prompt_starvation_mode() -> str:
    print("\nVault sync activity detected.")
    print("Choose a fallback mode:")
    print("- append: apply append-block actions only")
    print("- all: apply all Class A actions")
    print("- abort: stop without applying changes")

    while True:
        answer = input("Fallback [append/all/abort]: ").strip().lower()
        if answer in ("append", "all", "abort"):
            return answer
        print("Please answer append, all, or abort.")


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
    ttl_sec: int = 60,
) -> ApplyResult:
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
        print(f"Write lease denied: {message}")
        return ApplyResult(
            return_code=12,
            conflicts=[],
            changes=[],
            waited_sec=waited_sec,
            starvation=starvation,
            fallback=fallback,
            offline_lock=offline_lock_created,
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
        append_items = [
            item
            for item in class_a_items
            if item.get("type") == "append_related_links_section"
        ]
        applicable = class_a_items

        if starvation:
            if not yes:
                choice = _prompt_starvation_mode()
                if choice == "abort":
                    print("Apply aborted due to sync activity.")
                    print("Tip: pause sync or watch the vault for a quiet window, then retry.")
                    return ApplyResult(
                        return_code=11,
                        conflicts=[],
                        changes=[],
                        waited_sec=waited_sec,
                        starvation=True,
                        fallback="abort",
                        offline_lock=offline_lock_created,
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
                print("No applicable actions available under starvation fallback.")
                print("Tip: pause sync or watch the vault for a quiet window, then retry.")
                return ApplyResult(
                    return_code=11,
                    conflicts=[],
                    changes=[],
                    waited_sec=waited_sec,
                    starvation=True,
                    fallback=fallback or "none",
                    offline_lock=offline_lock_created,
                )
            return ApplyResult(
                return_code=0,
                conflicts=[],
                changes=[],
                waited_sec=waited_sec,
                starvation=False,
                fallback="none",
                offline_lock=offline_lock_created,
            )

        summary = _summarize_items(applicable)
        if not yes:
            if not _prompt_confirmation(summary):
                return ApplyResult(
                    return_code=0,
                    conflicts=[],
                    changes=[],
                    waited_sec=waited_sec,
                    starvation=starvation,
                    fallback=fallback,
                    offline_lock=offline_lock_created,
                )

        for item in applicable:
            target_path = item.get("target_path") or ""
            if not target_path:
                continue
            file_path = _relative_target(vault_path, target_path)
            if not file_path.exists():
                note_path = conflicts_dir / f"{target_path}.note"
                diff_path = conflicts_dir / f"{target_path}.diff"
                _write_conflict_note(note_path, "Target file missing; cannot apply.")
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
                    "File changed since plan generation; apply skipped.",
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
            _ensure_howto(conflicts_dir)
    finally:
        if offline_lock_cleanup:
            remove_offline_lock(offline_lock_path)
        release_write_lease(locks_dir)

    return_code = 2 if conflicts else 0
    return ApplyResult(
        return_code=return_code,
        conflicts=conflicts,
        changes=changes,
        waited_sec=waited_sec,
        starvation=starvation,
        fallback=fallback,
        offline_lock=offline_lock_created,
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


def _load_run_log(run_id: str, base_dir: Path) -> Tuple[Optional[Dict[str, object]], Path]:
    run_dir = base_dir / "reports" / "runs" / run_id
    log_path = run_dir / "run-log.json"
    if not log_path.exists():
        print(f"Run log not found: {log_path}")
        return None, run_dir
    data = json.loads(log_path.read_text(encoding="utf-8"))
    return data, run_dir


def _dependency_notice(changes: List[Dict[str, object]]) -> None:
    selected_ids = {change.get("action_id") for change in changes}
    missing: List[str] = []
    for change in changes:
        for dep in change.get("dependencies", []) or []:
            if dep not in selected_ids:
                missing.append(dep)
    if missing:
        unique = ", ".join(sorted(set(missing)))
        print(f"Note: dependencies not selected for rollback: {unique}")


def _rollback_change_partial(
    change: Dict[str, object],
    vault_path: Path,
    run_dir: Path,
    conflicts: List[Dict[str, object]],
) -> None:
    target_path = change.get("target_path") or ""
    file_path = Path(vault_path) / target_path
    if not target_path or not file_path.exists():
        note_path = run_dir / "conflicts" / f"{target_path}.note"
        diff_path = run_dir / "conflicts" / f"{target_path}.diff"
        _write_conflict_note(note_path, "Missing file; rollback skipped.")
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
        detail = "Missing targets for rollback: " + ", ".join(missing) if missing else "No changes applied."
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
) -> ApplyResult:
    conflicts: List[Dict[str, object]] = []
    for change in changes:
        target_path = change.get("target_path")
        backup_path = Path(change.get("backup_path", ""))
        file_path = vault_path / (target_path or "")

        if not file_path.exists() or not backup_path.exists():
            note_path = run_dir / "conflicts" / f"{target_path}.note"
            diff_path = run_dir / "conflicts" / f"{target_path}.diff"
            _write_conflict_note(note_path, "Missing file or backup; rollback skipped.")
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
                "File modified after apply; rollback skipped.",
            )
            conflicts.append(
                {"target_path": target_path, "diff_path": str(diff_path), "note_path": str(note_path)}
            )
            continue

        backup_content = backup_path.read_text(encoding="utf-8")
        _atomic_write(file_path, backup_content)

    if conflicts:
        _ensure_howto(run_dir / "conflicts")
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
) -> ApplyResult:
    if item_id and target_path:
        print("Error: use either --item or --file, not both.")
        return ApplyResult(
            return_code=20,
            conflicts=[],
            changes=[],
            waited_sec=0,
            starvation=False,
            fallback="none",
            offline_lock=False,
        )

    data, run_dir = _load_run_log(run_id, base_dir)
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
                print(f"No matching action for id: {item_id}")
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
                print(f"No matching changes for file: {target_path}")
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
                print("Partial rollback only supports Class A actions. Use Git revert for others.")
                return ApplyResult(
                    return_code=20,
                    conflicts=[],
                    changes=[],
                    waited_sec=0,
                    starvation=False,
                    fallback="none",
                    offline_lock=False,
                )

        _dependency_notice(selected)
        conflicts: List[Dict[str, object]] = []
        for change in selected:
            _rollback_change_partial(change, vault_path, run_dir, conflicts)

        if conflicts:
            _ensure_howto(run_dir / "conflicts")
        return ApplyResult(
            return_code=2 if conflicts else 0,
            conflicts=conflicts,
            changes=selected,
            waited_sec=0,
            starvation=False,
            fallback="none",
            offline_lock=False,
        )

    return _rollback_full(changes, run_dir, vault_path)
