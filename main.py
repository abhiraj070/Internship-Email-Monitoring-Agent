"""
Internship Email Monitoring Agent - Application Entrypoint & CLI.
"""

import argparse
import logging
import sys
from agent.config import settings
from agent.service import AgentService
from agent.gmail_client import GmailClient
from agent.storage import StorageEngine
from agent.notifier import DiscordNotifier
from agent.classifier import EmailClassifier
from agent.models import EmailMessage, ClassificationResult, EmailCategory, Priority


def setup_logging(level_name: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def test_discord_webhook():
    """Send a test internship notification to verify Discord webhook."""
    print("Testing Discord webhook configuration...")
    if not settings.DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set in environment or .env file.")
        sys.exit(1)

    notifier = DiscordNotifier()
    test_email = EmailMessage(
        message_id="test_msg_001",
        thread_id="test_th_001",
        sender="Google Careers",
        sender_email="careers@google.com",
        subject="[Test] Software Engineering Intern Interview Invitation",
        date="Current",
        snippet="This is a test notification confirming your Discord webhook is active.",
        body_text="This is a test notification confirming your Discord webhook is active.",
        direct_link="https://mail.google.com/mail/u/0/#inbox",
    )
    test_classification = ClassificationResult(
        category=EmailCategory.INTERVIEW,
        priority=Priority.HIGH,
        company_name="Google",
        summary="Test notification confirming the Internship Email Monitoring Agent webhook setup is operational.",
        action_required="None - Webhook setup verified!",
        deadline="Not mentioned",
        is_relevant=True,
    )

    success = notifier.send_notification(test_email, test_classification)
    if success:
        print("[SUCCESS] Test notification delivered to Discord successfully!")
    else:
        print("[ERROR] Failed to send Discord notification. Please verify your webhook URL.")


def check_status():
    """Print current tracking database status."""
    storage = StorageEngine()
    total = storage.get_total_processed()
    print("=== Internship Email Monitoring Agent Status ===")
    print(f"Database Path    : {settings.DATABASE_PATH}")
    print(f"Total Processed  : {total} emails")
    print(f"Check Interval   : {settings.CHECK_INTERVAL_SECONDS} seconds")
    print(f"Search Query     : '{settings.GMAIL_SEARCH_QUERY}'")
    print(f"Gmail Token Path : {settings.GMAIL_TOKEN_PATH} (Exists: {settings.GMAIL_TOKEN_PATH.exists()})")
    print(f"Discord Webhook  : {'Configured' if settings.DISCORD_WEBHOOK_URL else 'Not set'}")


def main():
    parser = argparse.ArgumentParser(
        description="Internship Email Monitoring Agent: Automatic Gmail scanner for career and internship emails.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single monitoring cycle and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without sending actual Discord notifications.",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Authenticate with Gmail API and generate token.json.",
    )
    parser.add_argument(
        "--test-discord",
        action="store_true",
        help="Send a test notification to verify the Discord webhook configuration.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show database and configuration status.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=settings.CHECK_INTERVAL_SECONDS,
        help="Override polling interval in seconds.",
    )

    args = parser.parse_args()
    setup_logging(settings.LOG_LEVEL)

    if args.status:
        check_status()
        return

    if args.test_discord:
        test_discord_webhook()
        return

    gmail = GmailClient()

    if args.auth:
        print("Starting Gmail OAuth2 authentication...")
        if gmail.authenticate(interactive=True):
            print(f"[SUCCESS] Authenticated successfully. Token saved to {settings.GMAIL_TOKEN_PATH}")
        else:
            print("[ERROR] Authentication failed. Ensure credentials.json is present.")
            sys.exit(1)
        return

    # Normal execution flow
    if not settings.GMAIL_TOKEN_PATH.exists():
        print(f"Token file not found at {settings.GMAIL_TOKEN_PATH}. Attempting initial authentication...")
        if not gmail.authenticate(interactive=True):
            print("Authentication failed. Run with --auth after placing credentials.json.")
            sys.exit(1)
    else:
        if not gmail.authenticate(interactive=False):
            print("Cached token invalid. Please re-run with --auth to refresh credentials.")
            sys.exit(1)

    service = AgentService(gmail_client=gmail)

    if args.once:
        print("Running single monitoring cycle...")
        stats = service.run_once(dry_run=args.dry_run)
        print("Cycle completed:", stats)
    else:
        service.start_loop(interval_seconds=args.interval, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
