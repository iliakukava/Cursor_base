from __future__ import annotations

NOISE_MARKERS = ("реклама", "#ad", "розыгрыш", "promo")


def is_noisy_text(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in NOISE_MARKERS)

