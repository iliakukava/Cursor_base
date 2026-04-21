from __future__ import annotations

import json
import logging
from typing import Any

from .models import AppConfig
from .openrouter import openrouter_chat

LOGGER = logging.getLogger(__name__)


def synthesize_post(config: AppConfig, theme: str, entries: list[dict[str, Any]]) -> str:
    selected = entries[: config.write_max_files]
    limited: list[dict[str, str]] = []
    total_chars = 0
    for item in selected:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if total_chars + len(text) > config.write_max_total_chars and limited:
            break
        limited.append(
            {
                "text": text,
                "source_link": str(item.get("source_link", "")).strip(),
            }
        )
        total_chars += len(text)

    if not limited:
        return f"По теме '{theme}' нет текстовых материалов для генерации."

    prompt = _build_prompt(theme, limited, config.output_lang)
    out = openrouter_chat(
        api_key=config.openrouter_api_key,
        model=config.openrouter_model,
        system=(
            "Ты редактор Telegram-постов. Пиши цельный связный текст по материалам пользователя. "
            "Без списка источников в конце, без выдуманных фактов."
        ),
        user=prompt,
        timeout_sec=config.openrouter_timeout_sec,
        max_tokens=min(config.openrouter_max_tokens, 8192),
        temperature=0.35,
    )
    if out:
        return out
    LOGGER.warning("OpenRouter не вернул текст для /write.")
    return _fallback_text(theme, limited)


def _build_prompt(theme: str, items: list[dict[str, str]], output_lang: str) -> str:
    instructions = (
        "Ты пишешь авторский Telegram-пост на основе подборки материалов. "
        "Синтезируй одну общую идею. Не пересказывай каждый источник по отдельности. "
        "Не выдумывай факты вне входного контекста. "
        "Стиль: живой, цельный, без списков источников в конце."
    )
    lang_hint = "Пиши полностью на русском языке." if output_lang == "ru" else ""
    payload = json.dumps(items, ensure_ascii=False)
    return (
        f"{instructions}\n{lang_hint}\n"
        f"Тема: {theme}\n"
        "Ниже материалы:\n"
        f"{payload}\n\n"
        "Верни только готовый текст поста."
    )


def _fallback_text(theme: str, items: list[dict[str, str]]) -> str:
    first = items[0]["text"][:900]
    return (
        f"Черновик по теме '{theme}':\n\n"
        f"{first}\n\n"
        "OpenRouter не вернул ответ — упрощённый fallback."
    )
