from __future__ import annotations

from cli_helpers import run_oka


def test_oka_help() -> None:
    result = run_oka(["--help"])
    assert result.returncode == 0
    assert "oka" in result.stdout.lower()


def test_oka_run_help() -> None:
    result = run_oka(["run", "--help"])
    assert result.returncode == 0
    assert "run" in result.stdout.lower()


def test_oka_doctor_help() -> None:
    result = run_oka(["doctor", "--help"])
    assert result.returncode == 0
    assert "doctor" in result.stdout.lower()
