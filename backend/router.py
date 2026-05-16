import json
import os
import re
from dataclasses import dataclass
from typing import Literal

import httpx

HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_BASE = "https://router.huggingface.co/featherless-ai/v1/chat/completions"
HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json",
}

Intent = Literal["casual", "design", "transcribe", "cleanup", "complex"]

FALLBACK_TOKEN_THRESHOLD = 5


@dataclass
class ModelConfig:
    model_id: str
    alias: str
    max_tokens: int


CLASSIFIER = ModelConfig(
    model_id="Qwen/Qwen2.5-1.5B-Instruct",
    alias="classifier",
    max_tokens=16,
)

WORKER_CASUAL = ModelConfig(
    model_id="Qwen/Qwen2.5-1.5B-Instruct",
    alias="qwen/casual",
    max_tokens=512,
)

WORKER_DESIGN = ModelConfig(
    model_id="Qwen/Qwen2.5-7B-Instruct",
    alias="qwen/design",
    max_tokens=1024,
)

WORKER_TRANSCRIBE = ModelConfig(
    model_id="mistralai/Mistral-7B-Instruct-v0.2",
    alias="mistral/transcribe",
    max_tokens=1024,
)

WORKER_CLEANUP = ModelConfig(
    model_id="google/gemma-2-9b-it",
    alias="gemma/cleanup",
    max_tokens=1024,
)

WORKER_COMPLEX = ModelConfig(
    model_id="Qwen/Qwen2.5-14B-Instruct",
    alias="qwen/complex",
    max_tokens=2048,
)

_INTENT_MAP: dict[Intent, ModelConfig] = {
    "casual": WORKER_CASUAL,
    "design": WORKER_DESIGN,
    "transcribe": WORKER_TRANSCRIBE,
    "cleanup": WORKER_CLEANUP,
    "complex": WORKER_COMPLEX,
}

_SYSTEM_PROMPTS: dict[Intent, str] = {
    "casual": "You are a helpful assistant in a group chat. Be friendly and concise.",
    "design": (
        "You are a design expert in a group chat. Give clear, actionable design feedback. "
        "Focus on UI/UX, visual hierarchy, color, typography, and layout. Be specific."
    ),
    "transcribe": (
        "You are a meeting assistant. Summarize clearly: key decisions, action items (who/what/when), "
        "and follow-ups. Use bullet points. Be concise."
    ),
    "cleanup": (
        "You are an editor. Rewrite or clean up the text for clarity, tone, and grammar. "
        "Preserve the original meaning. Return only the improved version."
    ),
    "complex": "You are a helpful AI assistant in a group chat. Be thorough and accurate.",
}

_CLASSIFIER_SYSTEM = (
    "Classify this group chat message. Pick exactly one label from this list:\n"
    "casual, design, transcribe, cleanup, complex\n\n"
    "casual    = hi, hello, thanks, yes, no, short replies, small talk\n"
    "design    = colors, UI, layout, fonts, mockup, figma, brand, visual feedback\n"
    "transcribe = summarize a meeting, voice note, call recap, action items\n"
    "cleanup   = rewrite, fix grammar, improve tone, edit text\n"
    "complex   = everything else\n\n"
    'Reply with ONLY this JSON and nothing else: {"intent": "casual"} or {"intent": "design"} etc.'
)


_CASUAL_RE = re.compile(
    r"^\s*(hi|hey|hello|thanks|thank you|ty|yes|no|ok|okay|sure|got it|sounds good|lol|haha|yep|nope)[\s!?.]*$",
    re.IGNORECASE,
)
# Require an action verb before the content keyword to avoid false positives
# e.g. "fix this", "rewrite that", "clean up my email" — not "the icon on my shirt"
_CLEANUP_RE = re.compile(
    r"\b(fix|clean up|rewrite|rephrase|improve|edit|proofread|make.{0,10}(formal|professional)|polish)\b.{0,60}\b(this|that|sentence|email|message|text|paragraph|copy)\b",
    re.IGNORECASE,
)
_TRANSCRIBE_RE = re.compile(
    r"\b(summarize|summary|meeting notes|recap|action items|call notes|voice note|met with|talked to|agreed to)\b",
    re.IGNORECASE,
)
_DESIGN_RE = re.compile(
    r"\b(figma|mockup|wireframe|typography|sidebar|padding|margin|ui|ux|spacing|brand|logo)\b"
    r"|\b(color|colour|font|layout|design|button|icon)\b.{0,40}\b(app|site|page|component|screen|ui|ux|brand)\b",
    re.IGNORECASE,
)


def _keyword_intent(message: str) -> Intent | None:
    if _CASUAL_RE.match(message):
        return "casual"
    if _CLEANUP_RE.search(message):
        return "cleanup"
    if _TRANSCRIBE_RE.search(message):
        return "transcribe"
    if _DESIGN_RE.search(message):
        return "design"
    return None


async def _classify_intent(message: str) -> Intent:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                HF_BASE,
                headers=HF_HEADERS,
                json={
                    "model": CLASSIFIER.model_id,
                    "messages": [
                        {"role": "system", "content": _CLASSIFIER_SYSTEM},
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": CLASSIFIER.max_tokens,
                },
            )
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(raw)
            intent = parsed.get("intent", "complex")
            return intent if intent in _INTENT_MAP else "complex"
    except Exception:
        return "complex"


async def _call_model(
    worker: ModelConfig, system_prompt: str, message: str, context: list[dict]
) -> tuple[str, int]:
    messages = [{"role": "system", "content": system_prompt}] + context + [{"role": "user", "content": message}]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            HF_BASE,
            headers=HF_HEADERS,
            json={"model": worker.model_id, "messages": messages, "max_tokens": worker.max_tokens},
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("completion_tokens", len(content.split()))
        return content, tokens


async def route_message(message: str, context: list[dict]) -> dict:
    intent: Intent = _keyword_intent(message) or await _classify_intent(message)
    worker = _INTENT_MAP[intent]
    system_prompt = _SYSTEM_PROMPTS[intent]

    response, completion_tokens = await _call_model(worker, system_prompt, message, context)

    # Fallback: escalate to complex if response too short
    if completion_tokens < FALLBACK_TOKEN_THRESHOLD and worker != WORKER_COMPLEX:
        augmented = f"{message}\n\n[partial answer: {response}]"
        response, completion_tokens = await _call_model(
            WORKER_COMPLEX, _SYSTEM_PROMPTS["complex"], augmented, context
        )
        worker = WORKER_COMPLEX
        intent = "complex"

    return {
        "response": response,
        "model": worker.alias,
        "intent": intent,
        "cost": 0.0,
    }
