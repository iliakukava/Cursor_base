from __future__ import annotations

import logging
from pathlib import Path
import shlex

from telethon import events
from telethon.errors.rpcerrorlist import PeerFloodError
from telethon.tl.types import PeerChannel

from .digest_service import run_digest_once
from .fsm import ConversationState
from .knowledge import (
    count_saved_entries_by_theme,
    delete_entry_by_id,
    list_theme_entries_preview,
    move_entry_by_id,
    normalize_entry_id,
    read_theme_entries,
    resolve_theme,
    save_knowledge_entry,
    theme_choices,
)
from .models import AppConfig
from .state_store import StateStore
from .telegram_client import TgUserClient
from .write_synthesizer import synthesize_post

LOGGER = logging.getLogger(__name__)


def register_handlers(
    tg: TgUserClient, config: AppConfig, state: ConversationState, store: StateStore
) -> None:
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

        if lowered.startswith("/list"):
            parts = raw_text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply("Укажи тему: `/list спорт`", parse_mode="md")
                return
            theme = resolve_theme(config, parts[1])
            if not theme:
                await event.reply(_theme_prompt(config, "Тема не распознана. Выбери из списка:"))
                return
            previews = list_theme_entries_preview(config, theme, config.list_entries_limit)
            if not previews:
                await event.reply(f"По теме '{theme}' пока нет записей.")
                return
            lines = [f"Последние записи по теме '{theme}' (до {config.list_entries_limit}):", ""]
            for item in previews:
                created = item.created_at.replace("T", " ")[:19] if item.created_at else "unknown time"
                lines.append(f"• {item.entry_id} · {created}")
                lines.append(f"  {item.preview}")
            await tg.send_text(sender_id, "\n".join(lines))
            return

        if lowered.startswith("/rm"):
            parts = raw_text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply("Укажи id: `/rm <id>`", parse_mode="md")
                return
            entry_id = normalize_entry_id(parts[1] or "")
            if not entry_id:
                await event.reply("ID должен быть 32 hex-символа (`/rm <id>`).", parse_mode="md")
                return
            removed_path = delete_entry_by_id(config, entry_id)
            if removed_path is None:
                await event.reply(f"Запись {entry_id} не найдена.")
                return
            undo_path = store.get_last_knowledge_entry(sender_id)
            if undo_path and Path(undo_path).resolve() == removed_path.resolve():
                store.clear_last_knowledge_entry(sender_id)
            await event.reply(f"Удалено: {entry_id}")
            return

        if lowered.startswith("/mv"):
            parts = raw_text.split(maxsplit=2)
            if len(parts) < 3:
                await event.reply("Формат: `/mv <id> <новая тема>`", parse_mode="md")
                return
            entry_id = normalize_entry_id(parts[1] or "")
            if not entry_id:
                await event.reply("ID должен быть 32 hex-символа (`/mv <id> <тема>`).", parse_mode="md")
                return
            new_theme = resolve_theme(config, parts[2])
            if not new_theme:
                await event.reply(_theme_prompt(config, "Тема не распознана. Выбери из списка:"))
                return
            moved = move_entry_by_id(config, entry_id, new_theme)
            if moved is None:
                await event.reply(f"Запись {entry_id} не найдена.")
                return
            await event.reply(
                f"Перенесено: {entry_id}\n"
                f"Из темы: {moved.old_theme}\n"
                f"В тему: {moved.new_theme}"
            )
            return

        if lowered.startswith("/undo"):
            undo_path_raw = store.get_last_knowledge_entry(sender_id)
            if not undo_path_raw:
                await event.reply("Нечего отменять: последнее сохранение не найдено.")
                return
            undo_path = Path(undo_path_raw)
            root = (Path(config.data_dir) / "knowledge").resolve()
            undo_path_resolved = undo_path.resolve()
            if root not in undo_path_resolved.parents:
                store.clear_last_knowledge_entry(sender_id)
                await event.reply("Undo-запись устарела и была сброшена.")
                return
            if not undo_path.exists():
                store.clear_last_knowledge_entry(sender_id)
                await event.reply("Файл последнего сохранения уже отсутствует.")
                return
            undo_id = normalize_entry_id(undo_path.name)
            undo_path.unlink()
            store.clear_last_knowledge_entry(sender_id)
            await event.reply(f"Отменено последнее сохранение ({undo_id or undo_path.name}).")
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
            theme, style_key, error_text = _parse_write_args(raw_text, config)
            if error_text:
                await event.reply(error_text, parse_mode="md")
                return
            if not theme:
                await event.reply(_theme_prompt(config, "Тема не распознана. Выбери из списка:"))
                return
            entries = read_theme_entries(config, theme)
            if not entries:
                await event.reply(f"По теме '{theme}' пока нет сохраненных постов.")
                return
            style_suffix = f" (стиль: {style_key})" if style_key else ""
            await event.reply(f"Генерирую пост по теме '{theme}'{style_suffix}...")
            post_text = synthesize_post(config, theme, entries, style_key=style_key)
            await tg.send_text(sender_id, post_text)
            return

        pending = state.get_pending(sender_id)
        if pending is not None:
            theme = resolve_theme(config, raw_text)
            if not theme:
                await event.reply(_theme_prompt(config, "Тема не распознана. Выбери из списка:"))
                return
            result = save_knowledge_entry(
                config,
                text=pending.text,
                theme=theme,
                source_link=pending.source_link,
            )
            state.clear_pending(sender_id)
            if result.ok and result.path:
                store.set_last_knowledge_entry(sender_id, str(result.path.resolve()))
                await event.reply(f"Сохранено в тему: {theme}\nID: {result.path.stem.replace('entry_', '')}")
            elif result.duplicate_theme:
                duplicate_id = normalize_entry_id(result.duplicate_path.name) if result.duplicate_path else None
                duplicate_tail = f"\nID: {duplicate_id}" if duplicate_id else ""
                await event.reply(
                    f"Уже сохранено в теме: {result.duplicate_theme}.{duplicate_tail}\n"
                    "Дубликат не записан."
                )
            else:
                await event.reply("Не удалось сохранить запись: пустой текст или ошибка данных.")
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
        "• /list <тема> — показать последние записи темы (id + хвост текста)\n"
        "• /rm <id> — удалить запись по id\n"
        "• /mv <id> <новая тема> — перенести запись в другую тему\n"
        "• /undo — отменить последнее сохранение (ваше)\n"
        "• /write <тема> [--style=<ключ>] — сгенерировать пост из материалов темы\n"
        "• Перешлите сюда текстовый пост (forward), чтобы добавить его в базу по теме\n\n"
        f"Папки для дайджеста (SOURCE_FOLDER_NAMES): {folders}\n"
        f"Темы для базы и /write (THEMES): {themes}\n"
        f"Канал для отправки (TARGET_CHANNEL): {target}\n"
        f"Доступные стили /write: {_styles_hint(config)}\n"
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


def _styles_hint(config: AppConfig) -> str:
    if not config.write_styles:
        return "нет (используется базовый стиль)"
    return ", ".join(sorted(config.write_styles.keys()))


def _parse_write_args(raw_text: str, config: AppConfig) -> tuple[str | None, str | None, str | None]:
    payload = raw_text[len("/write") :].strip()
    if not payload:
        return None, None, "Укажи тему: `/write спорт`"
    try:
        tokens = shlex.split(payload)
    except ValueError:
        return None, None, "Не удалось разобрать аргументы. Используй: `/write <тема> --style=<ключ>`"

    style_key: str | None = None
    theme_tokens: list[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token.startswith("--style="):
            style_key = token.split("=", 1)[1].strip().lower()
            idx += 1
            continue
        if token == "--style":
            if idx + 1 >= len(tokens):
                return None, None, "После `--style` нужен ключ стиля."
            style_key = tokens[idx + 1].strip().lower()
            idx += 2
            continue
        theme_tokens.append(token)
        idx += 1

    theme_raw = " ".join(theme_tokens).strip()
    theme = resolve_theme(config, theme_raw) if theme_raw else None

    if not theme and not style_key and len(theme_tokens) > 1:
        candidate_style = theme_tokens[-1].strip().lower()
        if candidate_style in config.write_styles:
            style_key = candidate_style
            theme = resolve_theme(config, " ".join(theme_tokens[:-1]))

    if style_key and style_key not in config.write_styles:
        return (
            None,
            None,
            f"Стиль `{style_key}` не найден. Доступно: {_styles_hint(config)}",
        )

    if not theme:
        return None, style_key, _theme_prompt(config, "Тема не распознана. Выбери из списка:")

    return theme, style_key, None

