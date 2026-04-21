from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .models import PostCandidate


def _topic(item: PostCandidate) -> str:
    if item.ai_category:
        return item.ai_category
    return item.folder_name


def build_digest_text(items: list[PostCandidate], top_n: int, lookback_hours: int) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    selected = items if top_n <= 0 else items[:top_n]
    lines: list[str] = [
        f"Дайджест непрочитанного (не старше {lookback_hours} ч, {now})",
        "",
    ]

    if not selected:
        lines.append("Сегодня подходящих постов не найдено.")
        return "\n".join(lines)

    grouped: dict[str, list[PostCandidate]] = defaultdict(list)
    for item in selected:
        grouped[item.folder_name].append(item)

    for folder_name in sorted(grouped.keys()):
        lines.append(f"{folder_name}")
        lines.append("-" * max(8, len(folder_name)))
        bucket = sorted(grouped[folder_name], key=lambda x: (x.importance, x.final_score), reverse=True)
        for idx, item in enumerate(bucket, start=1):
            lines.append(f"{idx}. Тема: {_topic(item)}")
            lines.append(f"   Суть: {item.ai_summary or item.text[:260].replace(chr(10), ' ')}")
            lines.append(f"   Ссылка: {item.permalink}")
            lines.append("")

    return "\n".join(lines).strip()

