"""One non-interactive polling cycle for GitHub Actions."""

import logging
import os
from pathlib import Path

from agent.cloud_state import CloudState
from agent.config import settings
from agent.gmail_client import GmailClient
from agent.service import AgentService


def main():
    # The local runner logs email subjects. Cloud logs deliberately omit them.
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    state = CloudState(Path(os.environ["EMAIL_STATE_PATH"]))
    if not settings.DISCORD_WEBHOOK_URL:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL repository secret")
    gmail = GmailClient()
    if not gmail.authenticate(interactive=False):
        raise SystemExit("Gmail authorization failed. Regenerate GMAIL_TOKEN_JSON locally.")
    stats = AgentService(gmail_client=gmail, storage=state).run_once()
    print("Email monitoring cycle:", stats)
    if stats["notifications_failed"]:
        raise SystemExit("Some alerts were not delivered; they remain eligible for retry.")


if __name__ == "__main__":
    main()
