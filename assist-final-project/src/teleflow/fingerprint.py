from __future__ import annotations

import hashlib
import re
import unicodedata

_MULTISPACE_RE = re.compile(r"\s+")


def normalize_for_dedupe(text: str, max_chars: int) -> str:
    """Normalize text for duplicate detection."""
    raw = (text or "").strip().lower()
    if not raw:
        return ""

    compact = _MULTISPACE_RE.sub("", raw)
    filtered_chars: list[str] = []
    for ch in compact:
        category = unicodedata.category(ch)
        if category in {"So", "Sk"}:
            continue
        filtered_chars.append(ch)
        if len(filtered_chars) >= max_chars:
            break
    return "".join(filtered_chars)


def content_fingerprint(text: str, max_chars: int) -> str:
    normalized = normalize_for_dedupe(text, max_chars)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
