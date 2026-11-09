"""
Configuration settings for the Internship Email Monitoring Agent.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Agent environment and runtime settings."""

    # Gmail API Authentication
    GMAIL_CREDENTIALS_PATH: Path = Path(os.getenv("GMAIL_CREDENTIALS_PATH", BASE_DIR / "credentials.json"))
    GMAIL_TOKEN_PATH: Path = Path(os.getenv("GMAIL_TOKEN_PATH", BASE_DIR / "token.json"))
    GMAIL_SEARCH_QUERY: str = os.getenv("GMAIL_SEARCH_QUERY", "is:unread")
    MAX_EMAILS_PER_POLL: int = int(os.getenv("MAX_EMAILS_PER_POLL", "20"))

    # Discord Webhook
    DISCORD_WEBHOOK_URL: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL")

    # Storage
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
    DATABASE_PATH: Path = DATA_DIR / "processed_emails.db"

    # Execution Loop
    CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Optional AI Enhancements (Gemini / OpenAI API keys if configured)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")

    @classmethod
    def ensure_directories(cls):
        """Create necessary directories like data folder."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
