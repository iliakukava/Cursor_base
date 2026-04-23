"""Вызовы LLM-провайдеров (OpenRouter / Yandex AI Studio) через urllib."""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

LOGGER = logging.getLogger(__name__)

OPENROUTER_API_V1 = "https://openrouter.ai/api/v1/chat/completions"
YANDEX_COMPLETION_V1 = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def llm_chat(
    *,
    provider: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
    max_tokens: int = 8192,
    temperature: float = 0.2,
    yandex_folder_id: str = "",
) -> str:
    provider_norm = (provider or "").strip().lower()
    if provider_norm == "yandex":
        return yandex_chat(
            api_key=api_key,
            folder_id=yandex_folder_id,
            model=model,
            system=system,
            user=user,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    return openrouter_chat(
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def openrouter_chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
    max_tokens: int = 8192,
    temperature: float = 0.2,
) -> str:
    """Текст первого choice или пустая строка при ошибке."""
    key = (api_key or "").strip()
    if not key:
        return ""

    body: dict[str, Any] = {
        "model": (model or "").strip(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": float(temperature),
        "max_tokens": int(max(64, max_tokens)),
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_API_V1, data=payload, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Authorization", f"Bearer {key}")

    referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
    title = os.getenv("OPENROUTER_APP_TITLE", "").strip()
    if referer:
        req.add_header("HTTP-Referer", referer)
    if title:
        req.add_header("X-Title", title)
    else:
        req.add_header("HTTP-Referer", "https://github.com/teleflow/assist-final-project")
        req.add_header("X-Title", "TeleFlow")

    ctx = ssl.create_default_context()
    raw = ""
    try:
        with urllib.request.urlopen(req, timeout=max(5, int(timeout_sec)), context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:1200]
        LOGGER.warning("OpenRouter HTTP %s: %s", exc.code, err_body)
        return ""
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        LOGGER.warning("OpenRouter: %s", exc)
        return ""

    if not raw.strip():
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        LOGGER.warning("OpenRouter: невалидный JSON (первые 200 симв.): %s", raw[:200])
        return ""

    try:
        choices = data.get("choices") or []
        if not choices:
            LOGGER.warning("OpenRouter: пустой choices")
            return ""
        msg = choices[0].get("message") or {}
        return (msg.get("content") or "").strip()
    except (TypeError, KeyError, IndexError):
        LOGGER.warning("OpenRouter: неожиданная структура ответа")
        return ""


def yandex_chat(
    *,
    api_key: str,
    folder_id: str,
    model: str,
    system: str,
    user: str,
    timeout_sec: int,
    max_tokens: int = 8192,
    temperature: float = 0.2,
) -> str:
    """Текст первого alternative из Yandex completion API либо пустая строка."""
    key = (api_key or "").strip()
    folder = (folder_id or "").strip()
    if not key or not folder:
        return ""

    model_uri = f"gpt://{folder}/{(model or '').strip()}"
    body: dict[str, Any] = {
        "modelUri": model_uri,
        "completionOptions": {
            "stream": False,
            "temperature": float(temperature),
            "maxTokens": str(int(max(64, max_tokens))),
        },
        "messages": [
            {"role": "system", "text": system},
            {"role": "user", "text": user},
        ],
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(YANDEX_COMPLETION_V1, data=payload, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Authorization", f"Api-Key {key}")
    req.add_header("x-folder-id", folder)

    ctx = ssl.create_default_context()
    raw = ""
    try:
        with urllib.request.urlopen(req, timeout=max(5, int(timeout_sec)), context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:1200]
        LOGGER.warning("Yandex AI Studio HTTP %s: %s", exc.code, err_body)
        return ""
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        LOGGER.warning("Yandex AI Studio: %s", exc)
        return ""

    if not raw.strip():
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        LOGGER.warning("Yandex AI Studio: невалидный JSON (первые 200 симв.): %s", raw[:200])
        return ""

    try:
        alternatives = data.get("result", {}).get("alternatives") or []
        if not alternatives:
            LOGGER.warning("Yandex AI Studio: пустой alternatives")
            return ""
        message = alternatives[0].get("message") or {}
        return (message.get("text") or "").strip()
    except (TypeError, KeyError, IndexError):
        LOGGER.warning("Yandex AI Studio: неожиданная структура ответа")
        return ""
