import json
import os
import traceback
import uuid
from collections import OrderedDict, deque
from datetime import datetime

import httpx
from fastapi import APIRouter, Request

import google_tools
from router import HF_BASE, HF_HEADERS, WORKER_COMPLEX

router = APIRouter()

BLUEBUBBLES_URL = os.getenv("BLUEBUBBLES_URL", "").replace('"', "").strip().rstrip("/")
BLUEBUBBLES_PASSWORD = os.getenv("BLUEBUBBLES_PASSWORD", "")
DEMO_CHAT_GUID = (
    os.getenv("DEMO_CHAT_GUID", "any;+;6d23dfa9618e444e81cc9220769d5c4d")
    .replace('"', "")
    .strip()
)

SYSTEM_PROMPT = (
    "You are Penguin, an AI agent in an iMessage group chat. "
    "You are dry, deadpan, and slightly sarcastic. Speak in 1-3 sentences. "
    "You have opinions. Never say 'As an AI'. No markdown — iMessage doesn't render it. "
    "Just talk like a person who happens to know a lot."
)

_ACTION_SYSTEM = """\
You are an action parser for a group chat AI. Parse the user's request into JSON.
Return ONLY valid JSON — no explanation, no markdown fences.

Current datetime: {now} (Pacific Time)

Supported actions:
  get_calendar  — check upcoming events
    params: {{"days": <int, default 1>}}

  create_event  — add a calendar event
    params: {{"title": "...", "start_iso": "YYYY-MM-DDTHH:MM:SS", "end_iso": "YYYY-MM-DDTHH:MM:SS", "description": ""}}

  send_email    — send an email
    params: {{"to": "<email address or 'team'>", "subject": "...", "body": "..."}}

  read_email    — read recent/filtered emails
    params: {{"query": "<gmail search query>", "max_results": 5}}

Examples:
  "what's on the calendar tomorrow"       → {{"action":"get_calendar","params":{{"days":2}}}}
  "schedule team meeting Friday 3pm"      → {{"action":"create_event","params":{{"title":"Team Meeting","start_iso":"2026-05-22T15:00:00","end_iso":"2026-05-22T16:00:00","description":""}}}}
  "email everyone that demo is at 5pm"   → {{"action":"send_email","params":{{"to":"team","subject":"Demo at 5pm","body":"Hey team, the demo is at 5pm today."}}}}
  "any unread emails"                    → {{"action":"read_email","params":{{"query":"is:unread","max_results":5}}}}
"""

# LRU dedup set — BlueBubbles fires the same event 2-3x per message
_seen: OrderedDict[str, None] = OrderedDict()
_MAX_SEEN = 200

# Rolling context per chat
_ctx: dict[str, deque] = {}
_MAX_CTX = 20


def _chat_id(guid: str) -> str:
    """Bare chat identifier from a BlueBubbles GUID.

    Incoming webhooks deliver 'iMessage;+;<id>'; the send API accepts the
    'any;+;<id>' convenience form. Comparing only <id> makes the service
    prefix irrelevant.
    """
    return guid.replace('"', "").strip().rsplit(";", 1)[-1].lower()


DEMO_CHAT_ID = _chat_id(DEMO_CHAT_GUID)


def _is_new(guid: str) -> bool:
    if guid in _seen:
        return False
    if len(_seen) >= _MAX_SEEN:
        _seen.popitem(last=False)
    _seen[guid] = None
    return True


def _add(chat_guid: str, role: str, content: str):
    if chat_guid not in _ctx:
        _ctx[chat_guid] = deque(maxlen=_MAX_CTX)
    _ctx[chat_guid].append({"role": role, "content": content})


def _get(chat_guid: str) -> list[dict]:
    return list(_ctx.get(chat_guid, []))


async def _call_penguin(message: str, context: list[dict]) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + context + [{"role": "user", "content": message}]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            HF_BASE,
            headers=HF_HEADERS,
            json={"model": WORKER_COMPLEX.model_id, "messages": messages, "max_tokens": 256},
        )
    return resp.json()["choices"][0]["message"]["content"].strip()


async def _parse_action(action_text: str) -> dict | None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M %A")
    system = _ACTION_SYSTEM.format(now=now)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            HF_BASE,
            headers=HF_HEADERS,
            json={
                "model": WORKER_COMPLEX.model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": action_text},
                ],
                "max_tokens": 256,
            },
        )
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


async def _wrap_in_penguin_voice(raw_result: str, action_text: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"You just completed this action: '{action_text}'\n"
                f"Result: {raw_result}\n\n"
                "Report the result to the group chat in your voice. "
                "One or two sentences max. If it failed, say so plainly."
            ),
        },
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            HF_BASE,
            headers=HF_HEADERS,
            json={"model": WORKER_COMPLEX.model_id, "messages": messages, "max_tokens": 128},
        )
    return resp.json()["choices"][0]["message"]["content"].strip()


async def _handle_action(action_text: str) -> str:
    if not action_text:
        return "Action what? Try: 'action: what's on the calendar' or 'action: schedule meeting Friday 3pm'"

    print(f"[penguin] parsing action: {action_text!r}")
    try:
        parsed = await _parse_action(action_text)
    except Exception as e:
        print(f"[penguin] action parse error: {e}")
        return "Couldn't figure out what you wanted. Try being more specific — 'action: schedule team meeting Friday 3pm' or 'action: email everyone about the demo'"

    action = parsed.get("action", "")
    params = parsed.get("params", {})
    print(f"[penguin] action={action} params={params}")

    required = {
        "create_event": ["title", "start_iso", "end_iso"],
        "send_email": ["to", "subject", "body"],
    }
    missing = [k for k in required.get(action, []) if not params.get(k)]
    if missing:
        return f"Missing info to {action}: {', '.join(missing)}. Can you be more specific?"

    try:
        if action == "get_calendar":
            raw = google_tools.get_calendar_events(**params)
        elif action == "create_event":
            raw = google_tools.create_calendar_event(**params)
        elif action == "send_email":
            raw = google_tools.send_email(**params)
        elif action == "read_email":
            raw = google_tools.read_emails(**params)
        else:
            return f"I don't know how to '{action}'. Supported: get_calendar, create_event, send_email, read_email."
    except Exception as e:
        print(f"[penguin] action execute error: {e}")
        traceback.print_exc()
        return f"That didn't work: {e}"

    print(f"[penguin] raw action result: {raw!r}")
    try:
        return await _wrap_in_penguin_voice(raw, action_text)
    except Exception:
        return raw


async def _send(text: str):
    if not text:
        print("[penguin] send skipped: empty reply")
        return
    if not BLUEBUBBLES_URL:
        print("[penguin] send skipped: BLUEBUBBLES_URL not set")
        return
    url = f"{BLUEBUBBLES_URL}/api/v1/message/text"
    payload = {
        "chatGuid": DEMO_CHAT_GUID,
        "tempGuid": f"temp-{uuid.uuid4()}",
        "message": text,
        "method": "apple-script",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, params={"password": BLUEBUBBLES_PASSWORD}, json=payload)
            print(
                f"[penguin] sent to {url} chatGuid={DEMO_CHAT_GUID!r} "
                f"-> {resp.status_code} {resp.text[:300]}"
            )
        except Exception as e:
            print(f"[penguin] send error: {e}")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
        etype = body.get("type")
        print(f"[penguin] webhook received: type={etype}")

        if etype != "new-message":
            return {"ok": True}

        data = body.get("data", {})
        guid = data.get("guid", "")
        text = (data.get("text") or "").strip()
        is_from_me = data.get("isFromMe", False)
        chats = data.get("chats", [])
        sender = (data.get("handle") or {}).get("address", "unknown")
        chat_guid = chats[0].get("guid", "") if chats else ""

        print(
            f"[penguin] msg from={sender} chat={chat_guid!r} "
            f"fromMe={is_from_me} text={text!r}"
        )

        if is_from_me:
            print("[penguin] skip: message is from me")
            return {"ok": True}

        if DEMO_CHAT_ID and DEMO_CHAT_ID not in chat_guid.lower():
            print(
                f"[penguin] skip: chat {_chat_id(chat_guid)!r} "
                f"!= demo {DEMO_CHAT_ID!r}"
            )
            return {"ok": True}

        if not _is_new(guid):
            print(f"[penguin] skip: duplicate event {guid}")
            return {"ok": True}

        _add(chat_guid, "user", f"{sender}: {text}")

        if "@penguin" not in text.lower():
            print("[penguin] skip: no @penguin mention")
            return {"ok": True}

        clean = text.strip()
        for prefix in ("@penguin", "@Penguin"):
            clean = clean.replace(prefix, "")
        clean = clean.strip()

        if clean.lower().startswith("action:"):
            action_text = clean[len("action:"):].strip()
            print(f"[penguin] action mode: {action_text!r}")
            result = await _handle_action(action_text)
            print(f"[penguin] action result: {result!r}")
            await _send(result)
        else:
            print(f"[penguin] running agent for: {clean!r}")
            reply = await _call_penguin(clean, _get(chat_guid))
            print(f"[penguin] agent reply: {reply!r}")
            _add(chat_guid, "assistant", reply)
            await _send(reply)

    except Exception as e:
        print(f"[penguin] webhook error: {e}")
        traceback.print_exc()

    return {"ok": True}
