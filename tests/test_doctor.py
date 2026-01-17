from __future__ import annotations

from pathlib import Path

from cli_helpers import run_oka


def test_doctor_reports_encoding_and_line_endings(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = run_oka(["doctor", "--vault", str(vault_path)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    stdout = result.stdout
    assert "Encoding:" in stdout
    assert "Line endings:" in stdout
    assert "utf8_bom=" in stdout
    assert "crlf=" in stdout
