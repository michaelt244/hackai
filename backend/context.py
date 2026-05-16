import json
import os
from datetime import date

import httpx

BUTTERBASE_URL = os.environ.get("BUTTERBASE_URL", "")
BUTTERBASE_KEY = os.environ.get("BUTTERBASE_ANON_KEY", "")

MAX_MESSAGES = 20

_windows: dict[str, list[dict]] = {}

_headers = {
    "apikey": BUTTERBASE_KEY,
    "Authorization": f"Bearer {BUTTERBASE_KEY}",
    "Content-Type": "application/json",
}


async def get_context(channel_id: str) -> list[dict]:
    if channel_id in _windows:
        return _windows[channel_id]
    if not BUTTERBASE_URL:
        _windows[channel_id] = []
        return []
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{BUTTERBASE_URL}/channel_summaries",
            headers={**_headers, "Accept": "application/json"},
            params={"channel_id": f"eq.{channel_id}", "order": "summary_date.desc", "limit": "1"},
        )
    rows = resp.json() if resp.status_code == 200 else []
    if rows:
        try:
            _windows[channel_id] = json.loads(rows[0]["summary_text"])
        except Exception:
            _windows[channel_id] = []
    else:
        _windows[channel_id] = []
    return _windows[channel_id]


async def add_message(channel_id: str, role: str, content: str):
    if channel_id not in _windows:
        _windows[channel_id] = []
    _windows[channel_id].append({"role": role, "content": content})
    if len(_windows[channel_id]) > MAX_MESSAGES:
        _windows[channel_id] = _windows[channel_id][-MAX_MESSAGES:]
    if not BUTTERBASE_URL:
        return
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(
            f"{BUTTERBASE_URL}/channel_summaries",
            headers={**_headers, "Prefer": "resolution=merge-duplicates"},
            json={
                "channel_id": channel_id,
                "summary_date": date.today().isoformat(),
                "summary_text": json.dumps(_windows[channel_id]),
            },
        )


def build_context_string(messages: list[dict], limit: int = 5) -> str:
    if not messages:
        return "No prior context for this channel."
    lines = []
    for msg in messages[-limit:]:
        role = "User" if msg["role"] == "user" else "Agent"
        content = msg["content"]
        try:
            data = json.loads(content)
            if "contact" in data:
                name = data["contact"].get("name", "Unknown")
                company = data["contact"].get("company", "")
                ctx = data["contact"].get("context", "")
                lines.append(f"{role}: Logged {name} ({company}) — {ctx}")
            else:
                lines.append(f"{role}: {content[:120]}")
        except Exception:
            lines.append(f"{role}: {content[:120]}")
    return "\n".join(lines)


async def get_augmented_system_prompt(channel_id: str, base_prompt: str) -> str:
    messages = await get_context(channel_id)
    context_summary = build_context_string(messages)
    return f"""{base_prompt}

---
CHANNEL CONTEXT (what this chat already knows):
{context_summary}

Use this context to recognize people, companies, or topics mentioned in previous notes.
Do not ask the user to repeat information already captured above.
"""
