# Penguin: Your Group Chat's AI Brain

> One AI, shared by the whole group. It listens, routes every message to the right model, takes real actions, and remembers everything across sessions.

Penguin lives inside your existing iMessage group chat. Mention `@penguin` and it responds, with full context of what the group has been talking about. Talk to it with a voice note and it transcribes and acts on it. Drop an image and it can pull it back later for feedback. No new app to download, it works where you already talk.

---

## One-Liner

**"The group chat where your team shares one AI brain: voice-first input, smart model routing, real actions, and memory that never forgets."**

---

## What It Does

- **Voice-first input.** Send a voice note and **VoiceOS** transcribes what you said into text Penguin can act on.
- **Lives in iMessage.** `@penguin` in any iMessage group, bridged via BlueBubbles. No extra app.
- **Smart model routing.** A keyword pre-filter plus a small Qwen classifier sends each message to the cheapest model that can handle it.
- **Takes action.** Ask it to check the calendar, schedule an event, or send an email, and it does it.
- **Image memory.** Photos dropped in the chat are stored in **Tencent Cloud Object Storage** so Penguin can fetch them later for design feedback.
- **Remembers.** A rolling per-channel context plus a contact CRM, persisted in **Butterbase**, so Penguin knows who said what across days.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                             │
│                                                                 │
│   VoiceOS ──speak──► iMessage Group Chat                        │
│                             │  "@penguin action: ..."           │
└─────────────────────────────┼───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BRIDGE LAYER                             │
│                                                                 │
│   Mac + BlueBubbles ◄── AppleScript ──► iMessage                │
│            │                                                    │
│     Cloudflare Tunnel                                           │
└─────────────────────────────┼───────────────────────────────────┘
                              │ POST /webhook
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAILWAY / FastAPI                            │
│                                                                 │
│   Adal agent loop: dedup ► chat filter ► @penguin? ► route      │
│                                                                 │
│      action: ?                                                  │
│   ┌──────────┴───────────┐                                      │
│  Yes                     No                                     │
│   │                      │                                      │
│   ▼                      ▼                                      │
│  Google APIs       Intent Router                                │
│  • Calendar        1. keyword check                             │
│  • Gmail           2. Qwen 1.5B classifier                      │
│                    casual → Qwen 1.5B                           │
│                    design → Qwen 7B                             │
│                    transcribe → Mistral 7B                      │
│                    cleanup → Gemma 9B                            │
│                    complex → Qwen 14B                           │
│                                                                 │
│   Tencent Cloud Object Storage ── images dropped in chat        │
│   Butterbase ──────── rolling context + CRM per channel         │
└─────────────────────────────┼───────────────────────────────────┘
                              │ reply
                              ▼
                 BlueBubbles → iMessage Chat
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

The keyword pre-filter runs first at zero latency. It falls back to the Qwen 1.5B classifier. If a worker returns under 5 tokens, it escalates to Qwen 14B.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send a message, get a routed AI response |
| POST | `/voice-note` | Parse a voice transcript into a CRM contact |
| GET | `/contacts/{channel_id}` | List CRM contacts for a channel |
| GET | `/stats/{channel_id}` | Cost savings stats |
| POST | `/warmup` | Pre-warm all models before a demo |
| POST | `/webhook` | BlueBubbles iMessage webhook |
| GET | `/health` | Health check |
| POST | `/v1/chat/completions` | OpenAI-compatible endpoint |

---

## Stack

- **Backend**: FastAPI plus uvicorn (Python 3.12)
- **Agent framework**: Adal (AdalFlow), runs the `@penguin` loop and tool dispatch
- **Voice input**: VoiceOS, transcribes spoken messages into text
- **Models**: HuggingFace featherless-ai (Qwen 1.5B / 7B / 14B, Mistral 7B, Gemma 2 9B)
- **Image storage**: Tencent Cloud Object Storage (S3-compatible)
- **Database**: Butterbase, rolling channel context plus contact CRM
- **iMessage**: BlueBubbles plus Cloudflare Tunnel
- **Actions**: Google Calendar API plus Gmail API
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

Run `backend/schema.sql` in the Butterbase dashboard SQL editor once to create the tables:

- `channel_usage`: per-message cost tracking
- `channel_summaries`: daily rolling context per channel
- `contacts`: CRM contact cards from voice notes
