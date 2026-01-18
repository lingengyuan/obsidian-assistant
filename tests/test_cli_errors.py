from __future__ import annotations

import os
from pathlib import Path

from cli_helpers import run_oka


def _fixture_vault() -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_vault"


def test_run_requires_vault(tmp_path: Path) -> None:
    result = run_oka(["run"], cwd=tmp_path)
    assert result.returncode == 2
    assert "vault" in result.stderr.lower()


def test_run_uses_env_vault(tmp_path: Path) -> None:
    vault_path = _fixture_vault()
    previous = os.environ.get("VAULT_PATH")
    os.environ["VAULT_PATH"] = str(vault_path)
    try:
        result = run_oka(["run"], cwd=tmp_path)
        assert result.returncode == 0, result.stderr
    finally:
        if previous is None:
            os.environ.pop("VAULT_PATH", None)
        else:
            os.environ["VAULT_PATH"] = previous


def test_run_invalid_max_file_env(tmp_path: Path) -> None:
    vault_path = _fixture_vault()
    prev_vault = os.environ.get("VAULT_PATH")
    prev_max = os.environ.get("OKA_MAX_FILE_MB")
    os.environ["VAULT_PATH"] = str(vault_path)
    os.environ["OKA_MAX_FILE_MB"] = "not-a-number"
    try:
        result = run_oka(["run"], cwd=tmp_path)
        assert result.returncode == 0, result.stderr
    finally:
        if prev_vault is None:
            os.environ.pop("VAULT_PATH", None)
        else:
            os.environ["VAULT_PATH"] = prev_vault
        if prev_max is None:
            os.environ.pop("OKA_MAX_FILE_MB", None)
        else:
            os.environ["OKA_MAX_FILE_MB"] = prev_max


def test_doctor_init_config(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    result = run_oka(
        ["doctor", "--init-config", "--vault", str(vault_dir)], cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert (vault_dir / "oka.toml").exists()

    repeat = run_oka(
        ["doctor", "--init-config", "--vault", str(vault_dir)], cwd=tmp_path
    )
    assert repeat.returncode == 0
    assert "already exists" in repeat.stderr.lower()


def test_no_command_prints_help(tmp_path: Path) -> None:
    result = run_oka([], cwd=tmp_path)
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
