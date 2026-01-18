from __future__ import annotations

from oka.core.scoring import (
    ScoringConfig,
    clamp,
    compute_confidence,
    quantile_normalize,
)


def test_clamp_bounds() -> None:
    assert clamp(1.5, 0.0, 1.0) == 1.0
    assert clamp(-0.1, 0.0, 1.0) == 0.0


def test_filters_reduce_confidence() -> None:
    config = ScoringConfig(w_content=1.0, w_title=0.0, w_link=0.0)
    base_confidence, _ = compute_confidence(0.8, 0.0, 0.0, [], config)
    filtered_confidence, _ = compute_confidence(
        0.8, 0.0, 0.0, [("path_penalty", 0.5)], config
    )
    assert filtered_confidence < base_confidence


def test_quantile_normalize_interface() -> None:
    values = [0.1, 0.5, 0.9]
    normalized = quantile_normalize(values)
    assert len(normalized) == len(values)
    assert min(normalized) == 0.0
    assert max(normalized) == 1.0


def test_quantile_reduces_outlier_gap() -> None:
    raw = [0.99, 0.5, 0.49, 0.48]
    normalized = quantile_normalize(raw)
    raw_sorted = sorted(raw, reverse=True)
    norm_sorted = sorted(normalized, reverse=True)
    raw_gap = raw_sorted[0] - raw_sorted[1]
    norm_gap = norm_sorted[0] - norm_sorted[1]
    assert norm_gap < raw_gap
