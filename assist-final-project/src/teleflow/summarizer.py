from __future__ import annotations

import json
import logging
import time
from typing import Any

from .models import AppConfig, PostCandidate
from .openrouter import llm_chat

LOGGER = logging.getLogger(__name__)


def _annotate_instructions() -> str:
    return (
        "Ты редактор строгого экспертного дайджеста. Твоя цель — оставить только самые интересные и практически релевантные посты. "
        "Ниже — JSON-массив объектов "
        '{"idx": number, "text": "..."} по порядку постов.\n'
        "Верни СТРОГО JSON-массив и ничего больше (без markdown и комментариев). "
        "Один объект на каждый элемент входа:\n"
        '[{"idx":1,"keep":true,"importance":1-10,"category":"...","summary":"..."}]\n'
        "Критерии keep=true: есть конкретная новая информация, практические выводы, прикладные методы/цифры/факты, "
        "или заметная стратегическая ценность для профессионального роста и принятия решений.\n"
        "Критерии keep=false: вода, мотивационные общие фразы, очевидные банальности, реклама без ценности, повторы, "
        "кликбейт, поверхностные пересказы без новых инсайтов.\n"
        "Оцени importance строго: 9-10 = очень редкая и высокополезная информация; 7-8 = сильный полезный материал; "
        "5-6 = средняя польза; 1-4 = низкая ценность.\n"
        "Поле category — короткая тематическая метка (1-3 слова). "
        "Поле summary — краткая суть поста (1 предложение, максимум 2, без воды). "
        "Никакого текста кроме JSON."
    )


class DigestAnnotator:
    """Разметка постов дайджеста через выбранный LLM-провайдер."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        model_name = config.openrouter_model if config.llm_provider == "openrouter" else config.yandex_model
        LOGGER.info(
            "LLM: provider=%s (model=%s, request_timeout=%ss, annotate_budget=%ss)",
            config.llm_provider,
            model_name,
            config.openrouter_timeout_sec,
            config.openrouter_annotate_budget_sec,
        )

    def _payload_json(self, batch: list[PostCandidate]) -> str:
        n = self.config.openrouter_digest_text_chars
        payload = [
            {"idx": i, "text": item.text[:n]}
            for i, item in enumerate(batch, start=1)
        ]
        return json.dumps(payload, ensure_ascii=False)

    def _batch_end(self, items: list[PostCandidate], lo: int) -> int:
        return min(lo + self.config.openrouter_digest_batch_size, len(items))

    def annotate(self, candidates: list[PostCandidate]) -> list[PostCandidate]:
        if not candidates:
            return []
        items = candidates[: self.config.openrouter_digest_max_items]
        started = time.monotonic()
        offset = 0

        while offset < len(items):
            if time.monotonic() - started > self.config.openrouter_annotate_budget_sec:
                LOGGER.warning(
                    "Достигнут бюджет OPENROUTER_ANNOTATE_BUDGET_SEC=%ss, остальные посты без LLM.",
                    self.config.openrouter_annotate_budget_sec,
                )
                break
            hi = self._batch_end(items, offset)
            batch = items[offset:hi]
            offset = hi
            stdin_json = self._payload_json(batch)

            api_key = (
                self.config.openrouter_api_key
                if self.config.llm_provider == "openrouter"
                else self.config.yandex_api_key
            )
            model = (
                self.config.openrouter_model
                if self.config.llm_provider == "openrouter"
                else self.config.yandex_model
            )
            response = llm_chat(
                provider=self.config.llm_provider,
                api_key=api_key,
                model=model,
                system=_annotate_instructions(),
                user=stdin_json,
                timeout_sec=self.config.openrouter_timeout_sec,
                max_tokens=self.config.openrouter_max_tokens,
                temperature=0.2,
                yandex_folder_id=self.config.yandex_folder_id,
            )

            parsed = self._parse_json(response)
            if not isinstance(parsed, list):
                parsed = []

            stripped = (response or "").strip()
            if not parsed:
                if stripped and stripped != "[]":
                    LOGGER.warning(
                        "LLM вернул не-JSON (первые 240 симв.): %s",
                        stripped.replace("\n", " ")[:240],
                    )
                elif stripped == "[]":
                    LOGGER.warning(
                        "LLM вернул пустой JSON [] — для батча дефолтные summary из текста поста."
                    )

            by_idx = {entry.get("idx"): entry for entry in parsed if isinstance(entry, dict)}
            for i, item in enumerate(batch, start=1):
                entry = by_idx.get(i, {})
                keep = bool(entry.get("keep", True))
                if self.config.relevance_only and not keep:
                    item.ai_keep = False
                    continue
                item.ai_keep = keep
                item.importance = int(entry.get("importance", 5) or 5)
                item.ai_category = str(entry.get("category", "") or "")
                summary = str(entry.get("summary", "") or "").strip()
                item.ai_summary = summary or item.text[:280].replace("\n", " ")

        return [item for item in items if item.ai_keep]

    @staticmethod
    def _parse_json(raw: str) -> Any:
        text = (raw or "").strip()
        if not text:
            return []
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                candidate = text[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return []
            return []
