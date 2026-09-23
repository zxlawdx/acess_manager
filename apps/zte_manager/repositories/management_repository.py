from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from apps.zte_manager.runtime import data_dir


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class ManagementRepository:
    """
    Persistência da camada de gerenciamento de CPE.

    Mantemos este banco separado do audit trail de atendimento para que
    inventário/fleet/agents/monitoramento possam evoluir sem misturar o
    histórico operacional já existente.
    """

    def __init__(
        self,
        path: Path | None = None,
    ):
        self.path = (
            path
            or data_dir()
            / "management.sqlite3"
        )
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(
            self.path
        )
        db.row_factory = (
            sqlite3.Row
        )

        try:
            yield db
            db.commit()
        finally:
            db.close()

    def _initialize(self):
        statements = (
            """
            CREATE TABLE IF NOT EXISTS cpe_device (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                customer_name TEXT,
                host TEXT,
                model TEXT,
                serial TEXT,
                mac TEXT,
                firmware TEXT,
                status TEXT NOT NULL DEFAULT 'unknown',
                rx_power REAL,
                uptime INTEGER,
                olt TEXT,
                cto TEXT,
                pop TEXT,
                agent_id INTEGER,
                tags_json TEXT NOT NULL DEFAULT '[]',
                capabilities_json TEXT NOT NULL DEFAULT '{}',
                current_config_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                last_seen TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_cpe_device_serial
            ON cpe_device(serial)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_cpe_device_scope
            ON cpe_device(pop, olt, cto)
            """,
            """
            CREATE TABLE IF NOT EXISTS management_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                config_json TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gateway_agent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                host TEXT NOT NULL,
                ssh_port INTEGER NOT NULL DEFAULT 22,
                ssh_user TEXT NOT NULL,
                ssh_key_path TEXT,
                vpn_driver TEXT NOT NULL DEFAULT 'none',
                vpn_config_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                last_seen TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS remote_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                agent_id INTEGER,
                attendant TEXT,
                driver TEXT,
                status TEXT NOT NULL,
                target_host TEXT,
                opened_at TEXT NOT NULL,
                expires_at TEXT,
                closed_at TEXT,
                details_json TEXT NOT NULL DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS batch_job (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                device_ids_json TEXT NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                succeeded INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                results_json TEXT NOT NULL DEFAULT '[]'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS monitor_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                status TEXT NOT NULL,
                interval_seconds INTEGER NOT NULL,
                duration_seconds INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS monitor_sample (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                captured_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_monitor_sample_run
            ON monitor_sample(run_id, id)
            """,
            """
            CREATE TABLE IF NOT EXISTS incident (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                scope_json TEXT NOT NULL,
                device_ids_json TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS firmware_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                version TEXT NOT NULL,
                file_path TEXT NOT NULL,
                sha256 TEXT,
                approved INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(model, version, file_path)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS backup_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                path TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS provisioning_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                status TEXT NOT NULL,
                step TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS management_setting (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        )

        with self._lock, self._connection() as db:
            for statement in statements:
                db.execute(
                    statement
                )

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            default=str,
        )

    @staticmethod
    def _loads(
        value: str | None,
        fallback,
    ):
        if value in (
            None,
            "",
        ):
            return fallback

        try:
            return json.loads(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return fallback

    @classmethod
    def _row(
        cls,
        row: sqlite3.Row | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None

        result = dict(
            row
        )

        for key in list(
            result
        ):
            if key.endswith(
                "_json"
            ):
                fallback = (
                    []
                    if key in {
                        "tags_json",
                        "device_ids_json",
                        "results_json",
                    }
                    else {}
                )

                result[
                    key[:-5]
                ] = cls._loads(
                    result.pop(key),
                    fallback,
                )

        return result

    @classmethod
    def _rows(
        cls,
        rows,
    ) -> list[dict[str, Any]]:
        return [
            cls._row(row)
            for row in rows
        ]

    # =====================================================
    # INVENTÁRIO
    # =====================================================

    def upsert_device(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        key = str(
            data.get("key")
            or data.get("serial")
            or data.get("mac")
            or data.get("host")
            or ""
        ).strip()

        if not key:
            raise ValueError(
                "O equipamento precisa de serial, MAC, host ou chave de inventário."
            )

        now = _now()

        with self._lock, self._connection() as db:
            existing = db.execute(
                "SELECT * FROM cpe_device WHERE key = ?",
                (key,),
            ).fetchone()

            created_at = (
                existing["created_at"]
                if existing
                else now
            )

            def previous(
                key,
                fallback=None,
            ):
                if (
                    key in data
                    and data.get(key) is not None
                ):
                    return data.get(
                        key
                    )

                if existing is not None:
                    return existing[
                        key
                    ]

                return fallback

            def previous_json(
                key,
                column,
                fallback,
            ):
                if key in data:
                    return self._dump(
                        data.get(key)
                        if data.get(key) is not None
                        else fallback
                    )

                if existing is not None:
                    return existing[
                        column
                    ]

                return self._dump(
                    fallback
                )

            values = {
                "customer_name": previous(
                    "customer_name"
                ),
                "host": previous(
                    "host"
                ),
                "model": previous(
                    "model"
                ),
                "serial": previous(
                    "serial"
                ),
                "mac": previous(
                    "mac"
                ),
                "firmware": previous(
                    "firmware"
                ),
                "status": previous(
                    "status",
                    "unknown"
                ),
                "rx_power": previous(
                    "rx_power"
                ),
                "uptime": previous(
                    "uptime"
                ),
                "olt": previous(
                    "olt"
                ),
                "cto": previous(
                    "cto"
                ),
                "pop": previous(
                    "pop"
                ),
                "agent_id": previous(
                    "agent_id"
                ),
                "tags_json": previous_json(
                    "tags",
                    "tags_json",
                    [],
                ),
                "capabilities_json": previous_json(
                    "capabilities",
                    "capabilities_json",
                    {},
                ),
                "current_config_json": previous_json(
                    "current_config",
                    "current_config_json",
                    {},
                ),
                "metadata_json": previous_json(
                    "metadata",
                    "metadata_json",
                    {},
                ),
                "last_seen": previous(
                    "last_seen",
                    now
                ),
                "created_at": created_at,
                "updated_at": now,
            }

            db.execute(
                """
                INSERT INTO cpe_device (
                    key, customer_name, host, model, serial, mac, firmware,
                    status, rx_power, uptime, olt, cto, pop, agent_id,
                    tags_json, capabilities_json, current_config_json,
                    metadata_json, last_seen, created_at, updated_at
                ) VALUES (
                    :key, :customer_name, :host, :model, :serial, :mac, :firmware,
                    :status, :rx_power, :uptime, :olt, :cto, :pop, :agent_id,
                    :tags_json, :capabilities_json, :current_config_json,
                    :metadata_json, :last_seen, :created_at, :updated_at
                )
                ON CONFLICT(key) DO UPDATE SET
                    customer_name = excluded.customer_name,
                    host = excluded.host,
                    model = excluded.model,
                    serial = excluded.serial,
                    mac = excluded.mac,
                    firmware = excluded.firmware,
                    status = excluded.status,
                    rx_power = excluded.rx_power,
                    uptime = excluded.uptime,
                    olt = excluded.olt,
                    cto = excluded.cto,
                    pop = excluded.pop,
                    agent_id = excluded.agent_id,
                    tags_json = excluded.tags_json,
                    capabilities_json = excluded.capabilities_json,
                    current_config_json = excluded.current_config_json,
                    metadata_json = excluded.metadata_json,
                    last_seen = excluded.last_seen,
                    updated_at = excluded.updated_at
                """,
                {
                    "key": key,
                    **values,
                },
            )

            row = db.execute(
                "SELECT * FROM cpe_device WHERE key = ?",
                (key,),
            ).fetchone()

        return self._row(
            row
        )

    def list_devices(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []

        if query:
            clauses.append(
                """
                (
                    customer_name LIKE ?
                    OR host LIKE ?
                    OR model LIKE ?
                    OR serial LIKE ?
                    OR mac LIKE ?
                    OR olt LIKE ?
                    OR cto LIKE ?
                    OR pop LIKE ?
                )
                """
            )
            pattern = f"%{query}%"
            params.extend(
                [pattern] * 8
            )

        if status:
            clauses.append(
                "status = ?"
            )
            params.append(
                status
            )

        sql = (
            "SELECT * FROM cpe_device"
            + (
                " WHERE "
                + " AND ".join(
                    clauses
                )
                if clauses
                else ""
            )
            + " ORDER BY last_seen DESC, id DESC LIMIT ?"
        )

        params.append(
            max(
                1,
                min(
                    int(limit),
                    5000,
                ),
            )
        )

        with self._lock, self._connection() as db:
            rows = db.execute(
                sql,
                params,
            ).fetchall()

        return self._rows(
            rows
        )

    def get_device(
        self,
        device_id: int,
    ) -> dict[str, Any] | None:
        with self._lock, self._connection() as db:
            row = db.execute(
                "SELECT * FROM cpe_device WHERE id = ?",
                (device_id,),
            ).fetchone()

        return self._row(
            row
        )

    def update_device_metadata(
        self,
        device_id: int,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {
            "customer_name",
            "olt",
            "cto",
            "pop",
            "agent_id",
            "status",
        }

        fields = []
        params = []

        for key, value in values.items():
            if key not in allowed:
                continue

            fields.append(
                f"{key} = ?"
            )
            params.append(
                value
            )

        if "tags" in values:
            fields.append(
                "tags_json = ?"
            )
            params.append(
                self._dump(
                    values.get("tags") or []
                )
            )

        if "metadata" in values:
            fields.append(
                "metadata_json = ?"
            )
            params.append(
                self._dump(
                    values.get("metadata") or {}
                )
            )

        if not fields:
            device = self.get_device(
                device_id
            )

            if device is None:
                raise ValueError(
                    "Equipamento não encontrado."
                )

            return device

        fields.append(
            "updated_at = ?"
        )
        params.append(
            _now()
        )
        params.append(
            device_id
        )

        with self._lock, self._connection() as db:
            db.execute(
                (
                    "UPDATE cpe_device SET "
                    + ", ".join(fields)
                    + " WHERE id = ?"
                ),
                params,
            )

        device = self.get_device(
            device_id
        )

        if device is None:
            raise ValueError(
                "Equipamento não encontrado."
            )

        return device

    # =====================================================
    # PERFIS / DRIFT
    # =====================================================

    def save_profile(
        self,
        name: str,
        config: dict[str, Any],
        *,
        description: str | None = None,
        is_default: bool = False,
    ) -> dict[str, Any]:
        now = _now()

        with self._lock, self._connection() as db:
            if is_default:
                db.execute(
                    "UPDATE management_profile SET is_default = 0"
                )

            db.execute(
                """
                INSERT INTO management_profile (
                    name, description, config_json, is_default,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    config_json = excluded.config_json,
                    is_default = excluded.is_default,
                    updated_at = excluded.updated_at
                """,
                (
                    name,
                    description,
                    self._dump(config),
                    1 if is_default else 0,
                    now,
                    now,
                ),
            )

            row = db.execute(
                "SELECT * FROM management_profile WHERE name = ?",
                (name,),
            ).fetchone()

        return self._row(
            row
        )

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM management_profile
                ORDER BY is_default DESC, name ASC
                """
            ).fetchall()

        return self._rows(
            rows
        )

    def get_profile(
        self,
        profile_id: int | None = None,
        *,
        name: str | None = None,
        default: bool = False,
    ) -> dict[str, Any] | None:
        with self._lock, self._connection() as db:
            if profile_id is not None:
                row = db.execute(
                    "SELECT * FROM management_profile WHERE id = ?",
                    (profile_id,),
                ).fetchone()
            elif name is not None:
                row = db.execute(
                    "SELECT * FROM management_profile WHERE name = ?",
                    (name,),
                ).fetchone()
            elif default:
                row = db.execute(
                    """
                    SELECT *
                    FROM management_profile
                    WHERE is_default = 1
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
            else:
                row = None

        return self._row(
            row
        )

    # =====================================================
    # AGENTS / VPN
    # =====================================================

    def save_agent(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(
            data.get("name")
            or ""
        ).strip()

        if not name:
            raise ValueError(
                "Informe um nome para o gateway/agent."
            )

        now = _now()

        with self._lock, self._connection() as db:
            db.execute(
                """
                INSERT INTO gateway_agent (
                    name, host, ssh_port, ssh_user, ssh_key_path,
                    vpn_driver, vpn_config_json, enabled,
                    last_seen, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    host = excluded.host,
                    ssh_port = excluded.ssh_port,
                    ssh_user = excluded.ssh_user,
                    ssh_key_path = excluded.ssh_key_path,
                    vpn_driver = excluded.vpn_driver,
                    vpn_config_json = excluded.vpn_config_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    name,
                    data.get("host") or "",
                    int(data.get("ssh_port") or 22),
                    data.get("ssh_user") or "",
                    data.get("ssh_key_path"),
                    data.get("vpn_driver") or "none",
                    self._dump(
                        data.get("vpn_config") or {}
                    ),
                    1 if data.get("enabled", True) else 0,
                    data.get("last_seen"),
                    now,
                    now,
                ),
            )

            row = db.execute(
                "SELECT * FROM gateway_agent WHERE name = ?",
                (name,),
            ).fetchone()

        return self._row(
            row
        )

    def list_agents(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            rows = db.execute(
                "SELECT * FROM gateway_agent ORDER BY name ASC"
            ).fetchall()

        return self._rows(
            rows
        )

    def get_agent(
        self,
        agent_id: int,
    ) -> dict[str, Any] | None:
        with self._lock, self._connection() as db:
            row = db.execute(
                "SELECT * FROM gateway_agent WHERE id = ?",
                (agent_id,),
            ).fetchone()

        return self._row(
            row
        )

    def touch_agent(
        self,
        agent_id: int,
    ):
        with self._lock, self._connection() as db:
            db.execute(
                """
                UPDATE gateway_agent
                SET last_seen = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    _now(),
                    _now(),
                    agent_id,
                ),
            )

    def start_remote_session(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now()

        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO remote_session (
                    device_id, agent_id, attendant, driver, status,
                    target_host, opened_at, expires_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("device_id"),
                    data.get("agent_id"),
                    data.get("attendant"),
                    data.get("driver"),
                    data.get("status") or "opening",
                    data.get("target_host"),
                    now,
                    data.get("expires_at"),
                    self._dump(
                        data.get("details") or {}
                    ),
                ),
            )
            session_id = cursor.lastrowid
            row = db.execute(
                "SELECT * FROM remote_session WHERE id = ?",
                (session_id,),
            ).fetchone()

        return self._row(
            row
        )

    def update_remote_session(
        self,
        session_id: int,
        *,
        status: str,
        details: dict[str, Any] | None = None,
        closed: bool = False,
    ) -> dict[str, Any] | None:
        with self._lock, self._connection() as db:
            db.execute(
                """
                UPDATE remote_session
                SET status = ?,
                    details_json = COALESCE(?, details_json),
                    closed_at = CASE WHEN ? = 1 THEN ? ELSE closed_at END
                WHERE id = ?
                """,
                (
                    status,
                    (
                        self._dump(details)
                        if details is not None
                        else None
                    ),
                    1 if closed else 0,
                    _now(),
                    session_id,
                ),
            )
            row = db.execute(
                "SELECT * FROM remote_session WHERE id = ?",
                (session_id,),
            ).fetchone()

        return self._row(
            row
        )

    def list_remote_sessions(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM remote_session
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 1000)),),
            ).fetchall()

        return self._rows(
            rows
        )

    # =====================================================
    # BATCH JOBS
    # =====================================================

    def create_batch_job(
        self,
        operation: str,
        device_ids: list[int],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now()

        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO batch_job (
                    operation, status, payload_json, device_ids_json,
                    total, created_at
                ) VALUES (?, 'queued', ?, ?, ?, ?)
                """,
                (
                    operation,
                    self._dump(payload),
                    self._dump(device_ids),
                    len(device_ids),
                    now,
                ),
            )
            job_id = cursor.lastrowid

        return self.get_batch_job(
            job_id
        )

    def update_batch_job(
        self,
        job_id: int,
        *,
        status: str,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        succeeded = sum(
            1
            for item in results
            if item.get("success")
        )
        failed = len(
            results
        ) - succeeded

        with self._lock, self._connection() as db:
            db.execute(
                """
                UPDATE batch_job
                SET status = ?,
                    succeeded = ?,
                    failed = ?,
                    finished_at = CASE
                        WHEN ? IN ('completed', 'failed', 'cancelled')
                        THEN ?
                        ELSE finished_at
                    END,
                    results_json = ?
                WHERE id = ?
                """,
                (
                    status,
                    succeeded,
                    failed,
                    status,
                    _now(),
                    self._dump(results),
                    job_id,
                ),
            )

        result = self.get_batch_job(
            job_id
        )

        if result is None:
            raise ValueError(
                "Job em lote não encontrado."
            )

        return result

    def get_batch_job(
        self,
        job_id: int,
    ) -> dict[str, Any] | None:
        with self._lock, self._connection() as db:
            row = db.execute(
                "SELECT * FROM batch_job WHERE id = ?",
                (job_id,),
            ).fetchone()

        return self._row(
            row
        )

    def list_batch_jobs(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM batch_job
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 1000)),),
            ).fetchall()

        return self._rows(
            rows
        )

    # =====================================================
    # MONITORAMENTO
    # =====================================================

    def start_monitor(
        self,
        device_id: int | None,
        *,
        interval_seconds: int,
        duration_seconds: int,
    ) -> dict[str, Any]:
        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO monitor_run (
                    device_id, status, interval_seconds,
                    duration_seconds, started_at
                ) VALUES (?, 'running', ?, ?, ?)
                """,
                (
                    device_id,
                    interval_seconds,
                    duration_seconds,
                    _now(),
                ),
            )
            run_id = cursor.lastrowid

        return self.get_monitor(
            run_id
        )

    def add_monitor_sample(
        self,
        run_id: int,
        payload: dict[str, Any],
    ):
        with self._lock, self._connection() as db:
            db.execute(
                """
                INSERT INTO monitor_sample (
                    run_id, captured_at, payload_json
                ) VALUES (?, ?, ?)
                """,
                (
                    run_id,
                    _now(),
                    self._dump(payload),
                ),
            )

    def finish_monitor(
        self,
        run_id: int,
        status: str = "completed",
    ):
        with self._lock, self._connection() as db:
            db.execute(
                """
                UPDATE monitor_run
                SET status = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    _now(),
                    run_id,
                ),
            )

    def get_monitor(
        self,
        run_id: int,
    ) -> dict[str, Any] | None:
        with self._lock, self._connection() as db:
            row = db.execute(
                "SELECT * FROM monitor_run WHERE id = ?",
                (run_id,),
            ).fetchone()

            samples = db.execute(
                """
                SELECT *
                FROM monitor_sample
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()

        result = self._row(
            row
        )

        if result is not None:
            result["samples"] = self._rows(
                samples
            )

        return result

    def running_monitors(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            rows = db.execute(
                """
                SELECT *
                FROM monitor_run
                WHERE status = 'running'
                ORDER BY id DESC
                """
            ).fetchall()

        return self._rows(
            rows
        )

    # =====================================================
    # INCIDENTES
    # =====================================================

    def upsert_incident(
        self,
        *,
        incident_key: str,
        severity: str,
        title: str,
        scope: dict[str, Any],
        device_ids: list[int],
        status: str = "open",
    ) -> dict[str, Any]:
        now = _now()

        with self._lock, self._connection() as db:
            db.execute(
                """
                INSERT INTO incident (
                    incident_key, status, severity, title,
                    scope_json, device_ids_json,
                    first_seen, last_seen, occurrence_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(incident_key) DO UPDATE SET
                    status = excluded.status,
                    severity = excluded.severity,
                    title = excluded.title,
                    scope_json = excluded.scope_json,
                    device_ids_json = excluded.device_ids_json,
                    last_seen = excluded.last_seen,
                    occurrence_count = incident.occurrence_count + 1
                """,
                (
                    incident_key,
                    status,
                    severity,
                    title,
                    self._dump(scope),
                    self._dump(device_ids),
                    now,
                    now,
                ),
            )
            row = db.execute(
                "SELECT * FROM incident WHERE incident_key = ?",
                (incident_key,),
            ).fetchone()

        return self._row(
            row
        )

    def list_incidents(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            if status:
                rows = db.execute(
                    """
                    SELECT *
                    FROM incident
                    WHERE status = ?
                    ORDER BY last_seen DESC
                    LIMIT ?
                    """,
                    (
                        status,
                        max(1, min(int(limit), 1000)),
                    ),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT *
                    FROM incident
                    ORDER BY last_seen DESC
                    LIMIT ?
                    """,
                    (max(1, min(int(limit), 1000)),),
                ).fetchall()

        return self._rows(
            rows
        )

    # =====================================================
    # FIRMWARE / BACKUPS / PROVISIONAMENTO
    # =====================================================

    def register_firmware(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now()

        with self._lock, self._connection() as db:
            db.execute(
                """
                INSERT INTO firmware_catalog (
                    model, version, file_path, sha256,
                    approved, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model, version, file_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    approved = excluded.approved,
                    notes = excluded.notes
                """,
                (
                    data.get("model") or "",
                    data.get("version") or "",
                    data.get("file_path") or "",
                    data.get("sha256"),
                    1 if data.get("approved") else 0,
                    data.get("notes"),
                    now,
                ),
            )
            row = db.execute(
                """
                SELECT *
                FROM firmware_catalog
                WHERE model = ? AND version = ? AND file_path = ?
                """,
                (
                    data.get("model") or "",
                    data.get("version") or "",
                    data.get("file_path") or "",
                ),
            ).fetchone()

        return self._row(
            row
        )

    def list_firmware(
        self,
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            if model:
                rows = db.execute(
                    """
                    SELECT *
                    FROM firmware_catalog
                    WHERE model = ?
                    ORDER BY created_at DESC
                    """,
                    (model,),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT *
                    FROM firmware_catalog
                    ORDER BY created_at DESC
                    """
                ).fetchall()

        return self._rows(
            rows
        )

    def register_backup(
        self,
        *,
        device_id: int | None,
        path: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO backup_catalog (
                    device_id, path, reason, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    path,
                    reason,
                    _now(),
                    self._dump(
                        metadata or {}
                    ),
                ),
            )
            backup_id = cursor.lastrowid
            row = db.execute(
                "SELECT * FROM backup_catalog WHERE id = ?",
                (backup_id,),
            ).fetchone()

        return self._row(
            row
        )

    def list_backups(
        self,
        device_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            if device_id is None:
                rows = db.execute(
                    """
                    SELECT *
                    FROM backup_catalog
                    ORDER BY id DESC
                    LIMIT 500
                    """
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT *
                    FROM backup_catalog
                    WHERE device_id = ?
                    ORDER BY id DESC
                    LIMIT 500
                    """,
                    (device_id,),
                ).fetchall()

        return self._rows(
            rows
        )

    def add_provisioning_event(
        self,
        *,
        device_id: int | None,
        status: str,
        step: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock, self._connection() as db:
            cursor = db.execute(
                """
                INSERT INTO provisioning_event (
                    device_id, status, step, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    status,
                    step,
                    _now(),
                    self._dump(
                        payload or {}
                    ),
                ),
            )
            event_id = cursor.lastrowid
            row = db.execute(
                "SELECT * FROM provisioning_event WHERE id = ?",
                (event_id,),
            ).fetchone()

        return self._row(
            row
        )

    def list_provisioning_events(
        self,
        device_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connection() as db:
            if device_id is None:
                rows = db.execute(
                    """
                    SELECT *
                    FROM provisioning_event
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, min(int(limit), 2000)),),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT *
                    FROM provisioning_event
                    WHERE device_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        device_id,
                        max(1, min(int(limit), 2000)),
                    ),
                ).fetchall()

        return self._rows(
            rows
        )

    # =====================================================
    # SETTINGS
    # =====================================================

    def set_setting(
        self,
        key: str,
        value: Any,
    ):
        with self._lock, self._connection() as db:
            db.execute(
                """
                INSERT INTO management_setting (
                    key, value_json, updated_at
                ) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    self._dump(value),
                    _now(),
                ),
            )

    def get_setting(
        self,
        key: str,
        default=None,
    ):
        with self._lock, self._connection() as db:
            row = db.execute(
                """
                SELECT value_json
                FROM management_setting
                WHERE key = ?
                """,
                (key,),
            ).fetchone()

        if row is None:
            return default

        return self._loads(
            row["value_json"],
            default,
        )


management_repository = ManagementRepository()
