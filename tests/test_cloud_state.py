import json
from unittest.mock import MagicMock

import pytest

from agent.cloud_state import CloudState
from agent.service import AgentService
from tests.test_notifier import make_sample_data


def test_cloud_state_persists_only_confirmed_alerts_and_hashes(tmp_path):
    path = tmp_path / 'processed_ids.json'
    email, classification = make_sample_data()
    gmail, classifier, notifier = MagicMock(), MagicMock(), MagicMock()
    gmail.list_unprocessed_message_ids.return_value = [email.message_id]
    gmail.get_email_message.return_value = email
    classifier.classify.return_value = classification
    notifier.send_notification.return_value = False
    service = AgentService(gmail, CloudState(path), classifier, notifier)
    assert service.run_once()['notifications_failed'] == 1
    assert not path.exists()
    notifier.send_notification.return_value = True
    assert service.run_once()['notifications_sent'] == 1
    serialized = path.read_text()
    assert email.message_id not in serialized
    assert email.subject not in serialized
    assert email.sender_email not in serialized
    assert len(json.loads(serialized)[0]) == 64
    restored = AgentService(gmail, CloudState(path), classifier, notifier)
    assert restored.run_once()['skipped_already_processed'] == 1


def test_corrupt_cloud_state_fails_closed(tmp_path):
    path = tmp_path / 'processed_ids.json'
    path.write_text('["bad"]')
    with pytest.raises(ValueError, match='refusing to reset'):
        CloudState(path)
