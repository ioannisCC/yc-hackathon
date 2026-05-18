"""Offline idempotency check for book_appointment.

Verifies the duplicate-booking loop bug is fixed: two consecutive calls
to book_appointment with the same args + same call_context should result
in exactly ONE Cal.com POST. The second call must return
already_booked=True with the cached uid.

Run:
    cd backend && python -m app.tests.test_book_idempotent
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any
from uuid import uuid4

from app.agent import tools
from app.models import OutboundCall


class _FakeBiz:
    """Mimics the fields book_appointment touches on Business without
    requiring an actual ORM-attached row."""

    def __init__(self) -> None:
        self.id = uuid4()
        self.name = "Fake Salon"
        self.timezone = "America/Los_Angeles"
        self.agentmail_inbox_id = "inbox_fake"
        self.cal_event_type_ids = [42]


async def _run() -> None:
    biz = _FakeBiz()
    ctx = OutboundCall(
        target_business_id=biz.id,
        caller_agent_id="caller_x",
        intent="test",
        caller_context={},
        dynamic_system_prompt="...",
        status="in_progress",
    )

    # ---- Spy fakes -----------------------------------------------------
    calcom_calls: list[dict[str, Any]] = []

    async def fake_create_booking(
        event_id: int, attendee_name: str, attendee_email: str,
        start_iso: str, tz: str,
    ) -> dict[str, Any]:
        calcom_calls.append(
            {
                "event_id": event_id,
                "name": attendee_name,
                "email": attendee_email,
                "start": start_iso,
                "tz": tz,
            }
        )
        return {"uid": "booking_abc123", "id": "booking_abc123"}

    mail_calls: list[dict[str, Any]] = []

    async def fake_send_email(inbox_id: str, **kwargs: Any) -> None:
        mail_calls.append({"inbox_id": inbox_id, **kwargs})

    # Replace the real service calls.
    tools.calcom_svc.create_booking = fake_create_booking  # type: ignore[assignment]
    tools.mail_svc.send_email = fake_send_email  # type: ignore[assignment]

    # Also short-circuit the merge() persistence — we're not testing the DB
    # write path here, just the in-memory idempotency boundary. The real
    # session would 500 because the FK to Business doesn't exist.
    class _NoOpSession:
        async def merge(self, obj: Any) -> Any:
            return obj

        async def commit(self) -> None:
            return None

    class _NoOpScope:
        async def __aenter__(self) -> _NoOpSession:
            return _NoOpSession()

        async def __aexit__(self, *args: Any) -> None:
            return None

    tools.session_scope = lambda: _NoOpScope()  # type: ignore[assignment]

    # ---- First call ----------------------------------------------------
    args = {
        "service_name": "Haircut",
        "start_iso": "2026-05-21T16:00:00.000Z",
        "caller_name": "Sir",
        "caller_email": "n@example.com",
    }
    r1 = await tools.book_appointment(
        biz,  # type: ignore[arg-type]
        "+12297027082",
        call_context=ctx,
        **args,
    )
    assert r1["already_booked"] is False, f"first call should not be cached: {r1}"
    assert r1["booking_uid"] == "booking_abc123", r1
    assert ctx.cal_booking_uid == "booking_abc123", "uid should be written on ctx"
    assert len(calcom_calls) == 1, f"expected 1 Cal.com POST, got {len(calcom_calls)}"

    # ---- Second call with the SAME context ----------------------------
    r2 = await tools.book_appointment(
        biz,  # type: ignore[arg-type]
        "+12297027082",
        call_context=ctx,
        **args,
    )
    assert r2["already_booked"] is True, f"second call should be cached: {r2}"
    assert r2["booking_uid"] == "booking_abc123", r2
    assert len(calcom_calls) == 1, (
        f"second call should NOT POST again — saw {len(calcom_calls)} total"
    )

    # ---- Third call with NO context (idempotency disabled) ------------
    r3 = await tools.book_appointment(
        biz,  # type: ignore[arg-type]
        "+12297027082",
        call_context=None,
        **args,
    )
    assert r3["already_booked"] is False, r3
    assert len(calcom_calls) == 2, (
        f"context=None should POST again — saw {len(calcom_calls)}"
    )

    print("PASS  book_appointment idempotency")
    print(f"  - 2 calls + same ctx → 1 Cal.com POST")
    print(f"  - 2nd call returned already_booked=True with cached uid")
    print(f"  - call without ctx still POSTs (idempotency is opt-in)")


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except AssertionError as e:
        print(f"FAIL  {e}")
        sys.exit(1)
