# GroupMind — Your Team's Shared AI Brain

> Your group chat just got smarter. One AI subscription, shared by everyone — ask questions, log meetings by voice, and it remembers everything for the whole team.

GroupMind lives inside your group chat. Ask it anything and it routes your message to the cheapest model that can handle it. Speak a voice note about a meeting and it parses a structured contact card for the whole team. Every response is visible, every cost is tracked, and the group never loses context.

---

## One-Liner

**"The group chat where your team shares one AI brain — smart routing, voice-first contact logging, and memory that never forgets."**

---

## What It Does

- **Smart AI routing** — 3-tier routing sends simple questions to Groq (cheap), complex reasoning to Claude (powerful)
- **Voice-first meeting logs** — hold VoiceOS hotkey, speak a meeting note → HypeScribe transcribes → Claude parses a shared contact card for the whole group
- **Shared context** — the AI remembers your group's conversation across sessions via daily summaries
- **Visible cost** — every response shows `[Claude Haiku · 0.8¢]` so the group sees exactly what it's saving
- **Savings counter** — running total of what the group saved vs. everyone buying individual subscriptions

---

## Architecture

```
Text Message ──────────────────────────────────┐
                                               ▼
Voice Note → HypeScribe → transcript ──► POST /chat or POST /voice-note
                                               │
                                    ┌──────────┴──────────┐
                                    │      AI Router       │
                                    │  (classify intent)   │
                                    └──────────┬──────────┘
                                               │
                          ┌────────────────────┼─────────────────────┐
                          ▼                    ▼                      ▼
                   Groq / Llama          Claude Haiku           Claude Sonnet
                 (simple/casual)       (summaries/medium)    (code/reasoning)
                          │
                   Context Manager
                   ├── active window: last 20 msgs (in-memory per channel)
                   └── daily summaries → Butterbase (Postgres)

Voice note path only:
  Claude CRM Agent → structured contact card → Butterbase contacts table
                                             → posted to GetStream as activity
```

---

## Routing Tiers

| Tier | Model | Triggers | Cost |
|------|-------|----------|------|
| 1 | Groq Llama 3.1 8B | Simple facts, casual chat, quick Q&A | ~$0.001 |
| 2 | Claude Haiku | Summaries, moderate reasoning, lists | ~$0.008 |
| 3 | Claude Sonnet | Code, deep reasoning, complex analysis | ~$0.025 |

---

## CRM Agent — Claude System Prompt

When a voice note is detected, Claude receives the transcript and returns:

```json
{
  "contact": {
    "name": "string",
    "company": "string",
    "role": "string",
    "context": "string"
  },
  "actionItems": ["array of next steps"],
  "sentiment": "positive | neutral | negative",
  "followUpDate": "ISO 8601 or null",
  "suggestedMessage": "1-2 sentence conversational summary"
}
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Group chat UI | GetStream React SDK |
| Voice input | VoiceOS (system hotkey) |
| Transcription | HypeScribe API |
| Backend API | Python FastAPI |
| AI routing | Pattern rules + Groq fallback classifier |
| LLM providers | Anthropic Claude API (Haiku + Sonnet) + Groq |
| Database | Butterbase (Postgres) — context summaries + contacts |
| Hosting | Tencent Cloud |

---

## Demo Script (2 min)

**Scene 1 (15s):** "Every team is already sharing Netflix. We built the same thing for AI — smarter, because it lives where your team already talks."

**Scene 2 (30s):** Type a question in the group chat → response appears with `[Groq · 0.1¢]` badge → ask something complex → response switches to `[Claude Sonnet · 2.4¢]` — the routing is visible and happening live.

**Scene 3 (45s):** Hold VoiceOS hotkey → speak: *"Met Sarah from Acme, their CTO, wants a demo next Thursday, very interested"* → transcription appears → agent card drops into chat: **Sarah | Acme | CTO | Demo Thu** → whole group sees it instantly.

**Scene 4 (30s):** Show savings counter: *"This group has saved $14.20 this session vs. individual subscriptions."* — *"One brain. Shared by everyone. Zero keyboards required."*

---

## Work Split

### Michael — AI Router + Database (`backend/router.py`, `backend/db.py`, `backend/savings.py`)
- [ ] `POST /chat` — main endpoint, calls router, returns response + model + cost
- [ ] `POST /voice-note` — receives transcript, calls CRM agent, returns contact card
- [ ] AI Router — keyword patterns + Groq fallback to classify tier 1/2/3
- [ ] CRM Agent — Claude prompt to parse voice transcript → structured contact JSON
- [ ] Butterbase DB client — contacts table + savings table
- [ ] Savings tracker — per-channel cost accumulation → `GET /stats/{channel_id}`

### Teammate 1 — Context Manager (`backend/context.py`)
- [ ] In-memory active window — `{channel_id: [last 20 messages]}` dict
- [ ] Auto-summarize — when window exceeds ~3k tokens, call Groq to summarize
- [ ] Butterbase write — store daily summary to `channel_summaries` table
- [ ] Butterbase read — on new session, load latest summary as system context
- [ ] Expose `get_context(channel_id)` and `add_message(channel_id, role, content)`

### Teammates 2 & 3 — Frontend + Messaging
- [ ] GetStream group chat UI (React)
- [ ] VoiceOS hotkey listener (`useVoiceOS.ts`)
- [ ] HypeScribe transcription wired to `POST /voice-note`
- [ ] Response badge component (`[Model · cost]`)
- [ ] Contact card component (AgentResponse)
- [ ] Savings counter display
- [ ] Wire all GetStream events → backend `/chat` and `/voice-note`

---

## Build Order (8-hour Sprint)

| Hour | Michael | Teammate 1 | Teammates 2 & 3 |
|------|---------|------------|-----------------|
| 1 | FastAPI scaffold + mock `/chat` response | Context window dict + `get_context` | GetStream chat UI up |
| 2 | AI router 3 tiers working | Auto-summarize trigger | VoiceOS hotkey working |
| 3 | CRM agent (Claude parsing) | Butterbase read/write for summaries | HypeScribe → `/voice-note` wired |
| 4 | Butterbase contacts + savings tables | Integrate context into `/chat` flow | Contact card component |
| 5 | `/stats` endpoint + savings tracker | End-to-end context test | Savings counter UI |
| 6 | Full backend integration test | Bug fixes | Response badges + polish |
| 7 | End-to-end test with frontend | End-to-end test with frontend | End-to-end test |
| 8 | Demo prep + bug fixes | Demo prep | Demo prep + record video |

---

## Sponsor Integration

| Sponsor | Role | Required? |
|---------|------|-----------|
| GetStream | Group chat UI + real-time activity feed | Yes — Sprint Track |
| VoiceOS | Voice input hotkey | Yes — voice feature |
| HypeScribe | Real-time transcription | Yes — voice feature |
| Tencent Cloud | Hosting backend | Yes — Sprint/Endurance |
| Butterbase | Postgres for context + contacts | Yes — persistence |
| Anthropic Claude | Routing (Haiku/Sonnet) + CRM agent | Yes — core AI |
| Groq | Cheap tier-1 routing + classifier | Yes — cost savings story |

---

## File Structure

```
groupmind/
├── backend/
│   ├── main.py                  # FastAPI app, routes
│   ├── router.py                # AI routing logic
│   ├── context.py               # Context manager
│   ├── crm_agent.py             # Claude CRM parser
│   ├── savings.py               # Cost tracking
│   └── db.py                    # Butterbase client
│
├── frontend/
│   ├── components/
│   │   ├── ChatUI.tsx           # GetStream wrapper
│   │   ├── VoiceInput.tsx       # VoiceOS hotkey
│   │   ├── AgentResponse.tsx    # Contact card
│   │   └── SavingsCounter.tsx
│   ├── hooks/
│   │   ├── useVoiceOS.ts
│   │   ├── useGetStream.ts
│   │   └── useAgent.ts
│   └── pages/
│       └── chat.tsx
│
├── .env.example
├── requirements.txt
├── package.json
└── README.md
```

---

## Setup

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env
# Fill: ANTHROPIC_API_KEY, GROQ_API_KEY, BUTTERBASE_URL
uvicorn backend.main:app --reload

# Frontend
npm install
npm run dev
```

---

## Hackathon

Built at **Hack-A-Stack 2026** — Santa Clara University
Tracks: GetStream Sprint Track + Endurance Track
