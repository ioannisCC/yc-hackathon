"""High-level calendar facade. Booking state lives in Cal.com — see calcom_svc."""
from __future__ import annotations

from app.services import calcom_svc


async def availability(event_type_id: int, start: str, end: str) -> list[str]:
    return await calcom_svc.get_availability(event_type_id, start, end)


async def book(
    event_type_id: int,
    name: str,
    email: str,
    start_iso: str,
    timezone: str,
) -> dict:
    return await calcom_svc.create_booking(
        event_type_id, name, email, start_iso, timezone
    )


async def reschedule(booking_uid: str, new_start_iso: str) -> dict:
    return await calcom_svc.reschedule_booking(booking_uid, new_start_iso)


async def cancel(booking_uid: str, reason: str = "Caller requested") -> dict:
    return await calcom_svc.cancel_booking(booking_uid, reason)
