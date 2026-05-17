"""Tool schemas + dispatch for the voice agent. Each tool takes the active
Business + caller phone and any tool args, returns a JSON-serializable dict."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from app.models import Business
from app.services import calcom_svc, mail_svc, memory_svc, moss_svc
from app.services.logging_svc import log_call_event

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


# ---------- Tool schemas (Claude tool-use format) ------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "lookup_business_info",
        "description": "Retrieve authoritative business knowledge — services, hours, prices, policies. Use for any factual question.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_availability",
        "description": "Check Cal.com availability for a named service on a given calendar date (YYYY-MM-DD). Returns ISO start times.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["service_name", "date"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Create a booking. Always confirm name, email, service, and start time verbally before calling.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"},
                "start_iso": {"type": "string", "description": "RFC 3339 start time"},
                "caller_name": {"type": "string"},
                "caller_email": {"type": "string"},
            },
            "required": ["service_name", "start_iso", "caller_name", "caller_email"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": "Move an existing booking to a new start time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_uid": {"type": "string"},
                "new_start_iso": {"type": "string"},
            },
            "required": ["booking_uid", "new_start_iso"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing booking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_uid": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["booking_uid"],
        },
    },
    {
        "name": "recall_caller",
        "description": "Recall what we already know about this caller (preferences, prior visits).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "remember_about_caller",
        "description": "Save a durable fact about this caller (preferences, allergies, kid names, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {"fact": {"type": "string"}},
            "required": ["fact"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Transfer the call to the business owner because the caller is upset or the request is out of scope.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


# ---------- Handlers -----------------------------------------------------------


async def lookup_business_info(
    business: Business, _caller: str, query: str
) -> dict[str, Any]:
    # Prefer semantic via Moss if this business has an index
    if business.moss_index_name:
        try:
            result = await moss_svc.query(business.moss_index_name, query)
            snippets = [d.get("text", "") for d in (result.get("docs") or []) if d.get("text")]
            if snippets:
                return {"results": snippets, "source": "moss"}
        except Exception as e:
            log_call_event(
                business.id, "tool:lookup_business_info", "moss_fallback",
                {"err": str(e)},
            )
    # Fallback: keyword scan over the BusinessInfo JSON stored at onboarding
    return {"results": _scan_extra(business.extra, query), "source": "in-memory"}


def _scan_extra(extra: dict[str, Any], q: str) -> list[str]:
    scraped = extra.get("scraped") or {}
    needles = [t for t in q.lower().split() if len(t) > 2]
    chunks: list[str] = []
    if scraped.get("description"):
        chunks.append(str(scraped["description"]))
    if scraped.get("booking_policy"):
        chunks.append(f"Booking policy: {scraped['booking_policy']}")
    for d, h in (scraped.get("hours") or {}).items():
        chunks.append(f"{d}: {h}")
    for s in (scraped.get("services") or []):
        line = s.get("name", "")
        if s.get("duration_minutes"):
            line += f" — {s['duration_minutes']} min"
        if s.get("price_usd") is not None:
            line += f" — ${s['price_usd']:g}"
        chunks.append(line)
    if not needles:
        return chunks[:5]
    return [c for c in chunks if any(n in c.lower() for n in needles)][:5]


def _pick_event_type(business: Business, service_name: str) -> int:
    """For Phase 2 we map by index — Phase 4 will properly look up by metadata."""
    if not business.cal_event_type_ids:
        raise RuntimeError("No event types configured for this business")
    return business.cal_event_type_ids[0]


async def get_availability(
    business: Business, _caller: str, service_name: str, date: str
) -> dict[str, Any]:
    event_id = _pick_event_type(business, service_name)
    start = f"{date}T00:00:00Z"
    end = (datetime.fromisoformat(date) + timedelta(days=1)).replace(
        tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    slots = await calcom_svc.get_availability(event_id, start, end)
    return {"event_type_id": event_id, "slots": slots[:10]}


async def book_appointment(
    business: Business,
    caller: str,
    service_name: str,
    start_iso: str,
    caller_name: str,
    caller_email: str,
) -> dict[str, Any]:
    event_id = _pick_event_type(business, service_name)
    booking = await calcom_svc.create_booking(
        event_id, caller_name, caller_email, start_iso, business.timezone
    )
    uid = booking.get("uid") or booking.get("id")
    # Confirmation email (fire & forget timing-wise but await for error propagation)
    try:
        await mail_svc.send_email(
            business.agentmail_inbox_id,
            to=caller_email,
            subject=f"Booking confirmed — {business.name}",
            text=(
                f"Hi {caller_name},\n\n"
                f"Your {service_name} appointment is confirmed for {start_iso}.\n"
                f"Reply to this email to reschedule or cancel.\n\n"
                f"— {business.name}"
            ),
        )
    except Exception as e:
        log_call_event(
            business.id, "tool:book_appointment", "email_send_failed", {"err": str(e)}
        )
    return {"uid": uid, "start": start_iso, "service": service_name}


async def reschedule_appointment(
    business: Business, _caller: str, booking_uid: str, new_start_iso: str
) -> dict[str, Any]:
    return await calcom_svc.reschedule_booking(booking_uid, new_start_iso)


async def cancel_appointment(
    business: Business,
    _caller: str,
    booking_uid: str,
    reason: str = "Caller requested",
) -> dict[str, Any]:
    return await calcom_svc.cancel_booking(booking_uid, reason)


async def recall_caller(business: Business, caller: str) -> dict[str, Any]:
    return {"profile": await memory_svc.profile(caller)}


async def remember_about_caller(
    business: Business, caller: str, fact: str
) -> dict[str, Any]:
    await memory_svc.remember(caller, fact)
    return {"ok": True}


async def escalate_to_human(
    business: Business, _caller: str, reason: str
) -> dict[str, Any]:
    # Phase 2 stub — real call transfer is Phase 3.
    log_call_event(business.id, "tool:escalate", "transfer_requested", {"reason": reason})
    return {"status": "transfer initiated"}


async def end_call(
    _business: Business, _caller: str, farewell_message: str = ""
) -> dict[str, Any]:
    """Outbound-only tool. The brain returns end_call=True so the webhook
    can hang up and mark the OutboundCall completed. Tool result is mostly
    informational — the spoken farewell is the assistant's text in the same
    turn, not this return value."""
    return {"farewell_message": farewell_message, "end_call": True}


DISPATCH: dict[str, ToolHandler] = {
    "lookup_business_info": lookup_business_info,
    "get_availability": get_availability,
    "book_appointment": book_appointment,
    "reschedule_appointment": reschedule_appointment,
    "cancel_appointment": cancel_appointment,
    "recall_caller": recall_caller,
    "remember_about_caller": remember_about_caller,
    "escalate_to_human": escalate_to_human,
    "end_call": end_call,
}


# Outbound caller agents have NO booking tools — the receiving business agent
# owns the calendar. The caller only ends the call.
END_CALL_SCHEMA: dict[str, Any] = {
    "name": "end_call",
    "description": (
        "Hang up the call after a natural farewell. Use ONLY after the goal is "
        "achieved (booking confirmed, info gathered) or it's clear no progress "
        "is possible. Always say one short farewell line in the same turn — "
        "the call ends right after."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "farewell_message": {
                "type": "string",
                "description": "One short farewell line, e.g. 'Thanks so much, have a great day!'",
            },
        },
        "required": ["farewell_message"],
    },
}

OUTBOUND_TOOL_SCHEMAS: list[dict[str, Any]] = [END_CALL_SCHEMA]


async def run_tool(
    name: str, business: Business, caller_phone: str, args: dict[str, Any]
) -> dict[str, Any]:
    handler = DISPATCH.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return await handler(business, caller_phone, **args)
    except Exception as e:
        log_call_event(
            business.id, f"tool:{name}", "tool_error",
            {"err": f"{type(e).__name__}: {e}"},
        )
        return {"error": f"{type(e).__name__}: {e}"}
