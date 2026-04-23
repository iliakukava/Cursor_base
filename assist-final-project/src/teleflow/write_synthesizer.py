from __future__ import annotations

import json
import logging
import re
from typing import Any

from .models import AppConfig
from .openrouter import llm_chat

LOGGER = logging.getLogger(__name__)


def synthesize_post(
    config: AppConfig, topic: str, entries: list[dict[str, Any]]
) -> str:
    selected = _select_relevant_entries(topic, entries)[: config.write_max_files]
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
        return f"Недостаточно контекста: в сохранённых постах нет материалов по теме '{topic}'."

    prompt = _build_prompt(topic, limited, config.output_lang)
    api_key = config.openrouter_api_key if config.llm_provider == "openrouter" else config.yandex_api_key
    model = config.openrouter_model if config.llm_provider == "openrouter" else config.yandex_model
    out = llm_chat(
        provider=config.llm_provider,
        api_key=api_key,
        model=model,
        system=(
            "Ты редактор Telegram-постов. Пиши цельный связный текст по материалам пользователя. "
            "Без списка источников в конце, без выдуманных фактов."
        ),
        user=prompt,
        timeout_sec=config.openrouter_timeout_sec,
        max_tokens=min(config.openrouter_max_tokens, 8192),
        temperature=0.35,
        yandex_folder_id=config.yandex_folder_id,
    )
    if out:
        return out
    LOGGER.warning("LLM не вернул текст для /write.")
    return _fallback_text(topic, limited)


def _build_prompt(
    topic: str, items: list[dict[str, str]], output_lang: str
) -> str:
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
        f"Тема: {topic}\n"
        "Ниже материалы:\n"
        f"{payload}\n\n"
        "Верни только готовый текст поста."
    )


def _fallback_text(topic: str, items: list[dict[str, str]]) -> str:
    first = items[0]["text"][:900]
    return (
        f"Черновик по теме '{topic}':\n\n"
        f"{first}\n\n"
        "OpenRouter не вернул ответ — упрощённый fallback."
    )


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Zа-яА-Я0-9]{3,}", text.lower())}


def _select_relevant_entries(topic: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    topic_tokens = _tokenize(topic)
    if not topic_tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in entries:
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        overlap = len(topic_tokens & _tokenize(text))
        if overlap <= 0:
            continue
        scored.append((overlap, entry))

    scored.sort(key=lambda item: (item[0], str(item[1].get("created_at", ""))), reverse=True)
    return [entry for _, entry in scored]
