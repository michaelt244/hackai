import os

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from context import add_message, get_context
from crm_agent import parse_voice_note
from router import HF_BASE, HF_HEADERS, _INTENT_MAP, route_message
from savings import get_stats, record_cost, save_contact

BUTTERBASE_URL = os.environ.get("BUTTERBASE_URL", "")
BUTTERBASE_KEY = os.environ.get("BUTTERBASE_ANON_KEY", "")
_BB_HEADERS = {
    "apikey": BUTTERBASE_KEY,
    "Authorization": f"Bearer {BUTTERBASE_KEY}",
    "Accept": "application/json",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    channel_id: str
    user_id: str
    message: str


class VoiceNoteRequest(BaseModel):
    channel_id: str
    user_id: str
    transcript: str


@app.post("/chat")
async def chat(req: ChatRequest):
    context = await get_context(req.channel_id)
    result = await route_message(req.message, context)
    await add_message(req.channel_id, "user", req.message)
    await add_message(req.channel_id, "assistant", result["response"])
    await record_cost(req.channel_id, result["cost"])
    return {
        "response": result["response"],
        "model": result["model"],
        "intent": result["intent"],
        "cost": result["cost"],
        "badge": f"[{result['model']} · {result['intent']} · {result['cost']:.1f}¢]",
    }


@app.post("/voice-note")
async def voice_note(req: VoiceNoteRequest):
    contact = await parse_voice_note(req.transcript)
    await add_message(req.channel_id, "user", f"[voice note] {req.transcript}")
    await save_contact(req.channel_id, contact)
    await record_cost(req.channel_id, 0.5)
    return contact


@app.get("/stats/{channel_id}")
async def stats(channel_id: str):
    return await get_stats(channel_id)


@app.get("/contacts/{channel_id}")
async def contacts(channel_id: str):
    if not BUTTERBASE_URL:
        return []
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            f"{BUTTERBASE_URL}/contacts",
            headers=_BB_HEADERS,
            params={"channel_id": f"eq.{channel_id}", "order": "created_at.desc"},
        )
    return resp.json() if resp.status_code == 200 else []


@app.post("/warmup")
async def warmup():
    """Pre-warm all worker models to eliminate cold-start latency on first real request."""
    ping = [{"role": "user", "content": "hi"}]
    seen = set()
    results = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for intent, worker in _INTENT_MAP.items():
            if worker.model_id in seen:
                results[intent] = "skipped (shared model)"
                continue
            seen.add(worker.model_id)
            try:
                resp = await client.post(
                    HF_BASE, headers=HF_HEADERS,
                    json={"model": worker.model_id, "messages": ping, "max_tokens": 5},
                )
                results[intent] = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
            except Exception as e:
                results[intent] = str(e)
    return {"warmed": results}


# OpenAI-compatible endpoint for Tencent TRTC Conversational AI
@app.post("/v1/chat/completions")
async def openai_compat(req: dict):
    messages = req.get("messages", [])
    message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    context = [m for m in messages if m["role"] in ("user", "assistant")][:-1]
    result = await route_message(message, context)
    return {
        "id": "chatcmpl-trtc",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result["response"]},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": -1, "completion_tokens": -1, "total_tokens": -1},
    }
