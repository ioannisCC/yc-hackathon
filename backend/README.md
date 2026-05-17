# Backend

FastAPI + SQLModel + asyncpg.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # then fill in the 7 API keys
```

## Smoke tests

Verifies every external service answers with our keys. Must finish in <30s
and must never spend money.

```bash
python -m app.tests.smoke
```

## Dev server

```bash
uvicorn app.main:app --reload
```

Health probe: `GET /health` → `{"status": "ok"}`.

## Files of note

| Path | Purpose |
|---|---|
| `app/config.py` | Loads `.env` via pydantic-settings |
| `app/db.py` | Async SQLModel engine + session |
| `app/models.py` | `Business`, `Caller`, `CallLog` (bookings live in Cal.com) |
| `app/services/calcom_svc.py` | Cal.com v2 wrapper (`cal-api-version: 2024-08-13`) |
| `app/tests/smoke.py` | Parallel sanity check for all 7 services |
