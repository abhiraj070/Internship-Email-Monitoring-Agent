"""
Core agent service orchestrating email monitoring, classification,
persistent deduplication, and Discord notifications.
"""

import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from agent.config import settings
from agent.gmail_client import GmailClient
from agent.storage import StorageEngine
from agent.classifier import EmailClassifier
from agent.notifier import DiscordNotifier
from agent.models import ProcessedRecord

logger = logging.getLogger(__name__)


class AgentService:
    """Orchestrates the lifecycle and polling cycles of the monitoring agent."""

    def __init__(
        self,
        gmail_client: Optional[GmailClient] = None,
        storage: Optional[StorageEngine] = None,
        classifier: Optional[EmailClassifier] = None,
        notifier: Optional[DiscordNotifier] = None,
    ):
        self.gmail = gmail_client or GmailClient()
        self.storage = storage or StorageEngine()
        self.classifier = classifier or EmailClassifier()
        self.notifier = notifier or DiscordNotifier()
        self._running = False

    def run_once(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes a single monitoring cycle:
        1. Retrieve newly received emails.
        2. Identify unprocessed messages.
        3. Extract relevant information.
        4. Classify each email.
        5. Evaluate its importance.
        6. Generate a concise summary.
        7. Send a Discord notification for relevant emails.
        8. Record processed email IDs.
        9. If nothing relevant is found, do not send unnecessary notifications.
        """
        stats = {
            "retrieved": 0,
            "unprocessed": 0,
            "relevant": 0,
            "notifications_sent": 0,
            "skipped_already_processed": 0,
        }

        logger.info("Starting email monitoring cycle...")

        # 1. Retrieve newly received emails
        message_ids = self.gmail.list_unprocessed_message_ids()
        stats["retrieved"] = len(message_ids)

        if not message_ids:
            logger.info("No candidate emails found matching query '%s'", settings.GMAIL_SEARCH_QUERY)
            return stats

        for msg_id in message_ids:
            # 2. Identify unprocessed messages
            if self.storage.is_processed(msg_id):
                stats["skipped_already_processed"] += 1
                logger.debug("Message %s already processed. Skipping.", msg_id)
                continue

            stats["unprocessed"] += 1

            # 3. Extract relevant information
            email_msg = self.gmail.get_email_message(msg_id)
            if not email_msg:
                logger.warning("Could not retrieve email message for id %s", msg_id)
                continue

            # 4, 5, 6. Classify each email, evaluate importance, generate summary
            classification = self.classifier.classify(email_msg)
            logger.info(
                "Processed email '%s' | Category: %s | Priority: %s | Company: %s",
                email_msg.subject,
                classification.category.value,
                classification.priority.value,
                classification.company_name,
            )

            notification_sent = False
            # 7. Send Discord notification for relevant emails
            if classification.is_relevant:
                stats["relevant"] += 1
                success = self.notifier.send_notification(
                    email=email_msg,
                    classification=classification,
                    dry_run=dry_run,
                )
                if success:
                    stats["notifications_sent"] += 1
                    notification_sent = True

            # 8. Record processed email ID in persistent storage
            record = ProcessedRecord(
                message_id=email_msg.message_id,
                thread_id=email_msg.thread_id,
                subject=email_msg.subject,
                sender=email_msg.display_sender,
                category=classification.category.value,
                priority=classification.priority.value,
                processed_at=datetime.now(timezone.utc),
                notification_sent=notification_sent,
            )
            self.storage.mark_processed(record)

        logger.info(
            "Cycle finished. Retrieved: %d, Unprocessed: %d, Relevant: %d, Alerts sent: %d",
            stats["retrieved"],
            stats["unprocessed"],
            stats["relevant"],
            stats["notifications_sent"],
        )
        return stats

    def start_loop(self, interval_seconds: Optional[int] = None, dry_run: bool = False):
        """Run continuous monitoring cycles at the configured interval."""
        interval = interval_seconds or settings.CHECK_INTERVAL_SECONDS
        self._running = True

        def handle_shutdown(signum, frame):
            logger.info("Shutdown signal received. Stopping monitoring agent...")
            self._running = False
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        logger.info("Internship Email Monitoring Agent started.")
        logger.info("Polling every %d seconds. Press Ctrl+C to stop.", interval)

        while self._running:
            try:
                self.run_once(dry_run=dry_run)
            except Exception as e:
                logger.error("Error during monitoring cycle: %s", e, exc_info=True)

            logger.info("Sleeping for %d seconds...", interval)
            time.sleep(interval)
