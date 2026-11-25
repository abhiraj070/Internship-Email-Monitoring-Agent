"""Minimal persistent deduplication state for public GitHub repositories."""

import hashlib
import json
from pathlib import Path

from agent.models import ProcessedRecord


class CloudState:
    """Store only SHA-256 message IDs, without subjects, senders, or email text."""

    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text()) if path.exists() else []
        if not isinstance(data, list) or any(
            not isinstance(item, str) or len(item) != 64
            or any(c not in "0123456789abcdef" for c in item)
            for item in data
        ):
            raise ValueError("Invalid cloud state; refusing to reset duplicate tracking")
        self.processed = set(data)

    def is_processed(self, message_id: str) -> bool:
        return self._key(message_id) in self.processed

    @staticmethod
    def _key(message_id: str) -> str:
        return hashlib.sha256(message_id.encode()).hexdigest()

    def mark_processed(self, record: ProcessedRecord) -> None:
        if not record.notification_sent and record.category != "NOT_RELEVANT":
            return
        self.processed.add(self._key(record.message_id))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(sorted(self.processed)) + "\n")
        temporary.replace(self.path)
