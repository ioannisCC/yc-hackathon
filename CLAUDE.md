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
| Per-business knowledge (services, hours, prices) | **Moss** — local SDK only (`uv sync --extra local`); prod runs REST fallback + in-memory scan. See `backend/HANDOFF_NOTES.md`. |
| Per-caller memory (preferences, history) | **Supermemory** (container tag `caller_+1XXX`) |
| Email confirmations + reply-driven reschedule/cancel | **AgentMail** (WebSockets, inbox per business) |
| Bookings + calendar | **Cal.com API v2** (one platform-owned account, event types tagged by `business_id`) |
| Outbound agent-to-agent calls (Claude Code → MCP → backend → AgentPhone) | **MCP server** at `mcp-server/` (sibling to `backend/`, `frontend/`) |
| Optional loader logo | Gemini 2.5 Flash (sponsor only) |
| Database | Postgres + SQLModel (businesses, call_logs, outbound_calls) |
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

8. **Outbound agent-to-agent runs through the same webhook.** When Sir's caller agent (env `CALLER_AGENT_ID`) dials a target business, AgentPhone hits `/webhooks/agentphone` exactly like an inbound call. The handler resolves agent → `Business` first, then falls through to active `OutboundCall` by `caller_agent_id`. Outbound uses the per-call `dynamic_system_prompt` stored on `OutboundCall` and ONLY the `end_call` tool (`OUTBOUND_TOOL_SCHEMAS`). Receiving business agents keep their full booking toolset.

9. **Per-call idempotency.** `OutboundCall.cal_booking_uid` and `CallLog.cal_booking_uid` anchor `book_appointment` so transcription drift can't trigger duplicate bookings inside a single call. If the field is set, the tool returns `{already_booked: true, booking_uid}` instead of POSTing Cal.com again. The webhook pre-fetches the row before `brain.run_turn` and passes it as `call_context`.

10. **Dynamic outbound prompt synthesis with pinned anti-drift principles.** `generate_outbound_system_prompt()` calls Haiku with a meta-prompt for the dynamic preamble (capped at 700 chars), then appends `_ANTI_DRIFT_PRINCIPLES` verbatim from Python. Total prompt stays under 2000 chars. Principles cover: brief turns, end-of-call protocol, 4-turn drift escape, audio-noise handling, no repeats.

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
- ❌ Do not store appointments in our Postgres. Cal.com owns bookings. We store `businesses`, `call_logs`, `outbound_calls` only.
- ❌ `pyproject.toml` is canonical. `requirements.txt` still exists as a defensive nixpacks fallback — keep it aligned, do not let it diverge from `pyproject.toml`.
- ❌ Do not add libraries not already in the stack table above without asking.
- ❌ Do not put `moss` back in main `[project.dependencies]`. It pulls `inferedge-moss-core==0.11.0` which is not published on PyPI Linux — Railway build will break. Local-only via `[project.optional-dependencies].local`.
- ❌ Do not break inbound flow when extending outbound (or vice versa). The webhook handler is the only shared seam; route by `agent_id` → `Business` then fall through to `OutboundCall`.

## How to Verify Your Work

Every external integration has a smoke test in `backend/app/tests/smoke.py`. After any change touching a service:

```bash
cd backend && python -m app.tests.smoke
```

All 8 services should print `PASS` (Browser Use 402 free-tier failure is a known pre-existing soft-fail when credits are out). Total runtime under 30 seconds. The smoke test never spends money.

There is also `python -m app.tests.test_book_idempotent` which offline-verifies the `book_appointment` idempotency boundary (no network).

## Cal.com Specifics

- API key prefix: `cal_live_` (live) or `cal_` (test). Live for us.
- Auth: `Authorization: Bearer ${CALCOM_API_KEY}`.
- Cal.com versions endpoints SEPARATELY. Passing the wrong `cal-api-version` for a given path silently routes to a stale handler. Use the constants from `calcom_svc.py`:
  - `EVENT_TYPES_API_VERSION = "2024-06-14"` (event-types)
  - `BOOKINGS_API_VERSION = "2024-08-13"` (bookings, reschedule, cancel, list)
  - `SLOTS_API_VERSION = "2024-09-04"` (availability — older versions 404)
- Base: `https://api.cal.com/v2`.
- Rate limit: 120 req/min — plenty for hackathon.
- Endpoints we use: `GET /me` (smoke), `POST /event-types` (create per-service), `GET /slots` (availability), `POST /bookings` (book), `POST /bookings/{uid}/reschedule`, `POST /bookings/{uid}/cancel`.
- `start` on `/bookings` and `/bookings/{uid}/reschedule` MUST be UTC `YYYY-MM-DDTHH:MM:SS.000Z` — Cal.com rejects signed offsets. Use `calcom_svc._to_utc_z()`.

## Phase Roadmap (actual state as of 2026-05-18)

The original 5-phase plan shipped. Deviations from the original plan are inline below.

- **Phase 1 (done):** Skeleton + smoke tests.
- **Phase 2 (done):** Onboarding pipeline. **Deviation:** Moss index creation requires the SDK and is local-only — onboarding logs a warning and continues with `moss_index_name=None` when running in prod; `lookup_business_info` falls back to in-memory scan over `business.extra.scraped`.
- **Phase 3 (done):** Voice webhook + Claude tool-call loop + AgentMail WS subscriber.
- **Phase 4 (done):** Frontend dashboard, dark/glass UI.
- **Phase 5 (done — pivoted from rehearsal to outbound agent-to-agent):** Sir types in Claude Code ("call Code Salon, book a haircut Tuesday 2pm"); MCP server (`mcp-server/`) calls `POST /agents/outbound-call`; backend synthesizes per-call prompt via Haiku, dials via AgentPhone `/v1/calls`, arms a 180s watchdog. New `OutboundCall` table, `CALLER_AGENT_ID` env, `OUTBOUND_TOOL_SCHEMAS = [end_call]`.
- **Phase 6 (done):** Dashboard endpoints for the outbound demo view — `GET /agents/outbound-call/{id}/transcript` (bootstrap), `/stream` (SSE), `/recording` (audio/wav proxy, keeps `AGENTPHONE_API_KEY` server-side).
- **Phase 7 (done):** Per-call `book_appointment` idempotency via `cal_booking_uid` on both `OutboundCall` and `CallLog`. Outbound prompt anti-drift principles pinned in Python. `send_email` tool for custom (non-booking-confirmation) email.

## Current architecture seams to know about

- **`webhooks.py` is the single shared entry point.** Inbound (`Business` route) and outbound (`OutboundCall` route) both flow through `/webhooks/agentphone`. Disambiguation: try `Business.agentphone_agent_id == agent_id` first; if None, fall through to active `OutboundCall.caller_agent_id == agent_id`. Never 404 on unknown agent_ids — return `{ok: true}`.
- **`brain.run_turn()`** accepts `system_prompt_override`, `tools_override`, and `call_context`. Outbound passes the `OutboundCall`; inbound pre-fetches the active `CallLog`.
- **MCP server** lives at `mcp-server/` (sibling, not under `backend/`). Has its own venv (`mcp-server/.venv`). Registered in Claude Code via `claude mcp add` writing to `~/.claude.json`, NOT via hand-edited config. `AGENTPHONE_BACKEND_URL` env points at Railway.
- **`init_db()`** runs idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for additive migrations (Phase 7 added `cal_booking_uid`). `create_all()` alone does not alter existing tables.

If you're not sure which phase you're in, you're in Phase 7+ — features added beyond the original plan are additive on top of working inbound flow. Never regress inbound when extending outbound.