from __future__ import annotations

from pathlib import Path

from oka.core.config import get_bool, get_int, load_config


def test_load_config_prefers_vault(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "oka.toml").write_text("[scan]\nmax_file_mb = 7\n", encoding="utf-8")
    data = load_config(vault_dir, tmp_path)
    assert get_int(data, "scan", "max_file_mb", 0) == 7


def test_get_bool_variants() -> None:
    config = {"flags": {"on": "true", "off": "0", "num": 1, "text": "yes"}}
    assert get_bool(config, "flags", "on", False) is True
    assert get_bool(config, "flags", "off", True) is False
    assert get_bool(config, "flags", "num", False) is True
    assert get_bool(config, "flags", "text", False) is True
