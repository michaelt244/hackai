VOICE-NATIVE CRM — SUBMISSION REFERENCE
ONE-LINER
Folk.app meets VoiceOS — manage all your relationships without touching a keyboard. Speak a contact note, agent parses it, logs it automatically.

TECH STACK (What to Mention)
Voice Input: VoiceOS (system-wide hotkey)
Transcription: HypeScribe API (real-time)
Messaging: GetStream SDK (real-time activity feed)
Agent: Claude API (structured parsing + response generation)
Backend: Node.js / TypeScript
Frontend: React / Next.js
Database: Tencent Cloud (COS + TencentDB PostgreSQL)
Hosting: Tencent Cloud (CVM / SCF serverless)
CORE FEATURES (MVP)
Voice Input — Hold VoiceOS hotkey, speak naturally in chat
Real-Time Transcription — HypeScribe transcribes in <3 seconds
Agent Parsing — Claude extracts: name, company, context, action items, sentiment
Smart Response — Agent generates summary card + suggested next steps
Quick Actions — Set reminder, draft email, view contact (extensible)
Auto-Logging — Contact record created/updated in Tencent Cloud DB
DEMO SCRIPT (Copy for Video)
Scene 1 (15 sec): "Most CRMs force you to stop, open an app, fill out fields. We built Folk for people who never stop moving."

Scene 2 (30 sec): Open GetStream chat → hold VoiceOS hotkey → speak: "Met Alex from TechCorp at the conference, CEO, interested in our platform, wants a demo next Friday" → transcription appears live.

Scene 3 (60 sec): Agent response appears:

Summary card: Alex | TechCorp | CEO | Demo request
Natural message: "Got it. You met Alex (CEO @ TechCorp) who wants a product demo. I'll set a reminder for next Friday. Want me to draft a follow-up email?"
Click [Draft Email] → template appears
Click [Set Reminder] → confirmed
Scene 4 (15 sec): "One voice note. Structured contact. Next steps locked in. No keyboard required."

CLAUDE SYSTEM PROMPT
You are a relationship intelligence agent that parses voice notes about meetings and interactions, then suggests next steps.

INPUT: Raw voice transcription of a user talking about a meeting/contact

OUTPUT: Respond ONLY with valid JSON:

{
  "contact": {
    "name": "string (required if mentioned)",
    "company": "string (optional)",
    "role": "string (optional)",
    "context": "string (what happened, any details)"
  },
  "actionItems": ["array of specific next steps"],
  "sentiment": "positive | neutral | negative",
  "followUpDate": "ISO 8601 date string or null",
  "suggestedMessage": "string (conversational 1-2 sentence summary)"
}

RULES:
- Extract contact info even if incomplete
- Identify specific dates/times for follow-ups
- Flag positive sentiment for partnership/sale signals
- Be conversational in suggestedMessage
- Ask clarifying question if information unclear
FILE STRUCTURE
voice-crm/
├── frontend/
│   ├── components/
│   │   ├── VoiceInput.tsx          (VoiceOS hotkey listener)
│   │   ├── AgentResponse.tsx       (summary card + buttons)
│   │   ├── ChatUI.tsx              (GetStream wrapper)
│   │   └── QuickActions.tsx        (Set reminder, Draft email, etc)
│   ├── hooks/
│   │   ├── useVoiceOS.ts
│   │   ├── useGetStream.ts
│   │   └── useAgent.ts
│   ├── pages/
│   │   ├── chat.tsx               (main interface)
│   │   ├── contacts.tsx
│   │   └── dashboard.tsx
│   └── lib/
│       ├── api.ts
│       └── types.ts
│
├── backend/
│   ├── api/
│   │   ├── voiceOS.ts            (voice input handler)
│   │   ├── transcription.ts       (HypeScribe API)
│   │   ├── agent.ts              (Claude API calls)
│   │   ├── getstream.ts          (GetStream integration)
│   │   └── contacts.ts           (DB CRUD)
│   ├── services/
│   │   ├── agentOrchestrator.ts  (parse → generate → post)
│   │   ├── contactService.ts
│   │   └── reminderService.ts
│   ├── schemas/
│   │   └── contact.schema.ts
│   └── index.ts
│
├── config/
│   ├── tencent.config.ts
│   ├── getstream.config.ts
│   ├── claude.config.ts
│   └── hypescribe.config.ts
│
├── prompts/
│   └── agent.system.prompt.md
│
├── .env.example
├── package.json
└── README.md
JUDGING CRITERIA HITS
✅ Idea Originality — Folk (CRM) + VoiceOS (voice-to-action) = fresh combo, not obvious
✅ Technical Complexity — Multi-API orchestration, real-time transcription, agent parsing
✅ UX & Design — Voice-first means zero friction, natural interaction
✅ Impact Potential — Founders, sales, investors, networkers all solve this problem daily
✅ Presentation — Clear demo, obvious problem → solution
✅ Sponsor Integration — VoiceOS + HypeScribe + GetStream + Tencent Cloud all genuinely used (not forced)
✅ Entrepreneurial Mindset — Scalable (team CRM, integrations, B2B SaaS play)
✅ User Insight — Solves real pain (CRM friction for fast-moving people)

QUICK IMPLEMENTATION ORDER
Wire VoiceOS hotkey listener (useVoiceOS hook)
Add HypeScribe transcription API handler
Test Claude agent parsing with sample notes
Build AgentResponse component (card + 2 buttons)
Integrate GetStream to post responses
Add Tencent Cloud DB for contacts
Record demo
Submit to DevPost by 6pm
SUCCESS CRITERIA
[ ] Speak voice note → appears in chat
[ ] Agent response with summary card appears in <5 sec
[ ] 2-3 quick actions work
[ ] Under 3-min demo
[ ] Clear product vision communicated
[ ] Uses all 4 sponsors genuinely
