# Penguin — Your Group Chat's AI Brain

> One AI, shared by the whole group. Routes every message to the right model, logs meetings by voice, and remembers everything across sessions.

Penguin lives inside your iMessage group chat (via BlueBubbles) and your web chat (via Bubble). Mention `@penguin` and it responds. Speak a voice note and it logs a structured contact card to your team's shared CRM. Every response shows which model handled it and what it cost.

---

## One-Liner

**"The group chat where your team shares one AI brain — smart routing, voice-first contact logging, and memory that never forgets."**

---

## What It Does

- **Smart AI routing** — keyword pre-filter + Qwen classifier routes each message to the cheapest capable model
- **iMessage integration** — `@penguin` in any iMessage group via BlueBubbles webhook
- **Voice-first CRM** — speak a meeting note → Qwen parses a structured contact card saved to Butterbase
- **Shared context** — rolling 20-message window per channel, persisted daily to Butterbase
- **Savings counter** — running total of what the group saved vs. everyone buying individual subscriptions

---

## Architecture

```
iMessage → BlueBubbles → POST /webhook → Penguin agent → BlueBubbles reply
Web chat → Bubble     → POST /chat    → Intent router → Response

POST /voice-note → Qwen CRM parser → Butterbase contacts table
GET  /contacts/{channel_id}        → Contact cards for frontend
GET  /stats/{channel_id}           → Cost savings display
```

---

## Intent Routing

| Intent | Trigger | Model |
|--------|---------|-------|
| casual | hi, thanks, yes/no | Qwen 1.5B |
| design | figma, UI, layout, colors | Qwen 7B |
| transcribe | summarize meeting, action items | Mistral 7B |
| cleanup | rewrite, fix grammar, edit this | Gemma 9B |
| complex | everything else | Qwen 14B |

Keyword pre-filter runs first (zero latency). Falls back to Qwen 1.5B classifier. If the worker returns < 5 tokens, escalates to Qwen 14B.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send a message, get routed AI response |
| POST | `/voice-note` | Parse voice transcript → CRM contact |
| GET | `/contacts/{channel_id}` | List CRM contacts for a channel |
| GET | `/stats/{channel_id}` | Cost savings stats |
| POST | `/warmup` | Pre-warm all models before demo |
| POST | `/webhook` | BlueBubbles iMessage webhook |
| GET | `/health` | Health check |
| POST | `/v1/chat/completions` | OpenAI-compatible endpoint (TRTC) |

---

## Stack

- **Backend**: FastAPI + uvicorn (Python 3.12)
- **Models**: HuggingFace featherless-ai (Qwen, Mistral, Gemma)
- **Persistence**: Butterbase (PostgREST-compatible)
- **iMessage**: BlueBubbles + Cloudflare tunnel
- **Frontend**: Bubble (REST via API Connector)
- **Deploy**: Railway

---

## Environment Variables

```
HF_TOKEN               # HuggingFace token
BUTTERBASE_URL         # https://api.butterbase.ai/v1/app_...
BUTTERBASE_ANON_KEY    # bb_sk_...
BLUEBUBBLES_URL        # Cloudflare tunnel URL to Mac running BlueBubbles
BLUEBUBBLES_PASSWORD   # BlueBubbles server password
DEMO_CHAT_GUID         # iMessage group GUID
```

---

## Running Locally

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env  # fill in keys
cd backend && uvicorn main:app --port 8001 --reload
```

---

## Database Schema

Run `backend/schema.sql` in the Butterbase dashboard SQL editor once to create tables:
- `channel_usage` — per-message cost tracking
- `channel_summaries` — daily rolling context per channel
- `contacts` — CRM contact cards from voice notes
