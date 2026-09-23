from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from apps.zte_manager.runtime import data_dir


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


class HistoryRepository:
    """
    Repository SQLite da operação.

    SQLite deixa o histórico transacional e local sem introduzir serviço
    externo. Cada método abre sua própria conexão para simplificar lifecycle
    no PyInstaller/Vela.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
    ):
        self.path = Path(
            db_path
            or data_dir() / "operations.sqlite3"
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = RLock()
        self._init_schema()

    def _connect(self):
        connection = sqlite3.connect(
            self.path,
            timeout=10,
        )

        connection.row_factory = sqlite3.Row
        connection.execute(
            "PRAGMA journal_mode=WAL"
        )
        connection.execute(
            "PRAGMA foreign_keys=ON"
        )

        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()

        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self):
        with self._lock, self._connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS attendant_session (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    host TEXT,
                    attendant TEXT,
                    model TEXT,
                    firmware TEXT,
                    serial TEXT
                );

                CREATE TABLE IF NOT EXISTS device_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    captured_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(session_id)
                        REFERENCES attendant_session(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS diagnostic_run (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    created_at TEXT NOT NULL,
                    status TEXT,
                    summary TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(session_id)
                        REFERENCES attendant_session(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS configuration_change (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    created_at TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    target TEXT,
                    before_json TEXT,
                    after_json TEXT,
                    success INTEGER NOT NULL,
                    message TEXT,
                    FOREIGN KEY(session_id)
                        REFERENCES attendant_session(id)
                        ON DELETE SET NULL
                );
                """
            )

    def start_session(
        self,
        *,
        host: str | None,
        attendant: str | None,
        device: dict[str, Any] | None = None,
    ) -> int:
        device = device or {}

        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO attendant_session (
                    started_at,
                    host,
                    attendant,
                    model,
                    firmware,
                    serial
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    host,
                    attendant,
                    device.get("modelo"),
                    device.get("firmware"),
                    device.get("serial"),
                ),
            )

            return int(cursor.lastrowid)

    def end_session(
        self,
        session_id: int | None,
    ):
        if not session_id:
            return

        with self._lock, self._connection() as db:
            db.execute(
                """
                UPDATE attendant_session
                SET ended_at = ?
                WHERE id = ?
                """,
                (
                    _utc_now(),
                    session_id,
                ),
            )

    def save_snapshot(
        self,
        session_id: int | None,
        reason: str,
        payload: Any,
    ) -> int:
        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO device_snapshot (
                    session_id,
                    captured_at,
                    reason,
                    payload_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    _utc_now(),
                    reason,
                    _json(payload),
                ),
            )

            return int(cursor.lastrowid)

    def save_diagnostic(
        self,
        session_id: int | None,
        result: dict[str, Any],
    ) -> int:
        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO diagnostic_run (
                    session_id,
                    created_at,
                    status,
                    summary,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    _utc_now(),
                    result.get("status"),
                    result.get("summary"),
                    _json(result),
                ),
            )

            return int(cursor.lastrowid)

    def save_change(
        self,
        session_id: int | None,
        *,
        operation: str,
        target: str | None,
        before: Any,
        after: Any,
        success: bool,
        message: str | None = None,
    ) -> int:
        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO configuration_change (
                    session_id,
                    created_at,
                    operation,
                    target,
                    before_json,
                    after_json,
                    success,
                    message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    _utc_now(),
                    operation,
                    target,
                    _json(before) if before is not None else None,
                    _json(after) if after is not None else None,
                    1 if success else 0,
                    message,
                ),
            )

            return int(cursor.lastrowid)

    def recent(
        self,
        limit: int = 50,
    ) -> dict[str, list[dict[str, Any]]]:
        limit = max(
            1,
            min(int(limit), 200),
        )

        with self._lock, self._connection() as db:
            sessions = self._rows(
                db.execute(
                    """
                    SELECT *
                    FROM attendant_session
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            )

            diagnostics = self._rows(
                db.execute(
                    """
                    SELECT id, session_id, created_at, status, summary, payload_json
                    FROM diagnostic_run
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ),
                json_fields=("payload_json",),
            )

            changes = self._rows(
                db.execute(
                    """
                    SELECT *
                    FROM configuration_change
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ),
                json_fields=("before_json", "after_json"),
            )

            snapshots = self._rows(
                db.execute(
                    """
                    SELECT *
                    FROM device_snapshot
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ),
                json_fields=("payload_json",),
            )

        return {
            "sessions": sessions,
            "diagnostics": diagnostics,
            "changes": changes,
            "snapshots": snapshots,
        }

    @staticmethod
    def _rows(
        cursor,
        json_fields: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        result = []

        for row in cursor.fetchall():
            item = dict(row)

            for field in json_fields:
                if item.get(field):
                    try:
                        item[field] = json.loads(
                            item[field]
                        )
                    except json.JSONDecodeError:
                        pass

            result.append(item)

        return result


history_repository = HistoryRepository()
