from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .fingerprint import content_fingerprint
from .filters import is_noisy_text
from .models import PostCandidate
from .telegram_client import ChannelInboxSnapshot, SourceChannel, TgUserClient

LOGGER = logging.getLogger(__name__)


def reaction_count(msg) -> int:
    reactions = getattr(msg, "reactions", None)
    if not reactions or not getattr(reactions, "results", None):
        return 0
    return sum(int(getattr(item, "count", 0)) for item in reactions.results)


def permalink(channel: SourceChannel, message_id: int) -> str:
    if channel.username:
        return f"https://t.me/{channel.username}/{message_id}"
    normalized = str(channel.channel_id).replace("-100", "")
    return f"https://t.me/c/{normalized}/{message_id}"


async def collect_candidates(
    tg: TgUserClient,
    channels: list[SourceChannel],
    lookback_hours: int,
    keywords: list[str],
    snapshots: dict[int, ChannelInboxSnapshot],
    max_messages_per_channel: int,
    include_all_recent: bool = False,
) -> list[PostCandidate]:
    since_dt = datetime.now(tz=timezone.utc) - timedelta(hours=lookback_hours)
    items: list[PostCandidate] = []

    for channel in channels:
        snapshot = snapshots.get(channel.channel_id)
        if snapshot is None:
            LOGGER.warning("Snapshot непрочитанных не найден для канала %s", channel.title)
            continue
        if include_all_recent:
            scan_limit = max_messages_per_channel
        else:
            if snapshot.unread_count <= 0:
                LOGGER.info("Канал %s: непрочитанных нет", channel.title)
                continue
            scan_limit = min(max_messages_per_channel, snapshot.unread_count)
        count_before = len(items)
        if include_all_recent:
            message_iter = tg.iter_recent_messages(
                channel.entity,
                since_dt,
                max_messages=scan_limit,
            )
        else:
            message_iter = tg.iter_unread_messages(
                channel.entity,
                snapshot.read_inbox_max_id,
                since_dt,
                max_messages=scan_limit,
            )

        async for msg in message_iter:
            text = (msg.message or "").strip()
            if len(text) < 120:
                continue
            if is_noisy_text(text):
                continue
            text_lower = text.lower()
            keyword_hits = sum(1 for keyword in keywords if keyword in text_lower)

            items.append(
                PostCandidate(
                    channel_id=channel.channel_id,
                    channel_title=channel.title,
                    folder_name=channel.folder_name,
                    message_id=msg.id,
                    date=msg.date,
                    text=text,
                    views=int(getattr(msg, "views", 0) or 0),
                    forwards=int(getattr(msg, "forwards", 0) or 0),
                    reactions=reaction_count(msg),
                    permalink=permalink(channel, msg.id),
                    keyword_hits=keyword_hits,
                )
            )
        LOGGER.info(
            "Канал %s: +%d кандидатов (просканировано <= %d)",
            channel.title,
            len(items) - count_before,
            scan_limit,
        )

    LOGGER.info("Итого собранных кандидатов: %d", len(items))
    return items


def dedupe_candidates_by_fingerprint(
    candidates: list[PostCandidate], dedupe_text_max_chars: int
) -> list[PostCandidate]:
    seen: set[str] = set()
    unique: list[PostCandidate] = []
    for item in candidates:
        fingerprint = content_fingerprint(item.text, dedupe_text_max_chars)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(item)
    return unique

