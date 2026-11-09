"""
SQLite-backed persistent storage for tracking processed emails and preventing duplicates.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from agent.models import ProcessedRecord
from agent.config import settings


class StorageEngine:
    """Manages tracking of processed Gmail messages and threads."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the processed_emails table schema."""
        with closing(self._get_connection()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processed_emails (
                        message_id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        subject TEXT,
                        sender TEXT,
                        category TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        processed_at TEXT NOT NULL,
                        notification_sent INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_thread_id ON processed_emails (thread_id)
                    """
                )

    def is_processed(self, message_id: str) -> bool:
        """Check if a specific message ID has already been processed."""
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_emails WHERE message_id = ?",
                (message_id,),
            )
            return cursor.fetchone() is not None

    def mark_processed(self, record: ProcessedRecord) -> None:
        """Record a processed message in the database."""
        with closing(self._get_connection()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO processed_emails (
                        message_id, thread_id, subject, sender,
                        category, priority, processed_at, notification_sent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.message_id,
                        record.thread_id,
                        record.subject,
                        record.sender,
                        record.category,
                        record.priority,
                        record.processed_at.isoformat(),
                        1 if record.notification_sent else 0,
                    ),
                )

    def get_thread_history(self, thread_id: str) -> List[ProcessedRecord]:
        """Retrieve previous messages recorded for a thread to evaluate thread updates."""
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT message_id, thread_id, subject, sender,
                       category, priority, processed_at, notification_sent
                FROM processed_emails
                WHERE thread_id = ?
                ORDER BY processed_at ASC
                """,
                (thread_id,),
            )
            rows = cursor.fetchall()
            return [
                ProcessedRecord(
                    message_id=row["message_id"],
                    thread_id=row["thread_id"],
                    subject=row["subject"],
                    sender=row["sender"],
                    category=row["category"],
                    priority=row["priority"],
                    processed_at=datetime.fromisoformat(row["processed_at"]),
                    notification_sent=bool(row["notification_sent"]),
                )
                for row in rows
            ]

    def get_total_processed(self) -> int:
        """Return total count of processed emails."""
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_emails")
            return cursor.fetchone()[0]

    def clear_all(self) -> None:
        """Clear all records (used for test resets)."""
        with closing(self._get_connection()) as conn:
            with conn:
                conn.execute("DELETE FROM processed_emails")
