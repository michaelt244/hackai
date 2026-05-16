import json

import httpx

from router import HF_BASE, HF_HEADERS

_EMPTY = {
    "contact": {"name": None, "company": None, "role": None, "context": ""},
    "actionItems": [],
    "sentiment": "neutral",
    "followUpDate": None,
    "suggestedMessage": "",
}

_SYSTEM = (
    "You are a relationship intelligence agent that parses voice notes about meetings.\n\n"
    "INPUT: Raw voice transcription of a user talking about a meeting or contact.\n\n"
    "OUTPUT: Respond ONLY with valid JSON, no other text:\n"
    "{\n"
    '  "contact": {"name": "string or null", "company": "string or null", "role": "string or null", "context": "string"},\n'
    '  "actionItems": ["array of specific next steps"],\n'
    '  "sentiment": "positive | neutral | negative",\n'
    '  "followUpDate": "ISO 8601 date string or null",\n'
    '  "suggestedMessage": "1-2 sentence summary of what to do next"\n'
    "}"
)


async def parse_voice_note(transcript: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            HF_BASE,
            headers=HF_HEADERS,
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                "max_tokens": 512,
            },
        )
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        return json.loads(raw)
    except Exception:
        result = dict(_EMPTY)
        result["contact"] = {**_EMPTY["contact"], "context": raw}
        return result
