"""
Unit tests for the EmailClassifier engine.
"""

from agent.models import EmailMessage, EmailCategory, Priority
from agent.classifier import EmailClassifier


def make_email(
    subject: str,
    body: str,
    sender: str = "Recruiter <recruiter@company.com>",
    sender_email: str = "recruiter@company.com",
    snippet: str = "",
) -> EmailMessage:
    return EmailMessage(
        message_id="msg_test",
        thread_id="th_test",
        sender=sender,
        sender_email=sender_email,
        subject=subject,
        date="Mon, 9 Nov 2026 10:00:00 +0000",
        snippet=snippet or body[:100],
        body_text=body,
        direct_link="https://mail.google.com/mail/u/0/#inbox/msg_test",
    )


def test_classify_interview_invitation():
    classifier = EmailClassifier()
    email = make_email(
        subject="Invitation to Interview: Software Engineering Intern at Google",
        body="Hi Abhiraj, we were impressed by your resume and would like to schedule your technical interview. Please book your interview slot by Friday.",
        sender="Google Careers <careers@google.com>",
        sender_email="careers@google.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.INTERVIEW
    assert result.priority == Priority.HIGH
    assert result.is_relevant is True
    assert "Google" in result.company_name
    assert "interview" in result.action_required.lower()


def test_classify_assessment():
    classifier = EmailClassifier()
    email = make_email(
        subject="Amazon Internship Online Assessment Invitation",
        body="Dear candidate, please complete the coding assessment on HackerRank. Deadline: Nov 15th.",
        sender="Amazon Recruiting <talent@amazon.com>",
        sender_email="talent@amazon.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.ASSESSMENT
    assert result.priority == Priority.HIGH
    assert result.is_relevant is True
    assert "Amazon" in result.company_name
    assert "Nov 15th" in result.deadline


def test_classify_job_offer():
    classifier = EmailClassifier()
    email = make_email(
        subject="Offer Letter: Summer 2027 Intern",
        body="We are pleased to offer you the position of Software Engineering Intern! Please review and confirm your offer.",
        sender="Stripe People <recruiting@stripe.com>",
        sender_email="recruiting@stripe.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.APPLICATION_UPDATE
    assert result.priority == Priority.HIGH
    assert result.is_relevant is True


def test_classify_application_update():
    classifier = EmailClassifier()
    email = make_email(
        subject="Update on your application for 2027 Intern",
        body="Thank you for applying. We have reviewed your application and will contact you regarding next steps in the process.",
        sender="Meta Recruiting <careers@meta.com>",
        sender_email="careers@meta.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.APPLICATION_UPDATE
    assert result.priority == Priority.MEDIUM
    assert result.is_relevant is True


def test_classify_recruiter_outreach():
    classifier = EmailClassifier()
    email = make_email(
        subject="Internship opportunities at Datadog",
        body="Hi Abhiraj, I came across your GitHub profile and was impressed by your background. Would love to connect regarding an internship position.",
        sender="Recruiter at Datadog <recruiter@datadog.com>",
        sender_email="recruiter@datadog.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.RECRUITER_COMMUNICATION
    assert result.priority == Priority.MEDIUM
    assert result.is_relevant is True


def test_classify_marketing_promo_ignored():
    classifier = EmailClassifier()
    email = make_email(
        subject="Special Offer: 50% discount on tech courses!",
        body="Save 50% on all machine learning bootcamps! Unsubscribe here. Sale ends this midnight.",
        sender="Course Academy <promotions@bootcamp.com>",
        sender_email="promotions@bootcamp.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.NOT_RELEVANT
    assert result.is_relevant is False


def test_classify_suspicious_phishing():
    classifier = EmailClassifier()
    email = make_email(
        subject="Urgent Job Offer: Work from home intern",
        body="You have been selected. Please message our hiring manager on Telegram and wire transfer $100 for equipment.",
        sender="hr_urgent_job@gmail.com",
        sender_email="hr_urgent_job@gmail.com",
    )

    result = classifier.classify(email)
    assert result.category == EmailCategory.REVIEW_REQUIRED
    assert result.priority == Priority.HIGH
    assert result.is_relevant is True
