# AI Receptionist

Paste a business URL → in under 5 minutes that business has a live phone
number staffed by a voice AI that books real appointments.

See `CLAUDE.md` for the full architecture and conventions.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # then fill in the keys
```

Postgres: paste your Railway-provided `DATABASE_URL` into `backend/.env`.
(No local docker-compose — Railway Postgres in dev too, per CLAUDE.md.)

## Smoke tests (8 checks, parallel, <30s)

```bash
cd backend && python -m app.tests.smoke
```

All 8 must print **PASS**. The smoke test never spends money.

## Required `backend/.env` keys

| Var | Service |
|---|---|
| `DATABASE_URL` | Postgres (Railway-provided in dev too) |
| `ANTHROPIC_API_KEY` | Claude Haiku 4.5 (voice brain) |
| `GEMINI_API_KEY` | Gemini 2.5 Flash (optional sponsor loader) |
| `AGENTPHONE_API_KEY` | AgentPhone (voice + numbers) |
| `AGENTPHONE_WEBHOOK_SECRET` | run `rotate_account_webhook_secret()` once manually, paste the output. Never auto-run on boot — it rotates every call. |
| `MOSS_PROJECT_ID` + `MOSS_PROJECT_KEY` | Moss (per-business knowledge index) |
| `SUPERMEMORY_API_KEY` | Supermemory (per-caller memory) |
| `AGENTMAIL_API_KEY` | AgentMail (inbox per business) |
| `BROWSER_USE_API_KEY` | Browser Use v3 |
| `CALCOM_API_KEY` | Cal.com v2 (`cal_live_…`) |
| `PUBLIC_BACKEND_URL` | ngrok / Railway URL (required for onboarding) |

## Run dev

```bash
# 1. Backend
cd backend && uvicorn app.main:app --reload

# 2. Frontend
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
```

## Onboard a test business

```bash
curl -X POST http://localhost:8000/businesses \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

Response includes `phone_number` — call that number to talk to the agent.

## Integration tests (spend small $)

```bash
cd backend && python -m app.tests.integration
```

Onboards a fixture business, posts a fake voice webhook, and simulates an
email-reply cancel. Requires uvicorn running on `:8000` for the voice-turn test.
