from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from router import route_message
from context import get_context, add_message
from crm_agent import parse_voice_note
from savings import record_cost, get_stats

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
    context = get_context(req.channel_id)
    result = await route_message(req.message, context)
    add_message(req.channel_id, "user", req.message)
    add_message(req.channel_id, "assistant", result["response"])
    record_cost(req.channel_id, result["cost"])
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
    add_message(req.channel_id, "user", f"[voice note] {req.transcript}")
    record_cost(req.channel_id, 0.5)
    return contact


@app.get("/stats/{channel_id}")
async def stats(channel_id: str):
    return get_stats(channel_id)
