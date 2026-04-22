from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PostCandidate:
    channel_id: int
    channel_title: str
    folder_name: str
    message_id: int
    date: datetime
    text: str
    views: int
    forwards: int
    reactions: int
    permalink: str
    keyword_hits: int = 0
    importance: int = 0
    ai_keep: bool = True
    ai_summary: str = ""
    ai_category: str = ""
    metrics_score: float = 0.0
    final_score: float = 0.0


@dataclass(slots=True)
class AppConfig:
    api_id: int
    api_hash: str
    phone_number: str
    session_name: str
    tg_proxy_enabled: bool
    tg_proxy_type: str
    tg_proxy_host: str | None
    tg_proxy_port: int | None
    tg_proxy_username: str | None
    tg_proxy_password: str | None
    tg_proxy_secret: str | None
    tg_proxy_rdns: bool
    tg_connect_timeout_sec: int
    tg_connect_total_sec: int
    tg_connection_retries: int
    tg_retry_delay_sec: int
    tg_rpc_timeout_sec: int
    run_once_budget_sec: int
    source_folder_names: list[str]
    keywords: list[str]
    target_channel: str | None
    digest_top_n: int
    lookback_hours: int
    openrouter_api_key: str
    openrouter_model: str
    openrouter_max_tokens: int
    openrouter_timeout_sec: int
    openrouter_annotate_budget_sec: int
    openrouter_digest_batch_size: int
    openrouter_digest_text_chars: int
    openrouter_digest_max_items: int
    relevance_only: bool
    dry_run: bool
    state_db_path: str
    log_level: str
    allowed_user_ids: set[int]
    themes: list[str]
    theme_dirs: dict[str, str]
    data_dir: str
    dedupe_text_max_chars: int
    list_entries_limit: int
    write_max_files: int
    write_max_total_chars: int
    write_styles: dict[str, str]
    output_lang: str
    collect_max_messages_per_channel: int
