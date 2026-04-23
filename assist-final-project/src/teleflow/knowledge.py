from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fingerprint import content_fingerprint
from .models import AppConfig

_ENTRY_ID_RE = re.compile(r"^[a-f0-9]{32}$")


@dataclass(slots=True)
class SaveKnowledgeResult:
    ok: bool
    path: Path | None
    duplicate_theme: str | None
    duplicate_path: Path | None
    fingerprint: str


@dataclass(slots=True)
class EntryPreview:
    entry_id: str
    created_at: str
    preview: str


@dataclass(slots=True)
class MoveKnowledgeResult:
    old_theme: str
    new_theme: str
    path: Path


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


def normalize_entry_id(raw_value: str) -> str | None:
    value = (raw_value or "").strip().lower()
    if value.startswith("entry_") and value.endswith(".json"):
        value = value[len("entry_") : -len(".json")]
    if not _ENTRY_ID_RE.fullmatch(value):
        return None
    return value


def _entry_name(entry_id: str) -> str:
    return f"entry_{entry_id}.json"


def _iter_all_entries(config: AppConfig) -> list[Path]:
    root = data_root(config) / "knowledge"
    if not root.exists():
        return []
    return [path for path in root.rglob("entry_*.json") if path.is_file()]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _entry_theme(config: AppConfig, path: Path, payload: dict[str, Any] | None = None) -> str:
    if payload:
        value = str(payload.get("theme", "")).strip()
        if value:
            return value
    folder = path.parent.name
    for theme in theme_choices(config):
        if _theme_folder(config, theme) == folder:
            return theme
    return folder


def _entry_fingerprint(config: AppConfig, payload: dict[str, Any]) -> str:
    saved = str(payload.get("fingerprint", "")).strip().lower()
    if saved:
        return saved
    text = str(payload.get("text", "")).strip()
    return content_fingerprint(text, config.dedupe_text_max_chars)


def save_knowledge_entry(
    config: AppConfig, *, text: str, theme: str, source_link: str | None
) -> SaveKnowledgeResult:
    text_clean = (text or "").strip()
    if not text_clean:
        return SaveKnowledgeResult(
            ok=False,
            path=None,
            duplicate_theme=None,
            duplicate_path=None,
            fingerprint="",
        )

    fingerprint = content_fingerprint(text_clean, config.dedupe_text_max_chars)
    for existing_path in _iter_all_entries(config):
        payload = _load_json(existing_path)
        if payload is None:
            continue
        if _entry_fingerprint(config, payload) == fingerprint:
            return SaveKnowledgeResult(
                ok=False,
                path=None,
                duplicate_theme=_entry_theme(config, existing_path, payload),
                duplicate_path=existing_path,
                fingerprint=fingerprint,
            )

    entry_id = uuid.uuid4().hex
    payload = {
        "id": entry_id,
        "text": text_clean,
        "theme": theme,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_link": source_link or "",
        "fingerprint": fingerprint,
    }
    path = theme_knowledge_dir(config, theme) / f"entry_{entry_id}.json"
    _atomic_write_json(path, payload)
    return SaveKnowledgeResult(
        ok=True,
        path=path,
        duplicate_theme=None,
        duplicate_path=None,
        fingerprint=fingerprint,
    )


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
        payload = _load_json(path)
        if payload is None:
            continue
        entries.append(payload)
    entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return entries


def read_all_entries(config: AppConfig) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for theme in theme_choices(config):
        entries.extend(read_theme_entries(config, theme))
    entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return entries


def list_theme_entries_preview(config: AppConfig, theme: str, limit: int) -> list[EntryPreview]:
    directory = theme_knowledge_dir(config, theme)
    if not directory.exists():
        return []

    prepared: list[EntryPreview] = []
    entries = read_theme_entries(config, theme)[: max(1, limit)]
    for payload in entries:
        raw_id = str(payload.get("id", "")).strip().lower()
        entry_id = normalize_entry_id(raw_id) or "unknown"
        text = str(payload.get("text", "")).strip()
        collapsed = " ".join(text.split())
        tail = collapsed[:140] + ("…" if len(collapsed) > 140 else "")
        prepared.append(
            EntryPreview(
                entry_id=entry_id,
                created_at=str(payload.get("created_at", "")).strip(),
                preview=tail or "—",
            )
        )
    return prepared


def find_entry_path(config: AppConfig, entry_id: str) -> Path | None:
    normalized = normalize_entry_id(entry_id)
    if not normalized:
        return None
    expected_name = _entry_name(normalized)
    for path in _iter_all_entries(config):
        if path.name.lower() == expected_name:
            return path
    return None


def delete_entry_by_id(config: AppConfig, entry_id: str) -> Path | None:
    path = find_entry_path(config, entry_id)
    if path is None:
        return None
    path.unlink(missing_ok=False)
    return path


def move_entry_by_id(config: AppConfig, entry_id: str, new_theme: str) -> MoveKnowledgeResult | None:
    source_path = find_entry_path(config, entry_id)
    if source_path is None:
        return None

    payload = _load_json(source_path) or {}
    old_theme = _entry_theme(config, source_path, payload)
    target_dir = theme_knowledge_dir(config, new_theme)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    os.replace(source_path, target_path)

    if payload:
        payload["theme"] = new_theme
        if "fingerprint" not in payload:
            payload["fingerprint"] = content_fingerprint(
                str(payload.get("text", "")).strip(), config.dedupe_text_max_chars
            )
        _atomic_write_json(target_path, payload)

    return MoveKnowledgeResult(old_theme=old_theme, new_theme=new_theme, path=target_path)

