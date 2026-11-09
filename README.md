# Internship Email Monitoring Agent

An intelligent, non-destructive email-monitoring agent designed to scan your Gmail inbox and detect emails related to internships, job applications, assessments, interviews, and recruiter communications. It sends structured, prioritized alerts directly to your Discord channel via webhook so you never miss a deadline or opportunity.

---

## 🎯 Features

- **Non-Destructive Gmail Monitoring**: Uses the strict `gmail.readonly` OAuth2 scope. Never archives, deletes, or marks emails as read.
- **Intelligent Classification**: Analyzes sender, subject, full body, deadlines, and expected actions into 8 discrete categories:
  - `INTERNSHIP_OPPORTUNITY`
  - `APPLICATION_UPDATE`
  - `INTERVIEW`
  - `ASSESSMENT`
  - `RECRUITER_COMMUNICATION`
  - `OTHER_INTERNSHIP_RELATED`
  - `NOT_RELEVANT`
  - `REVIEW_REQUIRED` (Uncertain/suspicious emails flagged for manual check)
- **Priority Determination**:
  - 🔴 **HIGH**: Interview invitations, assessment invitations, urgent deadlines, offer letters.
  - 🟡 **MEDIUM**: Application status changes, recruiter inquiries, new openings.
  - 🟢 **LOW**: Curated newsletters, general announcements.
- **Duplicate Prevention Engine**: SQLite-backed deduplication tracks unique message IDs and thread histories so you never receive duplicate notifications.
- **Direct Gmail Links**: Every alert provides a direct link to the exact email in your browser.
- **Security Guardrails**:
  - Treats email text as untrusted.
  - Strips HTML scripts/styles safely.
  - Detects phishing/fraud markers (e.g. wire transfer, telegram requests).
  - Never auto-replies or executes embedded commands.

---

## 🔔 Discord Alert Format

```text
🔔 NEW INTERNSHIP EMAIL

Company: [Company Name]
Category: [Classification]
Sender: [Sender]
Subject: [Email Subject]

Summary:
[Concise summary of the email]

Action Required:
[What the user needs to do, if anything]

Deadline:
[Deadline, if mentioned]

Priority:
[HIGH / MEDIUM / LOW]

Email Link:
[Direct Gmail link]
```

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Google Cloud Console project with the **Gmail API** enabled and `credentials.json` (OAuth Desktop app) downloaded.
- A Discord server with a Webhook URL created (Server Settings > Integrations > Webhooks).

### 2. Installation
```bash
git clone https://github.com/abhiraj070/Internship-Email-Monitoring-Agent.git
cd Internship-Email-Monitoring-Agent

# Set up virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the template and configure your parameters:
```bash
copy .env.example .env
```
Edit `.env`:
```env
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
GMAIL_CREDENTIALS_PATH="credentials.json"
GMAIL_SEARCH_QUERY="is:unread"
CHECK_INTERVAL_SECONDS=300
```

Place your Google Cloud `credentials.json` in the root folder.

### 4. Authenticate Gmail
Run the one-time authentication flow to generate `token.json`:
```bash
python main.py --auth
```

### 5. Verify Discord Webhook
Send a test alert to your Discord channel:
```bash
python main.py --test-discord
```

---

## 🚀 Running the Agent

### Start Continuous Monitoring
Runs every 300 seconds (or configured interval):
```bash
python main.py
```

### Run a Single Cycle (Cron or Scheduled Task)
```bash
python main.py --once
```

### Dry Run (Simulate without sending notifications)
```bash
python main.py --dry-run
```

### Check Agent & Database Status
```bash
python main.py --status
```

---

## 🧪 Testing

Run the full pytest suite:
```bash
pytest -v
```
All 20 test cases cover classification, parsing, HTML sanitization, persistent deduplication, priority rules, and notification dispatching.
