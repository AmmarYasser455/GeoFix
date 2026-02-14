"""SQLite-backed conversation persistence.

Stores chat conversations and messages for history, search, and export.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("geofix.storage.conversations")

SCHEMA = """\
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'New Conversation',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tokens_used     INTEGER DEFAULT 0,
    processing_time REAL DEFAULT 0.0,
    model           TEXT DEFAULT '',
    timestamp       TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS geospatial_projects (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_format     TEXT DEFAULT '',
    crs             TEXT DEFAULT '',
    feature_count   INTEGER DEFAULT 0,
    bbox_minx       REAL,
    bbox_miny       REAL,
    bbox_maxx       REAL,
    bbox_maxy       REAL,
    quality_score   INTEGER DEFAULT -1,
    error_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_proj_conv ON geospatial_projects(conversation_id);
"""


class ConversationStore:
    """Manages conversation persistence in SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
        return self._conn

    def create_conversation(self, title: str = "New Conversation") -> str:
        """Create a new conversation and return its ID."""
        conv_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now),
        )
        self.conn.commit()
        logger.info("Created conversation: %s", conv_id)
        return conv_id

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tokens_used: int = 0,
        processing_time: float = 0.0,
        model: str = "",
    ) -> str:
        """Add a message to a conversation. Returns the message ID."""
        msg_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO messages
               (id, conversation_id, role, content, tokens_used, processing_time, model, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, conversation_id, role, content, tokens_used, processing_time, model, now),
        )

        # Update conversation timestamp and auto-title from first user message
        self.conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )

        if role == "user":
            row = self.conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND role = 'user'",
                (conversation_id,),
            ).fetchone()
            if row[0] == 1:
                title = content[:60].strip() or "New Conversation"
                self.conn.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (title, conversation_id),
                )

        self.conn.commit()
        return msg_id

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get messages for a conversation, ordered chronologically."""
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_conversations(self, limit: int = 50) -> list[dict]:
        """List conversations ordered by most recent first."""
        rows = self.conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_conversations(self, query: str, limit: int = 20) -> list[dict]:
        """Search conversations by message content."""
        rows = self.conn.execute(
            """SELECT DISTINCT c.* FROM conversations c
               JOIN messages m ON m.conversation_id = c.id
               WHERE m.content LIKE ? OR c.title LIKE ?
               ORDER BY c.updated_at DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def export_conversation(self, conversation_id: str, fmt: str = "markdown") -> str:
        """Export a conversation as markdown or JSON."""
        messages = self.get_messages(conversation_id, limit=10000)
        conv = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()

        if not conv:
            return ""

        conv_dict = dict(conv)

        if fmt == "json":
            return json.dumps(
                {"conversation": conv_dict, "messages": messages},
                indent=2,
                default=str,
            )

        lines = [f"# {conv_dict['title']}\n"]
        lines.append(f"*Created: {conv_dict['created_at']}*\n")
        for msg in messages:
            role = "User" if msg["role"] == "user" else "GeoFix"
            lines.append(f"### {role}\n\n{msg['content']}\n")
        return "\n".join(lines)

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages."""
        self.conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self.conn.commit()

    def get_stats(self, conversation_id: str) -> dict:
        """Get analytics for a conversation."""
        row = self.conn.execute(
            """SELECT
                COUNT(*) as message_count,
                SUM(tokens_used) as total_tokens,
                AVG(processing_time) as avg_processing_time,
                SUM(processing_time) as total_processing_time
               FROM messages WHERE conversation_id = ?""",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else {}

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
