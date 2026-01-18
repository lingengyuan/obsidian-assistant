from __future__ import annotations

from oka.core.pipeline import _tokenize


def test_perf_smoke_tokenize() -> None:
    tokens = _tokenize("Alpha beta gamma 123")
    assert "alpha" in tokens
