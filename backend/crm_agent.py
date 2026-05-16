import json
import os

import httpx

HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_BASE = "https://router.huggingface.co/featherless-ai/v1/chat/completions"
HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json",
}

_SYSTEM_PROMPT = """You are a relationship intelligence agent that parses voice notes about meetings.

INPUT: Raw voice transcription of a user talking about a meeting or contact.

OUTPUT: Respond ONLY with valid JSON, no other text:
{
  "contact": {
    "name": "string or null",
    "company": "string or null",
    "role": "string or null",
    "context": "string — what happened, any details"
  },
  "actionItems": ["array of specific next steps"],
  "sentiment": "positive | neutral | negative",
  "followUpDate": "ISO 8601 date string or null",
  "suggestedMessage": "1-2 sentence summary of what to do next"
}"""

_EMPTY = {
    "contact": {"name": None, "company": None, "role": None, "context": ""},
    "actionItems": [],
    "sentiment": "neutral",
    "followUpDate": None,
    "suggestedMessage": "",
}


async def parse_voice_note(transcript: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            HF_BASE,
            headers=HF_HEADERS,
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": transcript},
                ],
                "max_tokens": 512,
            },
        )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            result = _EMPTY.copy()
            result["contact"] = {**_EMPTY["contact"], "context": raw}
            return result
