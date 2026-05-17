# AI Receptionist — Hackathon Build

## Mission

Paste any local business's Google Maps URL or website URL → in under 5 minutes that business has a live phone number staffed by a voice AI that books appointments, sends email confirmations, and remembers callers when they call back. Sells to SMBs at $49/mo.

Built for the Call My Agent Hackathon (YC SF, May 17 2026, hosted by AgentPhone). Target outcome: 1st place → YC interview.

## The Magic Moment

```
URL in → 90s cinematic onboarding → phone number out → live call works immediately.
```

This is the single demo beat the entire product is structured around. Everything else serves it.

## Stack (Locked — Do Not Substitute)

| Concern | Service |
|---|---|
| Voice + phone + SMS + transcripts + transfer + voicemail | **AgentPhone** (webhook mode, $0.13/min) |
| Voice brain (in-call reasoning + tool calls) | **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) |
| URL → typed business JSON | **Browser Use v3** (`browser-use-sdk`, Pydantic `output_schema`) |
| Per-business knowledge (services, hours, prices) | **Moss** (one index per business) |
| Per-caller memory (preferences, history) | **Supermemory** (container tag `caller_+1XXX`) |
| Email confirmations + reply-driven reschedule/cancel | **AgentMail** (WebSockets, inbox per business) |
| Bookings + calendar | **Cal.com API v2** (one platform-owned account, event types tagged by `business_id`) |
| Optional loader logo | Gemini 2.5 Flash (sponsor only) |
| Database | Postgres + SQLModel (businesses, callers, call_logs) |
| Backend | FastAPI + Python 3.11 + asyncpg |
| Frontend | Next.js 14 (app router) + TypeScript strict + Tailwind + shadcn/ui + Framer Motion |
| Deploy | Railway (continuous from hour 2) |

Eight services on stage. Eight sponsor logos.

## Architecture Principles

1. **AgentPhone webhook mode, not hosted mode.** Hosted has no tool calls. Our FastAPI receives the transcript, routes through Claude Haiku + tools (Moss/Supermemory/Cal.com/AgentMail), streams back NDJSON. Always emit an interim `{"text": "One moment.", "interim": true}` chunk first to avoid the 30s timeout.

2. **Two memory layers, not one.** Moss = the business's brain (loaded once, queried every turn). Supermemory = the caller's relationship (queried at call start, updated after each call). They are not interchangeable.

3. **Cal.com is multi-tenant via metadata.** ONE Cal.com account in our env. At business onboarding, we create per-service event types tagged with `metadata: { business_id }`. Filter by metadata for isolation.

4. **AgentMail uses WebSockets, not webhooks.** One less ngrok dependency. Subscribe to all business inboxes at FastAPI startup (`lifespan`).

5. **Per-business inboxes created on the fly.** At onboarding, call `client.inboxes.create()` and store the `inbox_id` on the business row. Free tier allows 3 → exactly 3 demo businesses.

6. **Browser Use returns validated Pydantic, not raw text.** Define `BusinessInfo` model with `output_schema=BusinessInfo`. No parsing layer.

7. Deploy to Railway continuously from hour 2. Backend + frontend + Postgres all on Railway. PUBLIC_BACKEND_URL is the Railway backend URL — feed it into AgentPhone webhook config. No ngrok in the demo path.

## Hard Conventions

- TypeScript: strict mode, no `any`, no `as unknown as`. Pydantic v2 on the Python side.
- Type hints everywhere. Single responsibility per file.
- All secrets via `.env`, never hardcoded. Never log secrets.
- Async by default in FastAPI (`async def` handlers, `asyncpg`, `AsyncBrowserUse`, `AsyncAgentMail`).
- Errors fail loudly during dev. No silent fallbacks.
- File and function names describe what they do, not how (`book_appointment` not `cal_post_booking`).

## What NOT to Do

- ❌ No demo bypasses. No fake integrations. No mocked tool responses. Every API call is real.
- ❌ No `time.sleep` in the voice path. Streaming or async only.
- ❌ No `requests` library. Use `httpx` for sync, `httpx.AsyncClient` for async.
- ❌ Do not provision real phone numbers, create real inboxes, or run paid Browser Use tasks in smoke tests.
- ❌ Do not store appointments in our Postgres. Cal.com owns bookings. We store `businesses`, `callers`, `call_logs` only.
- ❌ No `requirements.txt`. Use `pyproject.toml`.
- ❌ Do not add libraries not already in the stack table above without asking.

## How to Verify Your Work

Every external integration has a smoke test in `backend/app/tests/smoke.py`. After any change touching a service:

```bash
cd backend && python -m app.tests.smoke
```

All 7 services must print `PASS`. Total runtime under 30 seconds. The smoke test never spends money.

## Cal.com Specifics

- API key prefix: `cal_live_` (live) or `cal_` (test). Live for us.
- Auth: `Authorization: Bearer ${CALCOM_API_KEY}`.
- Required header on most endpoints: `cal-api-version: 2024-08-13`. Without it, requests default to an older version and may 404.
- Base: `https://api.cal.com/v2`.
- Rate limit: 120 req/min — plenty for hackathon.
- Endpoints we use: `GET /me` (smoke), `POST /event-types` (create per-service), `GET /slots` (availability), `POST /bookings` (book), `POST /bookings/{uid}/reschedule`, `POST /bookings/{uid}/cancel`.

## Phase Roadmap

- **Phase 1 (now):** Project skeleton + smoke tests. Verify every API key works. **Do not build the voice loop yet.**
- **Phase 2:** Onboarding pipeline (URL → BusinessInfo → Cal.com event types + Moss index + AgentMail inbox + AgentPhone number).
- **Phase 3:** Voice webhook + Claude tool-call loop + AgentMail WS subscriber.
- **Phase 4:** Frontend polish, demo dashboard, dark/glass UI.
- **Phase 5:** End-to-end rehearsal with 3 SF demo businesses.

If you're not sure which phase you're in, you're in Phase 1.