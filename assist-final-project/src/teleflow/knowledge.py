from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AppConfig


def _normalize_theme(value: str) -> str:
    return " ".join((value or "").strip().split()).lower()


def theme_choices(config: AppConfig) -> list[str]:
    return config.themes


def resolve_theme(config: AppConfig, raw_value: str) -> str | None:
    candidate = (raw_value or "").strip()
    if not candidate:
        return None

    if candidate.isdigit():
        idx = int(candidate) - 1
        if 0 <= idx < len(config.themes):
            return config.themes[idx]

    by_norm = {_normalize_theme(theme): theme for theme in config.themes}
    return by_norm.get(_normalize_theme(candidate))


def _theme_folder(config: AppConfig, theme: str) -> str:
    mapped = config.theme_dirs.get(theme)
    if mapped:
        return mapped
    return theme


def data_root(config: AppConfig) -> Path:
    return Path(config.data_dir)


def theme_knowledge_dir(config: AppConfig, theme: str) -> Path:
    folder = _theme_folder(config, theme)
    return data_root(config) / "knowledge" / folder


def theme_drafts_dir(config: AppConfig, theme: str) -> Path:
    folder = _theme_folder(config, theme)
    return data_root(config) / "drafts" / folder


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def save_knowledge_entry(config: AppConfig, *, text: str, theme: str, source_link: str | None) -> Path:
    entry_id = uuid.uuid4().hex
    payload = {
        "id": entry_id,
        "text": text,
        "theme": theme,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_link": source_link or "",
    }
    path = theme_knowledge_dir(config, theme) / f"entry_{entry_id}.json"
    _atomic_write_json(path, payload)
    return path


def count_saved_entries_by_theme(config: AppConfig) -> list[tuple[str, int]]:
    """Число сохранённых постов (файлов entry_*.json) по каждой теме из THEMES."""
    out: list[tuple[str, int]] = []
    for theme in theme_choices(config):
        directory = theme_knowledge_dir(config, theme)
        if not directory.exists():
            out.append((theme, 0))
            continue
        n = sum(1 for _ in directory.glob("entry_*.json"))
        out.append((theme, n))
    return out


def read_theme_entries(config: AppConfig, theme: str) -> list[dict[str, Any]]:
    directory = theme_knowledge_dir(config, theme)
    if not directory.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in directory.glob("entry_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                entries.append(payload)
        except Exception:
            continue
    entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return entries

