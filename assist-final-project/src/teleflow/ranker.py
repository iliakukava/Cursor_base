from __future__ import annotations

from .models import PostCandidate


def rank_candidates(candidates: list[PostCandidate]) -> list[PostCandidate]:
    for item in candidates:
        item.metrics_score = 0.0
        # Полностью LLM-режим: финальный score строится только из importance.
        item.final_score = round(float(item.importance), 3)

    candidates.sort(
        key=lambda x: (x.final_score, x.importance),
        reverse=True,
    )
    return candidates

