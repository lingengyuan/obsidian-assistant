from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class ScoringConfig:
    w_content: float = 0.6
    w_title: float = 0.3
    w_link: float = 0.1
    clamp_min: float = 0.0
    clamp_max: float = 1.0
    path_penalty: float = 0.9
    min_related_confidence: float = 0.3
    merge_confidence: float = 0.85
    low_confidence: float = 0.45
    norm_method: str = "quantile"


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def quantile_normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    if len(values) == 1:
        return [1.0]
    sorted_vals = sorted(values)
    last_index = len(values) - 1
    normalized: List[float] = []
    for value in values:
        left = bisect_left(sorted_vals, value)
        right = bisect_right(sorted_vals, value) - 1
        rank = (left + right) / 2
        normalized.append(rank / last_index)
    return normalized


def compute_confidence(
    content_sim: float,
    title_sim: float,
    link_overlap: float,
    filters: Iterable[Tuple[str, float]],
    config: ScoringConfig,
) -> Tuple[float, List[str]]:
    base = (
        config.w_content * content_sim
        + config.w_title * title_sim
        + config.w_link * link_overlap
    )
    factor = 1.0
    filter_entries: List[str] = []
    for name, value in filters:
        factor *= value
        filter_entries.append(f"{name}={value:.2f}")
    confidence = clamp(base * factor, config.clamp_min, config.clamp_max)
    return confidence, filter_entries


def build_reason(
    content_sim: float,
    title_sim: float,
    link_overlap: float,
    filters: List[str],
    config: ScoringConfig,
    raw_content_sim: Optional[float] = None,
) -> Dict[str, object]:
    reason: Dict[str, object] = {
        "content_sim": round(content_sim, 3),
        "title_sim": round(title_sim, 3),
        "link_overlap": round(link_overlap, 3),
        "filters": filters,
        "weights": {
            "content": config.w_content,
            "title": config.w_title,
            "link": config.w_link,
        },
        "norm_method": config.norm_method,
    }
    if raw_content_sim is not None:
        reason["raw_content_sim"] = round(raw_content_sim, 3)
    return reason
