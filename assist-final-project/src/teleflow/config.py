from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import AppConfig


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_folders(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _parse_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)).strip())


def _parse_positive_int(name: str, default: int) -> int:
    value = _parse_int(name, default)
    if value <= 0:
        raise ValueError(f"{name} должен быть > 0")
    return value


def _parse_optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return int(raw)


def _parse_allowed_user_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    result: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        result.add(int(item))
    return result


def _parse_themes(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_theme_dirs(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            continue
        source, target = pair.split(":", 1)
        source = source.strip()
        target = target.strip()
        if source and target:
            mapping[source] = target
    return mapping


def load_config() -> AppConfig:
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)

    api_id_raw = os.getenv("API_ID", "").strip()
    if not api_id_raw:
        raise ValueError("API_ID не задан в .env")

    api_hash = os.getenv("API_HASH", "").strip()
    if not api_hash:
        raise ValueError("API_HASH не задан в .env")

    phone_number = os.getenv("PHONE_NUMBER", "").strip()
    if not phone_number:
        raise ValueError("PHONE_NUMBER не задан в .env")

    source_folder_names = _parse_folders(os.getenv("SOURCE_FOLDER_NAMES", "edu"))
    if not source_folder_names:
        raise ValueError("SOURCE_FOLDER_NAMES пуст. Укажите хотя бы одну папку.")

    themes = _parse_themes(os.getenv("THEMES", "спорт,философия,бизнес,саморазвитие"))
    if not themes:
        raise ValueError("THEMES пуст. Укажите минимум одну тему.")

    target_channel = os.getenv("TARGET_CHANNEL", "").strip() or None
    allowed_user_ids = _parse_allowed_user_ids(os.getenv("ALLOWED_USER_IDS"))
    if not allowed_user_ids:
        raise ValueError("ALLOWED_USER_IDS пуст. Укажите хотя бы один numeric Telegram user id.")

    tg_proxy_enabled = _parse_bool(os.getenv("TG_PROXY_ENABLED"), False)
    tg_proxy_type = os.getenv("TG_PROXY_TYPE", "socks5").strip().lower()
    tg_proxy_host = os.getenv("TG_PROXY_HOST", "").strip() or None
    tg_proxy_port = _parse_optional_int("TG_PROXY_PORT")
    tg_proxy_username = os.getenv("TG_PROXY_USERNAME", "").strip() or None
    tg_proxy_password = os.getenv("TG_PROXY_PASSWORD", "").strip() or None
    tg_proxy_secret = os.getenv("TG_PROXY_SECRET", "").strip() or None

    if tg_proxy_enabled:
        if tg_proxy_type not in {"socks5", "mtproto"}:
            raise ValueError("TG_PROXY_TYPE должен быть socks5 или mtproto.")
        if not tg_proxy_host or not tg_proxy_port:
            raise ValueError("TG_PROXY_ENABLED=true, но TG_PROXY_HOST или TG_PROXY_PORT не заполнены.")
        if tg_proxy_type == "mtproto" and not tg_proxy_secret:
            raise ValueError("Для TG_PROXY_TYPE=mtproto заполните TG_PROXY_SECRET.")

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY обязателен (https://openrouter.ai/keys).")

    openrouter_model = os.getenv("OPENROUTER_MODEL", "").strip() or "openai/gpt-4o-mini"

    return AppConfig(
        api_id=int(api_id_raw),
        api_hash=api_hash,
        phone_number=phone_number,
        session_name=os.getenv("SESSION_NAME", "userbot_session").strip(),
        tg_proxy_enabled=tg_proxy_enabled,
        tg_proxy_type=tg_proxy_type,
        tg_proxy_host=tg_proxy_host,
        tg_proxy_port=tg_proxy_port,
        tg_proxy_username=tg_proxy_username,
        tg_proxy_password=tg_proxy_password,
        tg_proxy_secret=tg_proxy_secret,
        tg_proxy_rdns=_parse_bool(os.getenv("TG_PROXY_RDNS"), True),
        tg_connect_timeout_sec=_parse_positive_int("TG_CONNECT_TIMEOUT_SEC", 20),
        tg_connect_total_sec=_parse_positive_int("TG_CONNECT_TOTAL_SEC", 120),
        tg_connection_retries=_parse_positive_int("TG_CONNECTION_RETRIES", 5),
        tg_retry_delay_sec=_parse_positive_int("TG_RETRY_DELAY_SEC", 2),
        tg_rpc_timeout_sec=_parse_positive_int("TG_RPC_TIMEOUT_SEC", 60),
        run_once_budget_sec=_parse_positive_int("RUN_ONCE_BUDGET_SEC", 420),
        source_folder_names=source_folder_names,
        keywords=_parse_keywords(os.getenv("KEYWORDS")),
        target_channel=target_channel,
        digest_top_n=_parse_int("DIGEST_TOP_N", 0),
        lookback_hours=_parse_int("LOOKBACK_HOURS", 48),
        openrouter_api_key=openrouter_api_key,
        openrouter_model=openrouter_model,
        openrouter_max_tokens=_parse_positive_int("OPENROUTER_MAX_TOKENS", 8192),
        openrouter_timeout_sec=_parse_positive_int("OPENROUTER_TIMEOUT_SEC", 120),
        openrouter_annotate_budget_sec=_parse_positive_int("OPENROUTER_ANNOTATE_BUDGET_SEC", 300),
        openrouter_digest_batch_size=_parse_positive_int("OPENROUTER_DIGEST_BATCH_SIZE", 8),
        openrouter_digest_text_chars=_parse_positive_int("OPENROUTER_DIGEST_TEXT_CHARS", 1600),
        openrouter_digest_max_items=_parse_int("OPENROUTER_DIGEST_MAX_ITEMS", 80),
        relevance_only=_parse_bool(os.getenv("RELEVANCE_ONLY"), False),
        dry_run=_parse_bool(os.getenv("DRY_RUN"), True),
        state_db_path=os.getenv("STATE_DB_PATH", "state.db").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        allowed_user_ids=allowed_user_ids,
        themes=themes,
        theme_dirs=_parse_theme_dirs(os.getenv("THEME_DIRS")),
        data_dir=os.getenv("DATA_DIR", "data").strip(),
        write_max_files=_parse_int("WRITE_MAX_FILES", 20),
        write_max_total_chars=_parse_int("WRITE_MAX_TOTAL_CHARS", 12000),
        output_lang=os.getenv("OUTPUT_LANG", "ru").strip().lower(),
        collect_max_messages_per_channel=_parse_positive_int("COLLECT_MAX_MESSAGES_PER_CHANNEL", 300),
    )
