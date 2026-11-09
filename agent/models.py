"""
Data models and enumerations for the Internship Email Monitoring Agent.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    INTERNSHIP_OPPORTUNITY = "INTERNSHIP_OPPORTUNITY"
    APPLICATION_UPDATE = "APPLICATION_UPDATE"
    INTERVIEW = "INTERVIEW"
    ASSESSMENT = "ASSESSMENT"
    RECRUITER_COMMUNICATION = "RECRUITER_COMMUNICATION"
    OTHER_INTERNSHIP_RELATED = "OTHER_INTERNSHIP_RELATED"
    NOT_RELEVANT = "NOT_RELEVANT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EmailMessage(BaseModel):
    """Normalized email message extracted from Gmail."""
    message_id: str
    thread_id: str
    sender: str
    sender_email: str
    subject: str
    date: str
    snippet: str = ""
    body_text: str = ""
    direct_link: str

    @property
    def display_sender(self) -> str:
        if self.sender and self.sender_email and self.sender_email != self.sender:
            return f"{self.sender} <{self.sender_email}>"
        return self.sender or self.sender_email or "Unknown Sender"


class ClassificationResult(BaseModel):
    """Result of analyzing and categorizing an email."""
    category: EmailCategory
    priority: Priority
    company_name: str = "Unknown"
    summary: str
    action_required: str = "None specified"
    deadline: str = "Not mentioned"
    is_relevant: bool = True
    reasoning: Optional[str] = None


class ProcessedRecord(BaseModel):
    """Persistent database record for processed emails."""
    message_id: str
    thread_id: str
    subject: str
    sender: str
    category: str
    priority: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    notification_sent: bool = False
