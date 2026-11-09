"""
Unit tests for GmailClient payload parsing and safety mechanisms.
"""

import base64
from agent.gmail_client import GmailClient, SCOPES


def test_scopes_read_only():
    # Enforces non-destructive security guarantee
    assert SCOPES == ["https://www.googleapis.com/auth/gmail.readonly"]


def test_parse_message_payload_plain_text():
    client = GmailClient()

    plain_content = "Hello Abhiraj, you are invited to interview."
    encoded = base64.urlsafe_b64encode(plain_content.encode("utf-8")).decode("utf-8")

    fake_msg = {
        "id": "18a1b2c3d4e5f6",
        "threadId": "th_12345",
        "snippet": "Hello Abhiraj, you are invited...",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Google Internship Interview"},
                {"name": "From", "value": "Google Careers <careers@google.com>"},
                {"name": "Date", "value": "Mon, 9 Nov 2026 12:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": encoded},
        },
    }

    parsed = client._parse_message_payload(fake_msg)

    assert parsed.message_id == "18a1b2c3d4e5f6"
    assert parsed.thread_id == "th_12345"
    assert parsed.subject == "Google Internship Interview"
    assert parsed.sender == "Google Careers"
    assert parsed.sender_email == "careers@google.com"
    assert parsed.body_text == plain_content
    assert parsed.direct_link == "https://mail.google.com/mail/u/0/#inbox/18a1b2c3d4e5f6"


def test_parse_message_payload_html_sanitized():
    client = GmailClient()

    html_content = "<html><head><script>alert('malicious')</script></head><body><p>Congratulations on your <b>Offer Letter</b>!</p></body></html>"
    encoded = base64.urlsafe_b64encode(html_content.encode("utf-8")).decode("utf-8")

    fake_msg = {
        "id": "html_msg_1",
        "threadId": "th_html",
        "snippet": "Congratulations...",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Offer Letter"},
                {"name": "From", "value": "hr@apple.com"},
            ],
            "mimeType": "text/html",
            "body": {"data": encoded},
        },
    }

    parsed = client._parse_message_payload(fake_msg)

    assert "alert" not in parsed.body_text  # Script stripped
    assert "Congratulations on your Offer Letter!" in parsed.body_text
    assert parsed.direct_link == "https://mail.google.com/mail/u/0/#inbox/html_msg_1"
