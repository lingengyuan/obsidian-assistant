from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - fallback for older runtimes
    tomllib = None


def load_config(vault_path: Path, base_dir: Path) -> Dict[str, Any]:
    for path in (vault_path / "oka.toml", base_dir / "oka.toml"):
        if path.exists() and tomllib:
            return tomllib.loads(path.read_text(encoding="utf-8"))
    return {}


def _get_section(config: Dict[str, Any], section: str) -> Dict[str, Any]:
    node: Any = config
    for part in section.split("."):
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def get_int(config: Dict[str, Any], section: str, key: str, default: int) -> int:
    value = _get_section(config, section).get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float(config: Dict[str, Any], section: str, key: str, default: float) -> float:
    value = _get_section(config, section).get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_str(config: Dict[str, Any], section: str, key: str, default: str) -> str:
    value = _get_section(config, section).get(key, default)
    return str(value) if value is not None else default


def get_bool(config: Dict[str, Any], section: str, key: str, default: bool) -> bool:
    value = _get_section(config, section).get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default
