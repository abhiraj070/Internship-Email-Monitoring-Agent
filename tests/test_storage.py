"""
Unit tests for StorageEngine.
"""

import tempfile
from pathlib import Path
from datetime import datetime, timezone
import pytest

from agent.models import ProcessedRecord
from agent.storage import StorageEngine


@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_processed.db"
        yield StorageEngine(db_path=db_path)


def test_is_processed_initially_false(temp_storage):
    assert temp_storage.is_processed("msg_123") is False


def test_mark_and_check_processed(temp_storage):
    record = ProcessedRecord(
        message_id="msg_123",
        thread_id="th_456",
        subject="Summer 2027 Internship Offer",
        sender="recruiter@google.com",
        category="APPLICATION_UPDATE",
        priority="HIGH",
        processed_at=datetime.now(timezone.utc),
        notification_sent=True,
    )
    temp_storage.mark_processed(record)

    assert temp_storage.is_processed("msg_123") is True
    assert temp_storage.is_processed("other_id") is False
    assert temp_storage.get_total_processed() == 1


def test_thread_history(temp_storage):
    record1 = ProcessedRecord(
        message_id="msg_1",
        thread_id="th_shared",
        subject="Interview Invitation",
        sender="hr@meta.com",
        category="INTERVIEW",
        priority="HIGH",
        notification_sent=True,
    )
    record2 = ProcessedRecord(
        message_id="msg_2",
        thread_id="th_shared",
        subject="Re: Interview Invitation",
        sender="hr@meta.com",
        category="INTERVIEW",
        priority="HIGH",
        notification_sent=True,
    )
    temp_storage.mark_processed(record1)
    temp_storage.mark_processed(record2)

    history = temp_storage.get_thread_history("th_shared")
    assert len(history) == 2
    assert [r.message_id for r in history] == ["msg_1", "msg_2"]
