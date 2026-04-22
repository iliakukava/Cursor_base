from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class StateStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _set_value(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_state(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            conn.commit()

    def _get_value(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return str(row[0])

    def _delete_value(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM app_state WHERE key = ?", (key,))
            conn.commit()

    def set_last_run(self, dt: datetime) -> None:
        self._set_value("last_run", dt.astimezone(timezone.utc).isoformat())

    def set_last_knowledge_entry(self, user_id: int, path: str) -> None:
        self._set_value(f"last_knowledge_entry:{int(user_id)}", path)

    def get_last_knowledge_entry(self, user_id: int) -> str | None:
        return self._get_value(f"last_knowledge_entry:{int(user_id)}")

    def clear_last_knowledge_entry(self, user_id: int) -> None:
        self._delete_value(f"last_knowledge_entry:{int(user_id)}")

