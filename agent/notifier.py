"""
Discord notification dispatcher for internship alerts.
Formats messages according to the exact project specification.
"""

import logging
import time
from typing import Optional, Dict, Any
import requests

from agent.models import EmailMessage, ClassificationResult, Priority
from agent.config import settings

logger = logging.getLogger(__name__)

# Discord embed colors
PRIORITY_COLORS = {
    Priority.HIGH: 0xE74C3C,    # Red
    Priority.MEDIUM: 0xF39C12,  # Amber / Gold
    Priority.LOW: 0x3498DB,     # Blue
}


class DiscordNotifier:
    """Dispatches formatted alerts to a Discord webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL

    @classmethod
    def format_plain_text(cls, email: EmailMessage, classification: ClassificationResult) -> str:
        """Format the exact message string mandated in the specification."""
        return (
            "🔔 NEW INTERNSHIP EMAIL\n\n"
            f"Company: {classification.company_name}\n"
            f"Category: {classification.category.value}\n"
            f"Sender: {email.display_sender}\n"
            f"Subject: {email.subject}\n\n"
            "Summary:\n"
            f"{classification.summary}\n\n"
            "Action Required:\n"
            f"{classification.action_required}\n\n"
            "Deadline:\n"
            f"{classification.deadline}\n\n"
            "Priority:\n"
            f"{classification.priority.value}\n\n"
            "Email Link:\n"
            f"{email.direct_link}"
        )

    @classmethod
    def format_embed(cls, email: EmailMessage, classification: ClassificationResult) -> Dict[str, Any]:
        """Create a Discord embed representation with priority color coding."""
        color = PRIORITY_COLORS.get(classification.priority, 0x95A5A6)
        return {
            "title": f"🔔 {classification.company_name} - {classification.category.value}",
            "description": f"**Subject:** {email.subject}\n\n{classification.summary}",
            "color": color,
            "fields": [
                {
                    "name": "Priority",
                    "value": f"`{classification.priority.value}`",
                    "inline": True,
                },
                {
                    "name": "Deadline",
                    "value": classification.deadline,
                    "inline": True,
                },
                {
                    "name": "Action Required",
                    "value": classification.action_required,
                    "inline": False,
                },
                {
                    "name": "Sender",
                    "value": email.display_sender,
                    "inline": True,
                },
                {
                    "name": "Gmail Link",
                    "value": f"[Open Email]({email.direct_link})",
                    "inline": True,
                },
            ],
            "footer": {
                "text": "Internship Email Monitoring Agent",
            },
        }

    def send_notification(
        self,
        email: EmailMessage,
        classification: ClassificationResult,
        dry_run: bool = False,
    ) -> bool:
        """Send notification via webhook. Returns True on success."""
        content = self.format_plain_text(email, classification)
        embed = self.format_embed(email, classification)

        if dry_run:
            logger.info("Notification Dry Run:\n%s", content)
            return True
        if not self.webhook_url:
            logger.error("DISCORD_WEBHOOK_URL is not configured; alert remains pending.")
            return False

        # Bound untrusted email text to Discord's message/embed limits.
        embed["title"] = embed["title"][:256]
        embed["description"] = embed["description"][:2000]
        for field in embed["fields"]:
            field["value"] = str(field["value"] or "Not mentioned")[:700]

        payload = {
            "content": content[:2000],
            "embeds": [embed],
            "allowed_mentions": {"parse": []},
        }

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    self.webhook_url,
                    params={"wait": "true"},
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

                if response.status_code == 204 or response.status_code == 200:
                    logger.info("Successfully dispatched Discord notification for msg %s", email.message_id)
                    return True

                if response.status_code == 429:
                    # Discord rate-limited
                    try:
                        retry_after = max(0, min(float(response.json().get("retry_after", 2)), 60))
                    except (ValueError, TypeError):
                        retry_after = 2.0
                    logger.warning("Discord rate limited. Sleeping %s seconds...", retry_after)
                    time.sleep(retry_after)
                    continue

                if response.status_code >= 500 and attempt < max_retries:
                    time.sleep(1.5 * attempt)
                    continue
                logger.error("Discord webhook error: HTTP %s", response.status_code)
                return False

            except requests.RequestException as e:
                # Request exception strings can contain the secret webhook URL.
                logger.error("Network error sending notification (attempt %d): %s", attempt, type(e).__name__)
                if attempt < max_retries:
                    time.sleep(1.5 * attempt)
                else:
                    return False

        return False
