import os
import traceback
import uuid
from collections import OrderedDict, deque

import httpx
from fastapi import APIRouter, Request

from router import HF_BASE, HF_HEADERS, WORKER_COMPLEX

router = APIRouter()

BLUEBUBBLES_URL = os.getenv("BLUEBUBBLES_URL", "").replace('"', "").strip().rstrip("/")
BLUEBUBBLES_PASSWORD = os.getenv("BLUEBUBBLES_PASSWORD", "")
# May arrive as the send-side 'any;+;<id>' form, or malformed with stray quotes.
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

        # Match the bare identifier so 'iMessage;+;<id>' (inbound) and
        # 'any;+;<id>' (send form) compare equal.
        if DEMO_CHAT_ID and DEMO_CHAT_ID not in chat_guid.lower():
            print(
                f"[penguin] skip: chat {_chat_id(chat_guid)!r} "
                f"!= demo {DEMO_CHAT_ID!r}"
            )
            return {"ok": True}

        if not _is_new(guid):
            print(f"[penguin] skip: duplicate event {guid}")
            return {"ok": True}

        # All messages go into context, mention or not
        _add(chat_guid, "user", f"{sender}: {text}")

        if "@penguin" not in text.lower():
            print("[penguin] skip: no @penguin mention")
            return {"ok": True}

        clean = text.lower().replace("@penguin", "").strip()
        print(f"[penguin] running agent for: {clean!r}")
        reply = await _call_penguin(clean, _get(chat_guid))
        print(f"[penguin] agent reply: {reply!r}")

        _add(chat_guid, "assistant", reply)
        await _send(reply)

    except Exception as e:
        print(f"[penguin] webhook error: {e}")
        traceback.print_exc()

    return {"ok": True}
