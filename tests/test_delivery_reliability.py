"""Regression coverage for lost alerts, Discord failures, and Gmail pagination."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from agent.gmail_client import GmailClient
from agent.models import ProcessedRecord
from agent.notifier import DiscordNotifier
from agent.service import AgentService
from agent.storage import StorageEngine
from tests.test_notifier import make_sample_data


@pytest.mark.parametrize("dry_run, delivered", [(True, True), (False, False)])
def test_undelivered_email_remains_eligible(tmp_path, dry_run, delivered):
    email, classification = make_sample_data()
    gmail = MagicMock()
    gmail.list_unprocessed_message_ids.return_value = [email.message_id]
    gmail.get_email_message.return_value = email
    classifier = MagicMock()
    classifier.classify.return_value = classification
    notifier = MagicMock()
    notifier.send_notification.return_value = delivered
    storage = StorageEngine(tmp_path / "delivery.db")
    service = AgentService(gmail, storage, classifier, notifier)
    stats = service.run_once(dry_run=dry_run)
    assert stats["notifications_sent"] == 0
    assert storage.get_total_processed() == 0
    assert not storage.is_processed(email.message_id)
    notifier.send_notification.return_value = True
    assert service.run_once()["notifications_sent"] == 1
    assert storage.is_processed(email.message_id)
    assert service.run_once()["skipped_already_processed"] == 1


def test_old_failed_records_can_be_retried(tmp_path):
    storage = StorageEngine(tmp_path / "old.db")
    storage.mark_processed(ProcessedRecord(
        message_id="failed", thread_id="thread", subject="Interview",
        sender="HR", category="INTERVIEW", priority="HIGH", notification_sent=False,
    ))
    assert not storage.is_processed("failed")


def test_gmail_lists_beyond_first_page():
    client = GmailClient()
    client.service = MagicMock()
    list_call = client.service.users().messages().list
    list_call.return_value.execute.side_effect = [
        {"messages": [{"id": "already_seen"}], "nextPageToken": "older"},
        {"messages": [{"id": "new"}]},
    ]
    assert client.list_unprocessed_message_ids(max_results=1) == ["already_seen", "new"]
    assert list_call.call_args.kwargs["pageToken"] == "older"


def test_missing_webhook_is_a_failure(monkeypatch):
    monkeypatch.setattr("agent.notifier.settings.DISCORD_WEBHOOK_URL", None)
    assert not DiscordNotifier().send_notification(*make_sample_data())


@patch("agent.notifier.time.sleep")
@patch("agent.notifier.requests.post")
@pytest.mark.parametrize("first_status", [429, 502])
def test_discord_retries_transient_failures(post, sleep, first_status):
    first, success = MagicMock(), MagicMock()
    first.status_code = first_status
    first.json.return_value = {"retry_after": 0.01}
    success.status_code = 200
    post.side_effect = [first, success]
    assert DiscordNotifier("https://discord.com/api/webhooks/test").send_notification(*make_sample_data())
    assert post.call_count == 2


@patch("agent.notifier.requests.post")
def test_long_emails_fit_discord_limits_and_cannot_ping(post):
    post.return_value.status_code = 200
    email, result = make_sample_data()
    email.subject = "@everyone " * 1000
    result.summary = "x" * 10000
    result.company_name = "x" * 1000
    result.action_required = "x" * 10000
    result.deadline = "x" * 10000
    assert DiscordNotifier("https://discord.com/api/webhooks/test").send_notification(email, result)
    payload = post.call_args.kwargs["json"]
    embed = payload["embeds"][0]
    assert len(payload["content"]) <= 2000
    assert len(embed["title"]) <= 256
    assert len(embed["description"]) <= 4096
    assert all(len(f["value"]) <= 1024 for f in embed["fields"])
    assert sum(len(f["name"]) + len(f["value"]) for f in embed["fields"]) + len(embed["title"]) + len(embed["description"]) + len(embed["footer"]["text"]) <= 6000
    assert payload["allowed_mentions"] == {"parse": []}
    assert post.call_args.kwargs["params"] == {"wait": "true"}


@patch("agent.notifier.time.sleep")
@patch("agent.notifier.requests.post")
def test_network_errors_do_not_log_webhook_secret(post, sleep, caplog):
    post.side_effect = requests.ConnectionError("secret_webhook_token")
    assert not DiscordNotifier("https://discord.com/api/webhooks/test").send_notification(*make_sample_data())
    assert "secret_webhook_token" not in caplog.text
