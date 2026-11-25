# Gmail email alerts on GitHub Actions

The `Gmail Email Alerts` workflow checks Gmail once daily at approximately 9 AM IST (03:30 UTC). It uses the email-alerts Discord webhook, separately from the internship listings bot. Scheduled runs remain skipped until repository variable `EMAIL_MONITOR_ENABLED` is set to `true`.

## 1. Create Google credentials

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create/select a project, for example `Internship Email Alerts`.
2. Open **APIs & Services > Library**, find **Gmail API**, and click **Enable**.
3. Open **Google Auth Platform > Branding** (or **APIs & Services > OAuth consent screen**) and configure an app name, support email, and developer contact email.
4. Under **Audience**, choose **External** for a personal Gmail account. While the app is in **Testing**, add the Gmail address you want monitored under **Test users**.
5. Under **Data Access > Add or remove scopes**, add only `https://www.googleapis.com/auth/gmail.readonly`.
6. For ongoing unattended use, switch the app's publishing status to **In production** under **Audience** before generating the token. Testing-mode refresh tokens for Gmail access expire after seven days. Publishing status and Google's verification status are separate; Google can still show an unverified-app notice or impose account/organization restrictions.
7. Under **Clients > Create client**, select **Desktop app**, name it, create it, and download its JSON file.
8. Rename the downloaded file to `credentials.json` and place it in `C:\Code\Projects\Internship-Email-Monitoring-Agent`.

The app uses read-only Gmail access. It does not need your Gmail password or a service-account key.

References: [Google Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python), [Google refresh-token expiration](https://developers.google.com/identity/protocols/oauth2/#expiration).

## 2. Authorize once on your PC

Open PowerShell and run:

```powershell
cd C:\Code\Projects\Internship-Email-Monitoring-Agent
.\.venv\Scripts\python.exe main.py --auth
```

Sign in to the Gmail account you want monitored and approve the read-only access request. The command creates `token.json` in the project folder. Both credential files are ignored by Git. If you previously authorized in Testing mode, generate a fresh token after moving to Production: rename the old `token.json` out of the way first, then run the authorization command again.

## 3. Add two repository secrets

Open [this repository's Actions secrets settings](https://github.com/abhiraj070/Internship-Email-Monitoring-Agent/settings/secrets/actions). Choose **New repository secret** for each:

| Secret name | Value |
| --- | --- |
| `GMAIL_TOKEN_JSON` | The complete contents of the locally generated `token.json`, including the outer braces. |
| `DISCORD_WEBHOOK_URL` | The email-alerts webhook URL already configured in your local `.env`. Use the email-alerts URL, not the internship-updates URL. |

You can open `token.json` in a text editor or copy it directly to the clipboard from PowerShell:

```powershell
Get-Content -Raw .\token.json | Set-Clipboard
```

The runner does not need a separate `credentials.json` secret: the authorized-user token JSON contains the client ID, client secret, and refresh token needed for unattended refresh. Do not paste credentials into issues, workflow files, Git commits, or Actions logs.

## 4. Test, then enable the schedule

1. Open [Actions](https://github.com/abhiraj070/Internship-Email-Monitoring-Agent/actions), select **Gmail Email Alerts**, then **Run workflow** on `main`. Manual runs are allowed before enabling the schedule.
2. Confirm the run succeeds and relevant email alerts appear in the email-alerts Discord channel. A run with no relevant emails sends no message.
3. Under **Settings > Secrets and variables > Actions > Variables**, add repository variable `EMAIL_MONITOR_ENABLED` with value `true`.

Default cloud search: `in:inbox is:unread newer_than:1d`. This includes only unread inbox emails from the last day, excluding read emails and older mail. The live repository variable `GMAIL_SEARCH_QUERY` uses the same filter. The agent leaves emails unread and uses persistent tracking to avoid duplicate alerts. A rolling one-day window excludes older mail if a daily run is delayed or missed.

The workflow grants its built-in token `contents: write` so it can maintain the `email-monitor-state` branch. If repository rules block that branch or token writes, the checkpoint step fails; adjust those rules before relying on unattended runs.

## Persistence and operational limits

- Only SHA-256 message-ID fingerprints are committed to `email-monitor-state`. Email subjects, senders, content, Gmail tokens, and Discord webhook URLs are never committed by the workflow. Public fingerprints still reveal counts and activity timing.
- Completed deliveries are checkpointed even when later deliveries fail. Do not delete the state branch unless you intentionally want matching messages reconsidered. Separate local and cloud runs have separate tracking state.
- Runs are serialized. A runner crash or a failed state push after Discord delivery can cause duplicate alerts on the next run; delivery is not exactly once.
- Gmail authorization happens locally. Actions never opens a sign-in browser. If Google revokes or expires the refresh token, reauthorize locally and replace `GMAIL_TOKEN_JSON`.
- GitHub schedules are best effort and can be delayed. Public repositories can have schedules disabled after 60 days of inactivity. Check the Actions page when alerts stop.

Reference: [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
