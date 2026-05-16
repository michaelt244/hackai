# TEAMMATE 1 — owns this file
# Implement: get_context(channel_id), add_message(channel_id, role, content)
# See README for full spec.

import os
import json

_windows: dict[str, list[dict]] = {}
MAX_MESSAGES = 20

# Persistence layer
CONTEXT_DIR = "chat_contexts"
os.makedirs(CONTEXT_DIR, exist_ok=True)


def _get_context_file(channel_id: str) -> str:
    return os.path.join(CONTEXT_DIR, f"{channel_id}.json")


def _load_from_disk(channel_id: str) -> list[dict]:
    file_path = _get_context_file(channel_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_to_disk(channel_id: str, messages: list[dict]):
    with open(_get_context_file(channel_id), "w") as f:
        json.dump(messages, f, indent=2)


def get_context(channel_id: str) -> list[dict]:
    if channel_id not in _windows:
        _windows[channel_id] = _load_from_disk(channel_id)
    return _windows.get(channel_id, [])


def add_message(channel_id: str, role: str, content: str):
    if channel_id not in _windows:
        _windows[channel_id] = []
    _windows[channel_id].append({"role": role, "content": content})
    if len(_windows[channel_id]) > MAX_MESSAGES:
        _windows[channel_id] = _windows[channel_id][-MAX_MESSAGES:]
    _save_to_disk(channel_id, _windows[channel_id])


def build_context_string(channel_id: str, limit: int = 5) -> str:
    """Summarize recent messages into plain text for the system prompt."""
    messages = get_context(channel_id)
    if not messages:
        return "No prior context for this channel."

    lines = []
    for msg in messages[-limit:]:
        role = "User" if msg["role"] == "user" else "Agent"
        content = msg["content"]
        # If agent JSON, extract readable summary
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
    """Inject channel memory into the system prompt."""
    context_summary = build_context_string(channel_id)
    return f"""{base_prompt}

---
CHANNEL CONTEXT (what this chat already knows):
{context_summary}

Use this context to recognize people, companies, or topics mentioned in previous notes.
Do not ask the user to repeat information already captured above.
"""
