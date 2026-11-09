"""
Unit tests for DiscordNotifier.
"""

from unittest.mock import patch, MagicMock
from agent.models import EmailMessage, ClassificationResult, EmailCategory, Priority
from agent.notifier import DiscordNotifier, PRIORITY_COLORS


def make_sample_data():
    email = EmailMessage(
        message_id="msg_999",
        thread_id="th_999",
        sender="Jane Recruiter",
        sender_email="jane@stripe.com",
        subject="Summer 2027 Engineering Internship Interview",
        date="Mon, 9 Nov 2026 10:00:00 +0000",
        snippet="Please choose a time slot for your interview.",
        body_text="Please choose a time slot for your interview.",
        direct_link="https://mail.google.com/mail/u/0/#inbox/msg_999",
    )
    classification = ClassificationResult(
        category=EmailCategory.INTERVIEW,
        priority=Priority.HIGH,
        company_name="Stripe",
        summary="Invitation to schedule a technical interview.",
        action_required="Schedule your interview using the provided link",
        deadline="Friday, 5 PM",
        is_relevant=True,
    )
    return email, classification


def test_format_plain_text_matches_spec():
    email, classification = make_sample_data()
    text = DiscordNotifier.format_plain_text(email, classification)

    assert "🔔 NEW INTERNSHIP EMAIL" in text
    assert "Company: Stripe" in text
    assert "Category: INTERVIEW" in text
    assert "Sender: Jane Recruiter <jane@stripe.com>" in text
    assert "Subject: Summer 2027 Engineering Internship Interview" in text
    assert "Summary:\nInvitation to schedule a technical interview." in text
    assert "Action Required:\nSchedule your interview using the provided link" in text
    assert "Deadline:\nFriday, 5 PM" in text
    assert "Priority:\nHIGH" in text
    assert "Email Link:\nhttps://mail.google.com/mail/u/0/#inbox/msg_999" in text


def test_format_embed():
    email, classification = make_sample_data()
    embed = DiscordNotifier.format_embed(email, classification)

    assert embed["color"] == PRIORITY_COLORS[Priority.HIGH]
    assert "Stripe" in embed["title"]
    field_names = [f["name"] for f in embed["fields"]]
    assert "Priority" in field_names
    assert "Deadline" in field_names
    assert "Action Required" in field_names


def test_send_notification_dry_run():
    email, classification = make_sample_data()
    notifier = DiscordNotifier(webhook_url=None)
    success = notifier.send_notification(email, classification, dry_run=True)
    assert success is True


@patch("requests.post")
def test_send_notification_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_post.return_value = mock_resp

    email, classification = make_sample_data()
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/mock")
    success = notifier.send_notification(email, classification)

    assert success is True
    assert mock_post.called
    payload = mock_post.call_args[1]["json"]
    assert "content" in payload
    assert "embeds" in payload
