"""Cal.com API v2 wrapper. All bookings live in Cal.com, not our DB."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone as dt_timezone
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_BASE = "https://api.cal.com/v2"

# Cal.com versions endpoints SEPARATELY. Passing the wrong cal-api-version
# for a given path silently routes to a stale handler and returns 404 / wrong
# schema. Verified live (May 2026):
#   /event-types     → 2024-06-14
#   /bookings/*      → 2024-08-13
#   /slots           → 2024-09-04 (older versions 404)
# Every call below sets its version via headers= override.
EVENT_TYPES_API_VERSION = "2024-06-14"
BOOKINGS_API_VERSION = "2024-08-13"
SLOTS_API_VERSION = "2024-09-04"

# Cal.com event-type creates are 1-3s each but burst-slow under load when
# many businesses onboard in parallel — give it plenty of headroom.
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=_BASE,
            timeout=_TIMEOUT,
            headers={
                "Authorization": f"Bearer {settings.CALCOM_API_KEY}",
                # Reasonable default for endpoints that don't override
                # (e.g. /me). Path-specific versions are passed per call.
                "cal-api-version": BOOKINGS_API_VERSION,
                "Content-Type": "application/json",
            },
        )
    return _http


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")[:80]


def _to_utc_z(iso: str) -> str:
    """Normalize any ISO 8601 datetime to UTC `YYYY-MM-DDTHH:MM:SS.000Z`.

    Cal.com v2 /bookings rejects offsets like `-07:00` even when they
    represent the same instant — it wants the literal `.000Z` form. We
    accept anything `datetime.fromisoformat` understands (trailing `Z`,
    explicit `+00:00`, signed offsets, or naive). Naive values are
    treated as already-UTC."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


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

    Cal.com versions endpoints separately — see EVENT_TYPES_API_VERSION.
    Wrong version → 404.

    Single retry with 1s backoff on ReadTimeout or 5xx — 4xx is a client
    bug (bad slug, dupe title) and is not worth retrying."""
    title = f"{business_name} - {service_name}"
    body = {
        "title": title,
        "slug": _slugify(title) + f"-{business_id[:8]}",
        "lengthInMinutes": duration_minutes,
        "metadata": {"business_id": business_id, "service_name": service_name},
    }
    extra_headers = {"cal-api-version": EVENT_TYPES_API_VERSION}

    for attempt in (1, 2):
        try:
            r = await _client().post(
                "/event-types", json=body, headers=extra_headers
            )
            if 500 <= r.status_code < 600 and attempt == 1:
                log.warning(
                    "Cal.com create_event_type 5xx (attempt %d): %s",
                    attempt, r.status_code,
                )
                await asyncio.sleep(1.0)
                continue
            r.raise_for_status()
            return int(r.json().get("data", {})["id"])
        except httpx.ReadTimeout:
            if attempt == 1:
                log.warning("Cal.com create_event_type ReadTimeout, retrying once")
                await asyncio.sleep(1.0)
                continue
            raise

    raise RuntimeError("Cal.com create_event_type unreachable")  # pragma: no cover


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
        headers={"cal-api-version": SLOTS_API_VERSION},
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
        "start": _to_utc_z(start_iso),
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": timezone,
            "language": "en",
        },
    }
    r = await _client().post(
        "/bookings",
        json=body,
        headers={"cal-api-version": BOOKINGS_API_VERSION},
    )
    r.raise_for_status()
    return r.json().get("data", r.json())


async def reschedule_booking(
    booking_uid: str, new_start_iso: str, reason: str = "Caller requested"
) -> dict[str, Any]:
    r = await _client().post(
        f"/bookings/{booking_uid}/reschedule",
        json={"start": _to_utc_z(new_start_iso), "reschedulingReason": reason},
        headers={"cal-api-version": BOOKINGS_API_VERSION},
    )
    r.raise_for_status()
    return r.json().get("data", r.json())


async def cancel_booking(
    booking_uid: str, reason: str = "Caller requested"
) -> dict[str, Any]:
    r = await _client().post(
        f"/bookings/{booking_uid}/cancel",
        json={"cancellationReason": reason},
        headers={"cal-api-version": BOOKINGS_API_VERSION},
    )
    r.raise_for_status()
    return r.json().get("data", r.json())


async def list_bookings_for_business(business_id: str) -> list[dict[str, Any]]:
    """Filter Cal.com bookings by metadata.business_id."""
    r = await _client().get(
        "/bookings",
        params={"take": 100},
        headers={"cal-api-version": BOOKINGS_API_VERSION},
    )
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
