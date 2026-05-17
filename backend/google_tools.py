import base64
import os
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# Comma-separated fallback recipients when action says "email everyone/team"
TEAM_EMAIL = os.getenv("TEAM_EMAIL", "")


def _creds() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def get_calendar_events(days: int = 1) -> str:
    service = build("calendar", "v3", credentials=_creds())
    now = datetime.now(timezone.utc)
    time_max = (now + timedelta(days=days)).isoformat()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = result.get("items", [])
    if not events:
        return "Nothing on the calendar."
    lines = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        lines.append(f"• {e['summary']} — {start}")
    return "\n".join(lines)


def create_calendar_event(
    title: str, start_iso: str, end_iso: str, description: str = ""
) -> str:
    service = build("calendar", "v3", credentials=_creds())
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": end_iso, "timeZone": "America/Los_Angeles"},
    }
    result = service.events().insert(calendarId="primary", body=event).execute()
    return f"Done: '{result['summary']}' added to calendar — {result['start']['dateTime']}"


def send_email(to: str, subject: str, body: str) -> str:
    # "team" is a shorthand for the TEAM_EMAIL env var
    recipient = TEAM_EMAIL if to.strip().lower() in ("team", "everyone", "") else to
    if not recipient:
        return "No recipient — set TEAM_EMAIL in env vars."
    service = build("gmail", "v1", credentials=_creds())
    msg = MIMEText(body)
    msg["to"] = recipient
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.messages().send(userId="me", body={"raw": raw}).execute()
    return f"Done: email sent to {recipient}"


def read_emails(query: str = "", max_results: int = 5) -> str:
    service = build("gmail", "v1", credentials=_creds())
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query or "is:unread", maxResults=max_results)
        .execute()
    )
    messages = result.get("messages", [])
    if not messages:
        return "No emails found."
    lines = []
    for m in messages:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=m["id"],
                format="metadata",
                metadataHeaders=["Subject", "From"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        lines.append(f"• {headers.get('From', '?')} — {headers.get('Subject', '?')}")
    return "\n".join(lines)
