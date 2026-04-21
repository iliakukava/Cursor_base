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

    def set_last_run(self, dt: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_state(key, value)
                VALUES ('last_run', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (dt.astimezone(timezone.utc).isoformat(),),
            )
            conn.commit()

