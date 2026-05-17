"""Integration tests — actually exercise the live services end-to-end.

These DO spend small amounts of money. Run them manually after wiring changes:

    python -m app.tests.integration

Disabled in the default smoke run (smoke.py imports nothing from here).
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import MagicMock

import httpx
from sqlmodel import select

from app.db import init_db, session_scope
from app.models import Business, CallLog
from app.services import calcom_svc, mail_svc
from app.services.email_intent_svc import handle_inbox_event
from app.services.onboarding_svc import onboard_business

# A small, deterministic test page used as the Browser Use target.
FIXTURE_URL = "https://example.com"


async def test_onboard_smoke_business() -> Business:
    """Onboards a business from FIXTURE_URL and asserts shape."""
    print("\n[1/3] onboarding test business…")
    biz = await onboard_business(FIXTURE_URL)
    assert biz.phone_number, "no phone number assigned"
    assert biz.moss_index_name, "no moss index"
    assert biz.agentmail_inbox_id, "no inbox"
    assert biz.cal_event_type_ids, "no event types"
    async with session_scope() as s:
        row = (
            await s.execute(select(Business).where(Business.id == biz.id))
        ).scalar_one()
        assert row.system_prompt
    print(f"      → {biz.name} @ {biz.phone_number}, {len(biz.cal_event_type_ids)} event types")
    return biz


def _make_fake_webhook_payload(business: Business) -> dict[str, Any]:
    return {
        "event": "agent.message",
        "channel": "voice",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_id": business.agentphone_agent_id,
        "data": {
            "conversation_id": f"test_{int(time.time())}",
            "number_id": business.agentphone_number_id,
            "from_number": "+14155550123",
            "to_number": business.phone_number,
            "message": "Hi — what are your hours?",
            "direction": "inbound",
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "recent_history": [],
        "conversation_state": None,
    }


async def test_voice_turn_smoke(business: Business) -> None:
    """POSTs a signed fake AgentPhone webhook against a running uvicorn at :8000."""
    print("\n[2/3] voice turn test (requires uvicorn at localhost:8000)…")
    import hmac
    import hashlib
    from app.config import settings

    payload = _make_fake_webhook_payload(business)
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(
        settings.AGENTPHONE_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    async with httpx.AsyncClient(timeout=30) as c:
        async with c.stream(
            "POST",
            "http://localhost:8000/webhooks/agentphone",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": sig,
            },
        ) as r:
            assert r.status_code == 200, f"got {r.status_code}: {await r.aread()}"
            chunks: list[dict[str, Any]] = []
            async for line in r.aiter_lines():
                if line.strip():
                    chunks.append(json.loads(line))
    assert chunks and chunks[0].get("interim") is True
    assert chunks[-1].get("text"), "no final reply"
    print(f"      → reply: {chunks[-1]['text'][:80]}")

    # Give the fire-and-forget persist task a moment, then check CallLog
    await asyncio.sleep(1.0)
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(CallLog).where(CallLog.business_id == business.id)
            )
        ).scalars().all()
    assert rows, "no CallLog row written"
    print(f"      → CallLog rows: {len(rows)}")


async def test_email_reply_cancel(business: Business) -> None:
    """Books then simulates an email-reply cancel via handle_inbox_event."""
    print("\n[3/3] email-reply cancel test…")
    # Book a slot 7 days out
    start_iso = time.strftime(
        "%Y-%m-%dT15:00:00Z", time.gmtime(time.time() + 7 * 24 * 3600)
    )
    booking = await calcom_svc.create_booking(
        business.cal_event_type_ids[0],
        "Integration Test", "smoke@example.com",
        start_iso, business.timezone,
    )
    uid = booking.get("uid") or booking.get("id")
    assert uid, "no booking uid"
    print(f"      → booked uid={uid}")

    # Build a synthetic MessageReceivedEvent
    fake_msg = MagicMock()
    fake_msg.inbox_id = business.agentmail_inbox_id
    fake_msg.text = "Hi, please cancel my appointment, something came up."
    fake_msg.from_address = "smoke@example.com"
    fake_msg.subject = f"Re: Booking confirmed — {business.name} [uid:{uid}]"
    fake_msg.message_id = None  # skip the reply-send

    fake_event = MagicMock()
    fake_event.message = fake_msg

    await handle_inbox_event(fake_event)
    print("      → handler completed (check Cal.com bookings list to verify cancel)")


async def main() -> None:
    await init_db()
    biz = await test_onboard_smoke_business()
    await test_voice_turn_smoke(biz)
    await test_email_reply_cancel(biz)
    print("\nintegration suite OK")


if __name__ == "__main__":
    asyncio.run(main())
