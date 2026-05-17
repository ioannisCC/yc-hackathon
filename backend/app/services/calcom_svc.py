"""Cal.com API v2 wrapper. All bookings live in Cal.com, not our DB."""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import settings

_BASE = "https://api.cal.com/v2"
_VERSION = "2024-08-13"
_TIMEOUT = httpx.Timeout(10.0)

_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=_BASE,
            timeout=_TIMEOUT,
            headers={
                "Authorization": f"Bearer {settings.CALCOM_API_KEY}",
                "cal-api-version": _VERSION,
                "Content-Type": "application/json",
            },
        )
    return _http


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:80]


async def get_me() -> dict[str, Any]:
    r = await _client().get("/me")
    r.raise_for_status()
    return r.json()


async def create_event_type(
    business_id: str,
    business_name: str,
    service_name: str,
    duration_minutes: int = 30,
) -> int:
    """Create a per-service event type tagged with business_id metadata.

    Cal.com versions endpoints separately: event-types REQUIRES 2024-06-14,
    not the 2024-08-13 we use for bookings/slots. Wrong version → 404."""
    title = f"{business_name} - {service_name}"
    body = {
        "title": title,
        "slug": _slugify(title) + f"-{business_id[:8]}",
        "lengthInMinutes": duration_minutes,
        "metadata": {"business_id": business_id, "service_name": service_name},
    }
    r = await _client().post(
        "/event-types",
        json=body,
        headers={"cal-api-version": "2024-06-14"},
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    return int(data["id"])


async def get_availability(
    event_type_id: int, start_iso: str, end_iso: str
) -> list[str]:
    """Return ISO timestamps of available slots in [start, end]."""
    r = await _client().get(
        "/slots",
        params={
            "eventTypeId": event_type_id,
            "start": start_iso,
            "end": end_iso,
        },
    )
    r.raise_for_status()
    payload = r.json().get("data", {})
    slots: list[str] = []
    # /v2/slots returns { "<date>": [{"start": "<iso>"}, ...], ... } or { "slots": [...] }
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                for s in v:
                    if isinstance(s, dict) and "start" in s:
                        slots.append(s["start"])
                    elif isinstance(s, str):
                        slots.append(s)
    return slots


async def create_booking(
    event_type_id: int,
    attendee_name: str,
    attendee_email: str,
    start_iso: str,
    timezone: str,
) -> dict[str, Any]:
    body = {
        "eventTypeId": event_type_id,
        "start": start_iso,
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": timezone,
        },
    }
    r = await _client().post("/bookings", json=body)
    r.raise_for_status()
    return r.json().get("data", r.json())


async def reschedule_booking(
    booking_uid: str, new_start_iso: str, reason: str = "Caller requested"
) -> dict[str, Any]:
    r = await _client().post(
        f"/bookings/{booking_uid}/reschedule",
        json={"start": new_start_iso, "reschedulingReason": reason},
    )
    r.raise_for_status()
    return r.json().get("data", r.json())


async def cancel_booking(
    booking_uid: str, reason: str = "Caller requested"
) -> dict[str, Any]:
    r = await _client().post(
        f"/bookings/{booking_uid}/cancel",
        json={"cancellationReason": reason},
    )
    r.raise_for_status()
    return r.json().get("data", r.json())


async def list_bookings_for_business(business_id: str) -> list[dict[str, Any]]:
    """Filter Cal.com bookings by metadata.business_id."""
    r = await _client().get("/bookings", params={"take": 100})
    r.raise_for_status()
    rows = r.json().get("data", [])
    out: list[dict[str, Any]] = []
    for b in rows:
        meta = b.get("metadata") or {}
        if meta.get("business_id") == business_id:
            out.append(b)
    return out


async def close() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None
