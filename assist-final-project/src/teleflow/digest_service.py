from __future__ import annotations

import logging
from datetime import datetime, timezone

from .collector import collect_candidates, dedupe_candidates_by_fingerprint
from .models import AppConfig
from .publisher import build_digest_text
from .ranker import rank_candidates
from .state_store import StateStore
from .summarizer import DigestAnnotator
from .telegram_client import TgUserClient

LOGGER = logging.getLogger(__name__)
LOW_UNREAD_FALLBACK_THRESHOLD = 5
LOW_UNREAD_FALLBACK_LOOKBACK_HOURS = 5 * 24


async def build_digest(config: AppConfig, tg: TgUserClient) -> str:
    LOGGER.info("Дайджест: загрузка каналов из папок %s", config.source_folder_names)
    channels = await tg.get_channels_from_folders(config.source_folder_names)
    if not channels:
        LOGGER.warning("Нет каналов для обработки.")
        return "Подходящие каналы для выбранных папок не найдены."

    snapshots = await tg.get_inbox_snapshots(channels)
    total_unread = sum(snapshot.unread_count for snapshot in snapshots.values())
    use_recent_fallback = total_unread < LOW_UNREAD_FALLBACK_THRESHOLD
    effective_lookback_hours = config.lookback_hours
    if use_recent_fallback:
        effective_lookback_hours = max(
            config.lookback_hours,
            LOW_UNREAD_FALLBACK_LOOKBACK_HOURS,
        )
        LOGGER.info(
            "Непрочитанных постов мало (%d < %d): включен fallback по всем постам за %d часов.",
            total_unread,
            LOW_UNREAD_FALLBACK_THRESHOLD,
            effective_lookback_hours,
        )

    candidates = await collect_candidates(
        tg=tg,
        channels=channels,
        lookback_hours=effective_lookback_hours,
        keywords=config.keywords,
        snapshots=snapshots,
        max_messages_per_channel=config.collect_max_messages_per_channel,
        include_all_recent=use_recent_fallback,
    )
    deduped_candidates = dedupe_candidates_by_fingerprint(candidates, config.dedupe_text_max_chars)
    dropped = len(candidates) - len(deduped_candidates)
    if dropped > 0:
        LOGGER.info("Удалено дубликатов кандидатов: %d", dropped)
    candidates = deduped_candidates
    annotator = DigestAnnotator(config)
    annotated = annotator.annotate(candidates)
    ranked = rank_candidates(annotated)
    return build_digest_text(ranked, config.digest_top_n, effective_lookback_hours)


async def run_digest_once(
    config: AppConfig,
    tg: TgUserClient,
    target: str | int,
    preview_target: str | int | None = None,
) -> str:
    digest_text = await build_digest(config, tg)
    if config.dry_run:
        LOGGER.info("DRY_RUN=true, отправка пропущена")
        if preview_target is not None:
            await tg.send_text(preview_target, digest_text)
            LOGGER.info("DRY_RUN=true, отправлен preview в %s", preview_target)
        return digest_text

    await tg.send_text(target, digest_text)
    LOGGER.info("Дайджест отправлен в %s", target)
    StateStore(config.state_db_path).set_last_run(datetime.now(tz=timezone.utc))
    return digest_text
