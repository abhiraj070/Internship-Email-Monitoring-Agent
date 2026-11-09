"""
Gmail API client for fetching and parsing emails.
Strictly non-destructive (uses gmail.readonly scope).
"""

import base64
import email.utils
import logging
import re
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from agent.models import EmailMessage
from agent.config import settings

logger = logging.getLogger(__name__)

# Strictly read-only scope to enforce non-destructive operations
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    """Read-only Gmail client for monitoring candidate messages."""

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
    ):
        self.credentials_path = credentials_path or settings.GMAIL_CREDENTIALS_PATH
        self.token_path = token_path or settings.GMAIL_TOKEN_PATH
        self.service: Optional[Resource] = None

    def authenticate(self, interactive: bool = True) -> bool:
        """Authenticate with Google OAuth2."""
        creds = None

        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                logger.warning("Error loading existing token.json: %s", e)

        # Refresh or initiate flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning("Failed to refresh token: %s", e)
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    logger.error(
                        "OAuth credentials not found at %s. Please download credentials.json from Google Cloud Console.",
                        self.credentials_path,
                    )
                    return False

                if not interactive:
                    logger.error("Interactive authentication required but running non-interactively.")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path),
                        SCOPES,
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error("OAuth flow failed: %s", e)
                    return False

            # Save valid credentials for future runs
            if creds:
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())

        try:
            self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            return True
        except Exception as e:
            logger.error("Failed to build Gmail service: %s", e)
            return False

    def list_unprocessed_message_ids(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[str]:
        """Fetch list of message IDs matching the search query."""
        if not self.service:
            logger.error("Gmail service not initialized. Call authenticate() first.")
            return []

        search_query = query if query is not None else settings.GMAIL_SEARCH_QUERY
        limit = max_results or settings.MAX_EMAILS_PER_POLL

        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=search_query, maxResults=limit)
                .execute()
            )
            messages = results.get("messages", [])
            return [m["id"] for m in messages if "id" in m]
        except HttpError as error:
            logger.error("An error occurred while listing messages: %s", error)
            return []
        except Exception as e:
            logger.error("Unexpected error querying messages: %s", e)
            return []

    def get_email_message(self, message_id: str) -> Optional[EmailMessage]:
        """Fetch and parse a full email message safely."""
        if not self.service:
            return None

        try:
            msg_data = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            return self._parse_message_payload(msg_data)
        except HttpError as error:
            logger.error("HttpError fetching message %s: %s", message_id, error)
            return None
        except Exception as e:
            logger.error("Error parsing message %s: %s", message_id, e)
            return None

    def _parse_message_payload(self, msg_data: dict) -> EmailMessage:
        """Parse raw Gmail API response into normalized EmailMessage."""
        message_id = msg_data.get("id", "")
        thread_id = msg_data.get("threadId", "")
        snippet = msg_data.get("snippet", "")
        payload = msg_data.get("payload", {})
        headers = payload.get("headers", [])

        # Extract headers
        header_map = {h["name"].lower(): h["value"] for h in headers if "name" in h and "value" in h}
        subject = header_map.get("subject", "(No Subject)")
        raw_from = header_map.get("from", "Unknown")
        date = header_map.get("date", "")

        sender_name, sender_email = email.utils.parseaddr(raw_from)
        if not sender_name:
            sender_name = raw_from

        body_text = self._extract_body(payload)

        direct_link = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"

        return EmailMessage(
            message_id=message_id,
            thread_id=thread_id,
            sender=sender_name,
            sender_email=sender_email,
            subject=subject,
            date=date,
            snippet=snippet,
            body_text=body_text,
            direct_link=direct_link,
        )

    def _extract_body(self, payload: dict) -> str:
        """Extract clean text from MIME payload."""
        plain_parts = []
        html_parts = []

        def walk_parts(part: dict):
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")

            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8", errors="replace")
                    if mime_type == "text/plain":
                        plain_parts.append(decoded)
                    elif mime_type == "text/html":
                        html_parts.append(decoded)
                except Exception as e:
                    logger.debug("Failed to decode part: %s", e)

            for subpart in part.get("parts", []):
                walk_parts(subpart)

        walk_parts(payload)

        # Prefer plain text
        if plain_parts:
            return "\n".join(plain_parts).strip()

        # Fallback to sanitized HTML text
        if html_parts:
            soup = BeautifulSoup("\n".join(html_parts), "html.parser")
            # Strip non-text elements
            for tag in soup(["script", "style", "meta", "link"]):
                tag.decompose()
            raw_text = soup.get_text(separator=" ", strip=True)
            # Remove spaces before punctuation and collapse whitespace
            cleaned = re.sub(r"\s+([,.!?:;])", r"\1", raw_text)
            return re.sub(r"[ \t]+", " ", cleaned).strip()

        return ""
