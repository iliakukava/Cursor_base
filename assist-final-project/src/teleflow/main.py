from __future__ import annotations

import argparse
import asyncio
import logging

from .config import load_config
from .digest_service import run_digest_once
from .fsm import ConversationState
from .handlers import register_handlers
from .state_store import StateStore
from .telegram_client import TgUserClient

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TeleFlow userbot")
    parser.add_argument("--daemon", action="store_true", help="Запустить userbot в режиме ожидания")
    parser.add_argument("--once", action="store_true", help="Один цикл дайджеста и выход")
    return parser.parse_args()


def _resolve_once_target(config) -> str | int:
    if config.target_channel:
        return config.target_channel
    if config.allowed_user_ids:
        return sorted(config.allowed_user_ids)[0]
    return "me"


def _log_startup(config) -> None:
    model_name = config.openrouter_model if config.llm_provider == "openrouter" else config.yandex_model
    LOGGER.info(
        "Startup: proxy=%s type=%s dry_run=%s llm_provider=%s model=%s timeout=%ss annotate_budget=%ss connect_total=%ss rpc_timeout=%ss run_once_budget=%ss",
        "on" if config.tg_proxy_enabled else "off",
        config.tg_proxy_type,
        config.dry_run,
        config.llm_provider,
        model_name,
        config.openrouter_timeout_sec,
        config.openrouter_annotate_budget_sec,
        config.tg_connect_total_sec,
        config.tg_rpc_timeout_sec,
        config.run_once_budget_sec,
    )


async def run_once() -> None:
    config = load_config()
    logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))
    _log_startup(config)
    async with TgUserClient(config) as tg:
        target = _resolve_once_target(config)
        try:
            digest_text = await asyncio.wait_for(
                run_digest_once(config, tg, target=target),
                timeout=config.run_once_budget_sec,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"--once превысил лимит {config.run_once_budget_sec}с. "
                "Проверьте прокси/сеть и параметры LLM."
            ) from exc
        if config.dry_run:
            LOGGER.info("DRY_RUN=true, предпросмотр дайджеста:\n%s", digest_text)


async def run_daemon() -> None:
    config = load_config()
    logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))
    _log_startup(config)
    tg = TgUserClient(config)
    await tg.connect()
    state = ConversationState()
    store = StateStore(config.state_db_path)
    register_handlers(tg, config, state, store)
    LOGGER.info("Daemon режим запущен. Ожидание входящих сообщений...")
    await tg.client.run_until_disconnected()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.once and args.daemon:
        raise ValueError("Выберите один режим: либо --once, либо --daemon.")

    if args.once:
        asyncio.run(run_once())
        return

    asyncio.run(run_daemon())


if __name__ == "__main__":
    main()

