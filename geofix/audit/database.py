"""SQLite audit database — schema and operations.

Stores an immutable log of every fix attempt for accountability
and learning from past corrections.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("geofix.audit.database")

SCHEMA = """\
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    session_id      TEXT    NOT NULL DEFAULT '',
    feature_id      TEXT    NOT NULL,
    error_type      TEXT    NOT NULL,
    error_id        TEXT    NOT NULL,
    fix_type        TEXT    NOT NULL,
    tier            TEXT    NOT NULL,
    confidence      REAL    NOT NULL,
    reasoning       TEXT,
    before_wkt      TEXT,
    after_wkt       TEXT,
    action          TEXT    NOT NULL,
    validation_ok   INTEGER NOT NULL DEFAULT 1,
    new_errors      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_feature ON audit_log(feature_id);
CREATE INDEX IF NOT EXISTS idx_error_type ON audit_log(error_type);
"""


class AuditDatabase:
    """SQLite-backed audit log for GeoFix fix operations.

    Usage::

        db = AuditDatabase(Path("geofix_audit.db"))
        db.insert(entry_dict)
        rows = db.query(feature_id="42")
        db.close()
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(SCHEMA)
            logger.info("Audit database opened: %s", self.db_path)
        return self._conn

    def insert(self, entry: dict) -> int:
        """Insert a single audit entry. Returns the row ID."""
        cols = [
            "timestamp", "session_id", "feature_id", "error_type",
            "error_id", "fix_type", "tier", "confidence", "reasoning",
            "before_wkt", "after_wkt", "action", "validation_ok", "new_errors",
        ]
        values = [entry.get(c) for c in cols]
        placeholders = ", ".join("?" * len(cols))
        col_names = ", ".join(cols)

        cursor = self.conn.execute(
            f"INSERT INTO audit_log ({col_names}) VALUES ({placeholders})",
            values,
        )
        self.conn.commit()
        return cursor.lastrowid

    def query(
        self,
        feature_id: Optional[str] = None,
        session_id: Optional[str] = None,
        error_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit entries with optional filters."""
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []

        if feature_id:
            sql += " AND feature_id = ?"
            params.append(feature_id)
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        if error_type:
            sql += " AND error_type = ?"
            params.append(error_type)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count(self, session_id: Optional[str] = None) -> int:
        """Count total audit entries."""
        if session_id:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        return row[0]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
