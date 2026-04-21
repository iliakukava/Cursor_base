from __future__ import annotations

import math

from .models import PostCandidate


def _metric_score(item: PostCandidate) -> float:
    views_part = math.log1p(max(item.views, 0))
    forwards_part = math.log1p(max(item.forwards, 0)) * 1.5
    reactions_part = math.log1p(max(item.reactions, 0)) * 1.2
    length_part = min(len(item.text) / 1200.0, 1.0)
    keyword_part = min(item.keyword_hits * 0.8, 2.0)
    raw = views_part + forwards_part + reactions_part + length_part + keyword_part
    return max(0.0, min(10.0, raw))


def rank_candidates(candidates: list[PostCandidate]) -> list[PostCandidate]:
    for item in candidates:
        item.metrics_score = _metric_score(item)
        item.final_score = round((item.importance * 10.0) + item.metrics_score, 3)

    candidates.sort(
        key=lambda x: (x.final_score, x.importance, x.keyword_hits, x.views, x.reactions),
        reverse=True,
    )
    return candidates

