from __future__ import annotations

from pathlib import Path

import pytest

from oka.core.pipeline import scan_vault


def test_scan_throttle_sleep_ms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("a", encoding="utf-8")
    (vault / "b.md").write_text("b", encoding="utf-8")

    calls = {"count": 0}

    def fake_sleep(_: float) -> None:
        calls["count"] += 1

    monkeypatch.setattr("oka.core.pipeline.time.sleep", fake_sleep)

    scan_vault(vault, max_file_mb=5, sleep_ms=1)
    assert calls["count"] >= 2
