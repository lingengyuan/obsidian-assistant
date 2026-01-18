from __future__ import annotations

from pathlib import Path

from cli_helpers import run_oka


def test_doctor_output_zh(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = run_oka(
        ["doctor", "--vault", str(vault_path), "--lang", "zh"], cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    assert "Doctor 报告" in result.stdout
    assert "路径检查" in result.stdout


def test_run_report_zh(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    vault_path = repo_root / "tests" / "fixtures" / "sample_vault"

    result = run_oka(["run", "--vault", str(vault_path), "--lang", "zh"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    report_path = tmp_path / "reports" / "report.md"
    report = report_path.read_text(encoding="utf-8")
    assert "Obsidian Assistant 报告" in report
    assert "## 摘要" in report
    assert "## 下一步建议" in report
