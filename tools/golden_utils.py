from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

RUN_ID_RE = re.compile(r"\d{8}_\d{6}_[0-9a-f]{6}")
TIMESTAMP_KEYS = {"generated_at", "started_at", "ended_at", "created_at", "expires_at"}
PATH_KEYS = {
    "vault",
    "patch_path",
    "backup_path",
    "diff_path",
    "note_path",
    "path",
}


def _list_sort_key(item: dict[str, Any]) -> str | None:
    for key in ("action_id", "id", "target_path", "path", "file", "note_path"):
        value = item.get(key)
        if value is not None:
            return str(value)
    return None


def _maybe_sort_list(items: list[Any]) -> list[Any]:
    if not items:
        return items
    if not all(isinstance(item, dict) for item in items):
        return items
    keys = [_list_sort_key(item) for item in items]
    if any(key is None for key in keys):
        return items
    return [item for _, item in sorted(zip(keys, items), key=lambda pair: pair[0])]


def _normalize_path(value: str, base_dir: Path | None, vault_dir: Path | None) -> str:
    normalized = value.replace("\\", "/")
    if base_dir:
        normalized = normalized.replace(base_dir.as_posix(), "<BASE_DIR>")
    if vault_dir:
        normalized = normalized.replace(vault_dir.as_posix(), "<VAULT>")
    normalized = RUN_ID_RE.sub("<RUN_ID>", normalized)
    return normalized


def _normalize_text(value: str, base_dir: Path | None, vault_dir: Path | None) -> str:
    normalized = RUN_ID_RE.sub("<RUN_ID>", value)
    return _normalize_path(normalized, base_dir, vault_dir)


def normalize_json(
    data: Any,
    *,
    base_dir: Path | None = None,
    vault_dir: Path | None = None,
) -> Any:
    if isinstance(data, dict):
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            if key == "run_id":
                normalized[key] = "<RUN_ID>"
                continue
            if key.endswith("_hash"):
                normalized[key] = "<HASH>"
                continue
            if key in TIMESTAMP_KEYS:
                normalized[key] = "<TIMESTAMP>"
                continue
            if isinstance(value, (int, float)) and key.endswith("_ms"):
                normalized[key] = 0
                continue
            if key in PATH_KEYS and isinstance(value, str):
                normalized[key] = _normalize_path(value, base_dir, vault_dir)
                continue
            normalized[key] = normalize_json(value, base_dir=base_dir, vault_dir=vault_dir)
        return normalized
    if isinstance(data, list):
        ordered = _maybe_sort_list(list(data))
        return [normalize_json(item, base_dir=base_dir, vault_dir=vault_dir) for item in ordered]
    if isinstance(data, str):
        return _normalize_text(data, base_dir, vault_dir)
    return data


def json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def extract_related_block(content: str) -> str:
    lines = content.splitlines()
    if "## Related" not in lines:
        return ""
    start = lines.index("## Related")
    block: list[str] = []
    for line in lines[start:]:
        if line.startswith("## ") and line != "## Related" and block:
            break
        block.append(line)
    return "\n".join(block).strip() + "\n"


def build_reasoning_sample(item: dict[str, Any]) -> str:
    reason = item.get("reason", {})
    payload = {
        "action_id": item.get("id"),
        "type": item.get("type"),
        "confidence": item.get("confidence"),
        "reason": reason,
    }
    return json_dumps(payload)


def summarize_conflicts(conflicts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(conflicts)
    return {
        "count": len(items),
        "types": {},
        "items": items,
    }
