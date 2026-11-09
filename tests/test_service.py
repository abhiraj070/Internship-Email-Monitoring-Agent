"""
Unit tests for AgentService monitoring cycle.
"""

from unittest.mock import MagicMock
from agent.service import AgentService
from agent.models import EmailMessage, ClassificationResult, EmailCategory, Priority


def make_dummy_email(msg_id: str = "msg_1") -> EmailMessage:
    return EmailMessage(
        message_id=msg_id,
        thread_id="th_test",
        sender="Recruiter",
        sender_email="recruiter@example.com",
        subject="Internship Application Status",
        date="today",
        snippet="Your application is under review",
        body_text="Your application is under review",
        direct_link="https://mail.google.com",
    )


def test_agent_service_cycle_skips_processed():
    mock_gmail = MagicMock()
    mock_storage = MagicMock()
    mock_classifier = MagicMock()
    mock_notifier = MagicMock()

    mock_gmail.list_unprocessed_message_ids.return_value = ["msg_1", "msg_2"]
    # msg_1 is already processed, msg_2 is not
    mock_storage.is_processed.side_effect = lambda mid: mid == "msg_1"
    mock_gmail.get_email_message.return_value = make_dummy_email("msg_2")

    classification = ClassificationResult(
        category=EmailCategory.APPLICATION_UPDATE,
        priority=Priority.MEDIUM,
        company_name="Example Corp",
        summary="Application under review",
        action_required="None",
        deadline="Not mentioned",
        is_relevant=True,
    )
    mock_classifier.classify.return_value = classification

    service = AgentService(
        gmail_client=mock_gmail,
        storage=mock_storage,
        classifier=mock_classifier,
        notifier=mock_notifier,
    )

    stats = service.run_once(dry_run=True)

    assert stats["retrieved"] == 2
    assert stats["skipped_already_processed"] == 1
    assert stats["unprocessed"] == 1
    # Only msg_2 should have been fetched
    mock_gmail.get_email_message.assert_called_once_with("msg_2")


def test_agent_service_cycle_relevant_notified():
    mock_gmail = MagicMock()
    mock_storage = MagicMock()
    mock_classifier = MagicMock()
    mock_notifier = MagicMock()

    mock_gmail.list_unprocessed_message_ids.return_value = ["msg_interview"]
    mock_storage.is_processed.return_value = False

    email = EmailMessage(
        message_id="msg_interview",
        thread_id="th_interview",
        sender="HR",
        sender_email="hr@google.com",
        subject="Interview Invitation",
        date="today",
        snippet="interview",
        body_text="interview",
        direct_link="https://mail.google.com",
    )
    mock_gmail.get_email_message.return_value = email

    classification = ClassificationResult(
        category=EmailCategory.INTERVIEW,
        priority=Priority.HIGH,
        company_name="Google",
        summary="Interview confirmed",
        action_required="Schedule slot",
        deadline="Friday",
        is_relevant=True,
    )
    mock_classifier.classify.return_value = classification
    mock_notifier.send_notification.return_value = True

    service = AgentService(
        gmail_client=mock_gmail,
        storage=mock_storage,
        classifier=mock_classifier,
        notifier=mock_notifier,
    )

    stats = service.run_once(dry_run=False)

    assert stats["relevant"] == 1
    assert stats["notifications_sent"] == 1
    mock_notifier.send_notification.assert_called_once()
    mock_storage.mark_processed.assert_called_once()


def test_agent_service_cycle_non_relevant_no_notification():
    mock_gmail = MagicMock()
    mock_storage = MagicMock()
    mock_classifier = MagicMock()
    mock_notifier = MagicMock()

    mock_gmail.list_unprocessed_message_ids.return_value = ["msg_spam"]
    mock_storage.is_processed.return_value = False

    email = EmailMessage(
        message_id="msg_spam",
        thread_id="th_spam",
        sender="Store",
        sender_email="store@shoes.com",
        subject="50% Discount on Shoes",
        date="today",
        snippet="Buy shoes",
        body_text="Buy shoes",
        direct_link="https://mail.google.com",
    )
    mock_gmail.get_email_message.return_value = email

    classification = ClassificationResult(
        category=EmailCategory.NOT_RELEVANT,
        priority=Priority.LOW,
        company_name="Store",
        summary="Spam shoe ad",
        action_required="None",
        deadline="Not mentioned",
        is_relevant=False,
    )
    mock_classifier.classify.return_value = classification

    service = AgentService(
        gmail_client=mock_gmail,
        storage=mock_storage,
        classifier=mock_classifier,
        notifier=mock_notifier,
    )

    stats = service.run_once(dry_run=False)

    assert stats["relevant"] == 0
    assert stats["notifications_sent"] == 0
    mock_notifier.send_notification.assert_not_called()
    # It must STILL be marked as processed to prevent re-checking!
    mock_storage.mark_processed.assert_called_once()
