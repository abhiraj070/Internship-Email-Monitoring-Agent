"""
Unit tests for GmailClient payload parsing and safety mechanisms.
"""

import base64
from unittest.mock import MagicMock
import pytest
from agent.gmail_client import GmailClient, SCOPES


def test_listing_failure_is_not_reported_as_empty_inbox():
    client = GmailClient()
    client.service = MagicMock()
    client.service.users().messages().list().execute.side_effect = RuntimeError('offline')
    with pytest.raises(RuntimeError, match='Gmail message listing failed'):
        client.list_unprocessed_message_ids()


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
    assert parsed.direct_link == "https://mail.google.com/mail/#all/th_12345"


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
    assert parsed.direct_link == "https://mail.google.com/mail/#all/th_html"


def test_links_select_monitored_account_and_find_exact_message():
    from urllib.parse import parse_qs, unquote, urlsplit
    client = GmailClient()
    client.account_email = 'second+alerts@example.com'
    parsed = client._parse_message_payload({
        'id': 'message-2', 'threadId': 'conversation-1',
        'payload': {'headers': [{'name': 'Message-ID', 'value': '<unique+id/part@example.com>'}]},
    })
    direct = urlsplit(parsed.direct_link)
    exact = urlsplit(parsed.exact_search_link)
    assert parse_qs(direct.query) == {'authuser': ['second+alerts@example.com']}
    assert direct.fragment == 'all/conversation-1'
    assert parse_qs(exact.query) == parse_qs(direct.query)
    assert unquote(exact.fragment) == 'search/rfc822msgid:unique+id/part@example.com'
    assert '#inbox' not in parsed.direct_link


def test_missing_thread_id_links_to_message_in_all_mail():
    client = GmailClient()
    parsed = client._parse_message_payload({'id': 'message-only', 'payload': {}})
    assert parsed.direct_link.endswith('#all/message-only')
    assert parsed.exact_search_link is None
