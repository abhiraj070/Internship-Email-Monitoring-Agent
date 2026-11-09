"""
Intelligent email classification and priority determination engine.
Adheres strictly to the classification guidelines, priority rules, and security constraints.
"""

import re
from typing import Optional, Tuple
from agent.models import EmailCategory, Priority, ClassificationResult, EmailMessage


class EmailClassifier:
    """Classifies emails and extracts structured metadata (company, action, deadline)."""

    # Generic marketing / newsletter / spam markers
    MARKETING_PATTERNS = [
        r"unsubscribe",
        r"view in (browser|web)",
        r"manage preferences",
        r"special offer",
        r"save \d+%",
        r"discount code",
        r"sale ends",
        r"course enroll",
        r"webinar registration",
        r"black friday",
        r"cyber monday",
        r"no-reply@marketing\.",
        r"newsletter@",
        r"promotions@",
        r"deals@",
    ]

    # Phishing / fraudulent indicator patterns
    SUSPICIOUS_PATTERNS = [
        r"telegram",
        r"whatsapp (only|chat)",
        r"wire transfer",
        r"bitcoin|crypto",
        r"cashier'?s check",
        r"pay upfront",
        r"payment for equipment",
        r"processing fee",
    ]

    # Category Matchers
    INTERVIEW_PATTERNS = [
        r"interview invitation",
        r"invitation to interview",
        r"schedule your (initial|phone|technical|final|behavioral) interview",
        r"interview availability",
        r"interview confirmed",
        r"interview scheduled",
        r"reschedule your interview",
        r"interview feedback",
        r"phone screen",
        r"technical screen",
        r"virtual interview",
        r"google meet with",
        r"zoom interview",
    ]

    ASSESSMENT_PATTERNS = [
        r"online assessment",
        r"coding assessment",
        r"coding test",
        r"coding challenge",
        r"hackerrank",
        r"codesignal",
        r"karat",
        r"codility",
        r"technical assessment",
        r"take-home assignment",
        r"complete your assessment",
        r"assessment invitation",
        r"assessment link",
    ]

    APPLICATION_UPDATE_PATTERNS = [
        r"application (received|confirmed|submitted|status)",
        r"thank you for applying",
        r"update on your application",
        r"status of your application",
        r"shortlisted",
        r"pleased to offer",
        r"congratulations on your offer",
        r"offer letter",
        r"moving forward with your candidacy",
        r"next steps in the process",
        r"unable to move forward",
        r"regret to inform",
        r"decided to pursue other candidates",
        r"position has been filled",
    ]

    RECRUITER_PATTERNS = [
        r"came across your (profile|resume|linkedin|github)",
        r"impressed by your background",
        r"reaching out regarding",
        r"would love to connect",
        r"recruiting team at",
        r"are you open to",
        r"send over your updated resume",
        r"provide your transcript",
        r"compensation and start date",
        r"joining discussion",
    ]

    OPPORTUNITY_PATTERNS = [
        r"internship opening",
        r"internship opportunity",
        r"summer \d{4} intern",
        r"fall \d{4} intern",
        r"winter \d{4} intern",
        r"spring \d{4} intern",
        r"we are hiring interns",
        r"applications are now open",
        r"internship program",
        r"recruitment drive",
    ]

    # Deadline extractors
    DEADLINE_PATTERNS = [
        r"(?:deadline|due date|complete by|submit by|expires on|valid until)[:\s]+([A-Za-z0-9,:\s/]+?)(?:\.|\n|$)",
        r"(?:within|in)\s+(\d+\s+(?:hours?|days?|weeks?))",
        r"(?:before|by)\s+([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?(?:, \d{4})?)",
        r"(?:by)\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
    ]

    # Action required extractors
    ACTION_PATTERNS = [
        (r"(schedule|book) your interview", "Schedule your interview using the provided link"),
        (r"complete (the|your) (assessment|test|challenge)", "Complete the online assessment before the deadline"),
        (r"(submit|send|provide) your (resume|transcript|documents|availability)", "Submit the requested documents or availability"),
        (r"(confirm|accept|sign) (your|the) (offer|agreement)", "Review and respond to the offer / agreement"),
        (r"(reply|respond) to this (email|message)", "Reply to the recruiter's message"),
        (r"(fill out|complete) (the|this) (form|survey)", "Complete the required form"),
    ]

    def classify(self, email: EmailMessage) -> ClassificationResult:
        """Analyze an email message and return structured classification."""
        subject = email.subject.lower()
        body = email.body_text.lower()
        sender_lower = email.sender_email.lower()
        full_text = f"{subject}\n{body}"

        # 1. Suspicious / Fraudulent detection
        for pat in self.SUSPICIOUS_PATTERNS:
            if re.search(pat, full_text):
                return ClassificationResult(
                    category=EmailCategory.REVIEW_REQUIRED,
                    priority=Priority.HIGH,
                    company_name=self._extract_company_name(email),
                    summary="Potential suspicious or fraudulent recruitment email detected. Exercise caution.",
                    action_required="Manually review with extreme caution. Do not click links or send sensitive info.",
                    deadline="N/A",
                    is_relevant=True,
                    reasoning=f"Matched suspicious pattern '{pat}'",
                )

        # 2. Check for commercial marketing / promotions
        is_promo = any(re.search(pat, full_text) for pat in self.MARKETING_PATTERNS)

        # If it has heavy marketing markers and doesn't clearly mention a personal interview or assessment
        has_direct_applicant_signal = any(
            re.search(pat, full_text)
            for pat in (self.INTERVIEW_PATTERNS + self.ASSESSMENT_PATTERNS)
        )

        if is_promo and not has_direct_applicant_signal:
            # Check if it mentions internships
            if re.search(r"\bintern(ship)?s?\b", full_text):
                # Promotional email that mentions internships -> could be low priority opportunity or marketing
                if re.search(r"newsletter|digest|weekly round|curated", full_text):
                    return ClassificationResult(
                        category=EmailCategory.INTERNSHIP_OPPORTUNITY,
                        priority=Priority.LOW,
                        company_name=self._extract_company_name(email),
                        summary=self._generate_summary(email, "Curated internship newsletter / announcement"),
                        action_required="Browse opportunities if interested",
                        deadline=self._extract_deadline(email.body_text),
                        is_relevant=True,
                        reasoning="General internship newsletter",
                    )
            # Otherwise not relevant
            return ClassificationResult(
                category=EmailCategory.NOT_RELEVANT,
                priority=Priority.LOW,
                company_name=self._extract_company_name(email),
                summary="Marketing, newsletter, or promotional email.",
                action_required="None",
                deadline="Not mentioned",
                is_relevant=False,
                reasoning="Matched marketing/promotional pattern",
            )

        # 3. Match Specific Categories
        category = None
        reasoning = None

        # Check Interview
        for pat in self.INTERVIEW_PATTERNS:
            if re.search(pat, full_text):
                category = EmailCategory.INTERVIEW
                reasoning = f"Matched interview pattern: {pat}"
                break

        # Check Assessment
        if not category:
            for pat in self.ASSESSMENT_PATTERNS:
                if re.search(pat, full_text):
                    category = EmailCategory.ASSESSMENT
                    reasoning = f"Matched assessment pattern: {pat}"
                    break

        # Check Application Update
        if not category:
            for pat in self.APPLICATION_UPDATE_PATTERNS:
                if re.search(pat, full_text):
                    category = EmailCategory.APPLICATION_UPDATE
                    reasoning = f"Matched application status pattern: {pat}"
                    break

        # Check Recruiter Communication
        if not category:
            for pat in self.RECRUITER_PATTERNS:
                if re.search(pat, full_text):
                    category = EmailCategory.RECRUITER_COMMUNICATION
                    reasoning = f"Matched recruiter communication pattern: {pat}"
                    break

        # Check Internship Opportunity
        if not category:
            for pat in self.OPPORTUNITY_PATTERNS:
                if re.search(pat, full_text):
                    category = EmailCategory.INTERNSHIP_OPPORTUNITY
                    reasoning = f"Matched internship opportunity pattern: {pat}"
                    break

        # Check Other Internship Related
        if not category:
            if re.search(r"\bintern(ship)?s?\b", full_text) or re.search(r"\bjob application\b", full_text):
                category = EmailCategory.OTHER_INTERNSHIP_RELATED
                reasoning = "Contains general internship or job application terms"

        # Default fallback: if no category matched
        if not category:
            # If from career/recruiting domain or subject mentions career, flag REVIEW_REQUIRED
            if any(term in sender_lower or term in subject for term in ["career", "recruit", "talent", "jobs", "hiring"]):
                category = EmailCategory.REVIEW_REQUIRED
                reasoning = "Uncertain career-related email requiring user review"
            else:
                return ClassificationResult(
                    category=EmailCategory.NOT_RELEVANT,
                    priority=Priority.LOW,
                    company_name="N/A",
                    summary="General email not related to internships or career opportunities.",
                    action_required="None",
                    deadline="Not mentioned",
                    is_relevant=False,
                    reasoning="No internship indicators detected",
                )

        company = self._extract_company_name(email)
        deadline = self._extract_deadline(email.body_text)
        action = self._extract_action(email.body_text)
        priority = self._determine_priority(category, full_text, deadline, action)
        summary = self._generate_summary(email, reasoning)

        return ClassificationResult(
            category=category,
            priority=priority,
            company_name=company,
            summary=summary,
            action_required=action,
            deadline=deadline,
            is_relevant=True,
            reasoning=reasoning,
        )

    def _determine_priority(
        self,
        category: EmailCategory,
        full_text: str,
        deadline: str,
        action: str,
    ) -> Priority:
        """Assign priority according to section 5 of specification."""
        # HIGH:
        # - Interview invitations.
        # - Assessment invitations.
        # - Application deadlines / Requests requiring immediate action.
        # - Selection or offer letters.
        if category in (EmailCategory.INTERVIEW, EmailCategory.ASSESSMENT):
            return Priority.HIGH

        if re.search(r"offer letter|pleased to offer|congratulations.*offer|selected for", full_text):
            return Priority.HIGH

        if deadline != "Not mentioned" and ("urgent" in full_text or "immediately" in full_text or "24 hours" in full_text or "48 hours" in full_text):
            return Priority.HIGH

        # MEDIUM:
        # - Application status updates.
        # - Recruiter communication.
        # - New internship opportunities.
        if category in (
            EmailCategory.APPLICATION_UPDATE,
            EmailCategory.RECRUITER_COMMUNICATION,
            EmailCategory.INTERNSHIP_OPPORTUNITY,
        ):
            return Priority.MEDIUM

        # LOW:
        # - General internship newsletters.
        # - Informational recruitment announcements.
        if "newsletter" in full_text or "digest" in full_text:
            return Priority.LOW

        if category == EmailCategory.REVIEW_REQUIRED:
            return Priority.MEDIUM

        return Priority.LOW

    def _extract_company_name(self, email: EmailMessage) -> str:
        """Extract sender company name from email headers, sender address, or subject."""
        # Check display sender (e.g., "Jane Doe from Google" or "Amazon Recruiting")
        sender_raw = email.sender
        if sender_raw:
            clean_sender = re.sub(r"<.*?>", "", sender_raw).strip()
            # "Recruiter at Stripe" -> Stripe
            m_at = re.search(r"(?:at|from)\s+([A-Za-z0-9\.\s]+?)(?:$|\s*(?:Recruiting|Team|Careers))", clean_sender, re.I)
            if m_at:
                return m_at.group(1).strip()
            # "Google Careers" -> Google
            m_team = re.search(r"^([A-Za-z0-9\.\s]+?)\s+(?:Careers|Recruiting|Jobs|Talent|Team)", clean_sender, re.I)
            if m_team:
                return m_team.group(1).strip()
            if len(clean_sender) > 0 and len(clean_sender) < 30 and "@" not in clean_sender:
                return clean_sender

        # Check sender domain (e.g. jobs@uber.com -> Uber)
        email_addr = email.sender_email
        if "@" in email_addr:
            domain = email_addr.split("@")[-1].lower()
            generic_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]
            if domain not in generic_domains:
                parts = domain.split(".")
                # e.g. careers.google.com -> google
                for part in reversed(parts[:-1]):
                    if part not in ["careers", "jobs", "mail", "recruiting", "email"]:
                        return part.capitalize()

        # Check subject (e.g. "[Stripe] Interview Invitation")
        m_subj = re.search(r"\[([A-Za-z0-9\s]+)\]", email.subject)
        if m_subj:
            return m_subj.group(1).strip()

        return "Not identified"

    def _extract_deadline(self, body: str) -> str:
        """Extract explicit deadline if mentioned."""
        for pat in self.DEADLINE_PATTERNS:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip()
                # Sanitize length to prevent excessive text capture
                if 2 < len(extracted) <= 50:
                    return extracted
        return "Not mentioned"

    def _extract_action(self, body: str) -> str:
        """Extract actionable next steps for the user."""
        for pat, action_text in self.ACTION_PATTERNS:
            if re.search(pat, body, re.IGNORECASE):
                return action_text
        return "Review email details and confirm if any response is needed."

    def _generate_summary(self, email: EmailMessage, reason: Optional[str] = None) -> str:
        """Generate a concise, safe summary from subject and snippet/body."""
        snippet = email.snippet.strip()
        if snippet:
            # Limit snippet to clean single sentence or ~180 characters
            cleaned = re.sub(r"\s+", " ", snippet)
            if len(cleaned) > 200:
                cleaned = cleaned[:197] + "..."
            return cleaned

        body_clean = re.sub(r"\s+", " ", email.body_text).strip()
        if body_clean:
            if len(body_clean) > 200:
                return body_clean[:197] + "..."
            return body_clean

        return email.subject
