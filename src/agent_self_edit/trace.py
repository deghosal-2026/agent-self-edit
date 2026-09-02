"""SQLite-backed trace store, batching, and cleanup."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .types import Trace, validate_trace

StdList = list

logger = logging.getLogger("agent_self_edit.trace")

_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT    NOT NULL,
    task_input      TEXT    NOT NULL,
    steps           TEXT,
    final_output    TEXT    NOT NULL,
    expected_output TEXT    NOT NULL,
    success         INTEGER NOT NULL,
    failure_reason  TEXT,
    timestamp       TEXT    NOT NULL,
    prompt_version  INTEGER,
    processed       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_traces_task_id            ON traces(task_id);
CREATE INDEX IF NOT EXISTS idx_traces_prompt_version     ON traces(prompt_version);
CREATE INDEX IF NOT EXISTS idx_traces_success            ON traces(success);
CREATE INDEX IF NOT EXISTS idx_traces_timestamp          ON traces(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_processed          ON traces(processed);
"""

_MIGRATIONS: dict[int, str] = {}


@dataclass
class TraceStore:
    """SQLite store for execution traces."""

    path: str
    batch_size: int = 50
    _write_lock: threading.Lock = field(default_factory=threading.Lock)
    _db: sqlite3.Connection | None = field(default=None, init=False, repr=False)
    _batch_counter: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        db_path = Path(self.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            self._apply_migrations(conn)
            conn.commit()
        finally:
            conn.close()
        self._batch_counter = self.count(success=None)

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA user_version")
        version = int(cursor.fetchone()[0])
        if version > _SCHEMA_VERSION:
            raise RuntimeError(
                f"Trace DB schema version {version} is newer than "
                f"supported {_SCHEMA_VERSION}; downgrade not supported"
            )
        for target in range(version + 1, _SCHEMA_VERSION + 1):
            statement = _MIGRATIONS.get(target)
            if statement:
                conn.executescript(statement)
            conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()

    def store(self, trace: Trace) -> int:
        """Persist a :class:`Trace`, returning its row id."""
        with self._write_lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO traces (
                        task_id, task_input, steps, final_output, expected_output,
                        success, failure_reason, timestamp, prompt_version, processed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        trace.task_id,
                        trace.task_input,
                        json.dumps(trace.steps) if trace.steps else None,
                        trace.final_output,
                        trace.expected_output,
                        int(trace.success),
                        trace.failure_reason,
                        trace.timestamp,
                        trace.prompt_version,
                    ),
                )
                conn.commit()
                row_id = cursor.lastrowid
                if row_id is None:
                    raise RuntimeError("Failed to retrieve inserted trace id")
                return row_id
            finally:
                conn.close()

    def ingest(self, trace: dict[str, Any]) -> str:
        """Validate, store, and return the trace's task_id.

        Raises :class:`ValueError` for invalid traces without counting them.
        """
        parsed = validate_trace(trace)
        row_id = self.store(parsed)
        self._batch_counter += 1
        logger.info("Ingested trace task_id=%s row=%d", parsed.task_id, row_id)
        return parsed.task_id

    def get(self, task_id: str) -> Trace | None:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "SELECT * FROM traces WHERE task_id = ? ORDER BY id DESC LIMIT 1",
                (task_id,),
            )
            row = cursor.fetchone()
            return self._row_to_trace(row) if row is not None else None
        finally:
            conn.close()

    def list(
        self,
        success: bool | None = None,
        prompt_version: int | None = None,
        limit: int = 100,
    ) -> StdList[Trace]:
        clauses: list[str] = []
        params: list[Any] = []
        if success is not None:
            clauses.append("success = ?")
            params.append(int(success))
        if prompt_version is not None:
            clauses.append("prompt_version = ?")
            params.append(prompt_version)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        conn = self._connect()
        try:
            cursor = conn.execute(
                f"SELECT * FROM traces {where} ORDER BY id LIMIT ?",
                params,
            )
            return [self._row_to_trace(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def count(self, success: bool | None = None) -> int:
        if success is None:
            conn = self._connect()
            try:
                return int(conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0])
            finally:
                conn.close()
        conn = self._connect()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM traces WHERE success = ?",
                    (int(success),),
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def delete_before(self, timestamp: str) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM traces WHERE timestamp < ?", (timestamp,)
            )
            conn.commit()
            return int(cursor.rowcount)
        finally:
            conn.close()

    def _row_to_trace(self, row: sqlite3.Row) -> Trace:
        steps_raw = row["steps"]
        steps: list[dict[str, Any]] = json.loads(steps_raw) if steps_raw else []
        return Trace(
            task_id=row["task_id"],
            task_input=row["task_input"],
            steps=steps,
            final_output=row["final_output"],
            expected_output=row["expected_output"],
            success=bool(row["success"]),
            failure_reason=row["failure_reason"],
            timestamp=row["timestamp"],
            prompt_version=row["prompt_version"],
            row_id=row["id"],
        )

    # ---- batching ----

    def batch_ready(self) -> bool:
        return self.count_pending() >= self.batch_size

    def count_pending(self) -> int:
        conn = self._connect()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM traces WHERE processed = 0"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def get_batch(self, size: int) -> StdList[Trace]:
        """Atomically reserve and return a batch of pending traces.

        Rows are marked ``processed = -1`` (in-flight) to prevent concurrent
        workers from fetching the same rows. Call ``acknowledge_rows`` on
        success or ``release_in_flight`` on failure.
        """
        conn = self._connect()
        try:
            with self._write_lock:
                rows = conn.execute(
                    """
                    SELECT * FROM traces
                    WHERE processed = 0
                    ORDER BY id
                    LIMIT ?
                    """,
                    (size,),
                ).fetchall()
                if not rows:
                    return []
                row_ids = [row["id"] for row in rows]
                placeholders = ",".join("?" for _ in row_ids)
                conn.execute(
                    f"UPDATE traces SET processed = -1 WHERE id IN ({placeholders})",
                    row_ids,
                )
                conn.commit()
                traces = [self._row_to_trace(row) for row in rows]
                return traces
        finally:
            conn.close()

    def acknowledge_rows(self, traces: StdList[Trace]) -> None:
        """Mark rows as successfully processed (by immutable row id)."""
        if not traces:
            return
        row_ids = [t.row_id for t in traces if t.row_id is not None]
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"UPDATE traces SET processed = 1 WHERE id IN ({placeholders})",
                    row_ids,
                )
                conn.commit()
            finally:
                conn.close()

    def release_in_flight(self, traces: StdList[Trace]) -> None:
        """Release in-flight rows back to pending (for retry after failure)."""
        if not traces:
            return
        row_ids = [t.row_id for t in traces if t.row_id is not None]
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"UPDATE traces SET processed = 0 WHERE id IN ({placeholders})",
                    row_ids,
                )
                conn.commit()
            finally:
                conn.close()

    def acknowledge(self, task_ids: StdList[str]) -> None:
        """Legacy: acknowledge by task_id. Prefer ``acknowledge_rows``."""
        if not task_ids:
            return
        placeholders = ",".join("?" for _ in task_ids)
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"UPDATE traces SET processed = 1 WHERE task_id IN ({placeholders})",
                    task_ids,
                )
                conn.commit()
            finally:
                conn.close()

    def acknowledge_batch(self, traces: StdList[Trace]) -> None:
        """Mark rows as processed by their immutable ``id``, not ``task_id``.

        This prevents silent data loss when duplicate ``task_id`` values exist
        (ref #147). Pass the batch of traces returned by ``get_batch``.
        """
        if not traces:
            return
        row_ids = [t.row_id for t in traces if t.row_id is not None]
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute(
                    f"UPDATE traces SET processed = 1 WHERE id IN ({placeholders})",
                    row_ids,
                )
                conn.commit()
            finally:
                conn.close()

    # ---- cleanup ----

    def cleanup(self, retention_days: int = 90) -> int:
        """Delete traces older than ``retention_days``; 0 deletes everything."""
        if retention_days < 0:
            raise ValueError("retention_days must be >= 0")
        cutoff = (
            "9999-12-31T23:59:59Z"
            if retention_days == 0
            else (datetime.now(timezone.utc) - timedelta(days=retention_days))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        deleted = self.delete_before(cutoff)
        logger.info("Cleanup: deleted %d traces older than retention=%d", deleted, retention_days)
        return deleted
