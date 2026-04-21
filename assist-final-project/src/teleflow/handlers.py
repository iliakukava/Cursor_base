from __future__ import annotations

import logging

from telethon import events
from telethon.errors.rpcerrorlist import PeerFloodError
from telethon.tl.types import PeerChannel

from .digest_service import run_digest_once
from .fsm import ConversationState
from .knowledge import (
    count_saved_entries_by_theme,
    read_theme_entries,
    resolve_theme,
    save_knowledge_entry,
    theme_choices,
)
from .models import AppConfig
from .telegram_client import TgUserClient
from .write_synthesizer import synthesize_post

LOGGER = logging.getLogger(__name__)


def register_handlers(tg: TgUserClient, config: AppConfig, state: ConversationState) -> None:
    @tg.client.on(events.NewMessage(incoming=True))
    async def on_new_message(event):  # pragma: no cover - integration behavior
        if not event.is_private:
            return

        sender_id = int(event.sender_id or 0)
        if sender_id <= 0 or sender_id not in config.allowed_user_ids:
            return

        raw_text = (event.raw_text or "").strip()
        lowered = raw_text.lower()

        if lowered.startswith("/stats"):
            rows = count_saved_entries_by_theme(config)
            total = sum(n for _, n in rows)
            body = "\n".join(f"• {theme}: {n}" for theme, n in rows)
            await event.reply(f"Сохранённых постов в базе: {total}\n\n{body}")
            return

        if lowered.startswith("/digest"):
            await event.reply("Собираю дайджест, это может занять до пары минут...")
            try:
                await run_digest_once(config, tg, target=sender_id, preview_target=sender_id)
            except PeerFloodError:
                await event.reply(
                    "Дайджест собран, но Telegram временно не даёт отправить весь текст в ЛС (лимит PeerFlood). "
                    "Попробуйте позже или выставьте DRY_RUN=false и отправку в TARGET_CHANNEL."
                )
            return

        if lowered.startswith("/write"):
            parts = raw_text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply("Укажи тему: `/write спорт`", parse_mode="md")
                return
            theme = resolve_theme(config, parts[1])
            if not theme:
                await event.reply(_theme_prompt(config, "Тема не распознана. Выбери из списка:"))
                return
            entries = read_theme_entries(config, theme)
            if not entries:
                await event.reply(f"По теме '{theme}' пока нет сохраненных постов.")
                return
            await event.reply(f"Генерирую пост по теме '{theme}'...")
            post_text = synthesize_post(config, theme, entries)
            await tg.send_text(sender_id, post_text)
            return

        pending = state.get_pending(sender_id)
        if pending is not None:
            theme = resolve_theme(config, raw_text)
            if not theme:
                await event.reply(_theme_prompt(config, "Тема не распознана. Выбери из списка:"))
                return
            save_knowledge_entry(
                config,
                text=pending.text,
                theme=theme,
                source_link=pending.source_link,
            )
            state.clear_pending(sender_id)
            await event.reply(f"Сохранено в тему: {theme}")
            return

        message = event.message
        if getattr(message, "fwd_from", None):
            text = (message.message or "").strip()
            if not text:
                await event.reply("Сохраняю только текстовые посты. Этот forward пропущен.")
                return

            state.set_pending(sender_id, text, _extract_source_link(message))
            await event.reply(_theme_prompt(config, "Куда отнести этот пост?"))
            return

        if raw_text.startswith("/"):
            await event.reply(_help_text(config))
            return
        if raw_text:
            await event.reply(_help_text(config))


def _help_text(config: AppConfig) -> str:
    folders = ", ".join(config.source_folder_names) or "—"
    themes = ", ".join(theme_choices(config)) or "—"
    target = config.target_channel or "не задан (см. TARGET_CHANNEL в .env)"
    return (
        "Команда или сообщение не распознаны.\n\n"
        "Что можно сделать:\n"
        "• /digest — собрать дайджест из непрочитанного по папкам Telegram\n"
        "• /stats — сколько постов сохранено по каждой теме (THEMES)\n"
        "• /write <тема> — сгенерировать пост из сохранённых материалов (сначала forward + тема)\n"
        "• Перешлите сюда текстовый пост (forward), чтобы добавить его в базу по теме\n\n"
        f"Папки для дайджеста (SOURCE_FOLDER_NAMES): {folders}\n"
        f"Темы для базы и /write (THEMES): {themes}\n"
        f"Канал для отправки (TARGET_CHANNEL): {target}\n"
    )


def _theme_prompt(config: AppConfig, title: str) -> str:
    options = "\n".join(f"{idx}. {theme}" for idx, theme in enumerate(theme_choices(config), start=1))
    return f"{title}\n\n{options}"


def _extract_source_link(message) -> str | None:
    forward = getattr(message, "forward", None)
    if forward:
        chat = getattr(forward, "chat", None)
        channel_post = getattr(forward, "channel_post", None)
        if chat and channel_post:
            username = getattr(chat, "username", None)
            chat_id = getattr(chat, "id", None)
            if username:
                return f"https://t.me/{username}/{channel_post}"
            if chat_id:
                normalized = str(chat_id).replace("-100", "")
                return f"https://t.me/c/{normalized}/{channel_post}"

    fwd_from = getattr(message, "fwd_from", None)
    from_id = getattr(fwd_from, "from_id", None)
    channel_post = getattr(fwd_from, "channel_post", None)
    if isinstance(from_id, PeerChannel) and channel_post:
        normalized = str(from_id.channel_id).replace("-100", "")
        return f"https://t.me/c/{normalized}/{channel_post}"

    return None

