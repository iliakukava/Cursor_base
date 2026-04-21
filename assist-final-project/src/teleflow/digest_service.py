from __future__ import annotations

import logging
from datetime import datetime, timezone

from .collector import collect_candidates
from .models import AppConfig
from .publisher import build_digest_text
from .ranker import rank_candidates
from .state_store import StateStore
from .summarizer import DigestAnnotator
from .telegram_client import TgUserClient

LOGGER = logging.getLogger(__name__)


async def build_digest(config: AppConfig, tg: TgUserClient) -> str:
    LOGGER.info("Дайджест: загрузка каналов из папок %s", config.source_folder_names)
    channels = await tg.get_channels_from_folders(config.source_folder_names)
    if not channels:
        LOGGER.warning("Нет каналов для обработки.")
        return "Подходящие каналы для выбранных папок не найдены."

    snapshots = await tg.get_inbox_snapshots(channels)
    candidates = await collect_candidates(
        tg=tg,
        channels=channels,
        lookback_hours=config.lookback_hours,
        keywords=config.keywords,
        snapshots=snapshots,
        max_messages_per_channel=config.collect_max_messages_per_channel,
    )
    annotator = DigestAnnotator(config)
    annotated = annotator.annotate(candidates)
    ranked = rank_candidates(annotated)
    return build_digest_text(ranked, config.digest_top_n, config.lookback_hours)


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
