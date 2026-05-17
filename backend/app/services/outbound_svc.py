"""Outbound call orchestration.

Place a call from Sir's caller agent → a target business's phone number,
synthesize the per-call system prompt, persist the OutboundCall row, and
arm a hard-timeout watchdog. The agentphone-side hangup is best-effort
because the SDK surface for direct hangups varies; the watchdog also marks
the row completed locally even if the remote hangup fails."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.models import Business, OutboundCall
from app.services.logging_svc import log_call_event

log = logging.getLogger(__name__)

_AGENTPHONE_API_BASE = "https://api.agentphone.ai/v1"


# ---------- Target resolution ------------------------------------------------


async def resolve_target(s: AsyncSession, query: str) -> Business | None:
    """Resolve a free-form target query (UUID, name fragment, or phone)."""
    q = (query or "").strip()
    if not q:
        return None

    # 1. UUID
    try:
        as_uuid = UUID(q)
    except (ValueError, AttributeError):
        as_uuid = None
    if as_uuid is not None:
        row = await s.get(Business, as_uuid)
        if row is not None:
            return row

    # 2. Phone number (loose match — allow with/without +1, spaces, dashes)
    digits = "".join(c for c in q if c.isdigit())
    if len(digits) >= 7:
        variants = [q, f"+{digits}"]
        if not digits.startswith("1"):
            variants.append(f"+1{digits}")
        candidates = (
            await s.execute(
                select(Business).where(Business.phone_number.in_(variants))  # type: ignore[union-attr]
            )
        ).scalars().all()
        if candidates:
            return candidates[0]

    # 3. Case-insensitive name fragment
    like = f"%{q}%"
    row = (
        await s.execute(
            select(Business)
            .where(Business.name.ilike(like))  # type: ignore[union-attr]
            .order_by(Business.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


# ---------- Active-call lookup (used by webhook routing) ---------------------


async def get_active_outbound_call_by_caller_agent_id(
    caller_agent_id: str,
) -> tuple[OutboundCall, Business] | None:
    """Find the in-flight OutboundCall for this caller agent and load its
    target Business. Used by the webhook handler when no Business row matches
    the inbound agent_id (because that agent_id is OUR caller agent)."""
    if not caller_agent_id:
        return None
    async with session_scope() as s:
        row = (
            await s.execute(
                select(OutboundCall)
                .where(OutboundCall.caller_agent_id == caller_agent_id)
                .where(
                    OutboundCall.status.in_(("initiating", "ringing", "in_progress"))  # type: ignore[union-attr]
                )
                .order_by(OutboundCall.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        biz = await s.get(Business, row.target_business_id)
        if biz is None:
            return None
        return row, biz


# ---------- AgentPhone hangup (best-effort) ----------------------------------


async def hangup_agentphone_call(agentphone_call_id: str) -> bool:
    """Try a few likely shapes for AgentPhone's hangup endpoint. Returns True
    if any returned a 2xx. AgentPhone's call lifecycle API is in flux; if
    none work, we still mark the row completed locally."""
    if not agentphone_call_id or not settings.AGENTPHONE_API_KEY:
        return False
    headers = {"Authorization": f"Bearer {settings.AGENTPHONE_API_KEY}"}
    attempts = [
        ("POST", f"{_AGENTPHONE_API_BASE}/calls/{agentphone_call_id}/end"),
        ("POST", f"{_AGENTPHONE_API_BASE}/calls/{agentphone_call_id}/hangup"),
        ("DELETE", f"{_AGENTPHONE_API_BASE}/calls/{agentphone_call_id}"),
    ]
    async with httpx.AsyncClient(timeout=10.0) as http:
        for method, url in attempts:
            try:
                r = await http.request(method, url, headers=headers)
            except httpx.HTTPError as e:
                log.warning("hangup attempt %s %s errored: %s", method, url, e)
                continue
            if 200 <= r.status_code < 300:
                log.info("agentphone hangup ok via %s %s", method, url)
                return True
            log.info("agentphone hangup %s %s -> %d", method, url, r.status_code)
    return False


# ---------- AgentPhone outbound-call dial -------------------------------------


async def place_agentphone_call(
    *, caller_agent_id: str, to_number: str
) -> tuple[str | None, str | None]:
    """POST /v1/calls. Returns (agentphone_call_id, error_message).

    AgentPhone has not publicly stabilized this endpoint name across the SDK
    revisions we've seen, so we go directly over HTTP and tolerate both
    `callId` and `id` in the response."""
    if not settings.AGENTPHONE_API_KEY:
        return None, "AGENTPHONE_API_KEY not configured"

    headers = {
        "Authorization": f"Bearer {settings.AGENTPHONE_API_KEY}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "agentId": caller_agent_id,
        "toNumber": to_number,
    }
    if settings.CALLER_AGENT_PHONE_NUMBER:
        body["fromNumber"] = settings.CALLER_AGENT_PHONE_NUMBER

    log.info("agentphone outbound dial agent=%s to=%s", caller_agent_id, to_number)
    async with httpx.AsyncClient(timeout=30.0) as http:
        try:
            r = await http.post(f"{_AGENTPHONE_API_BASE}/calls", headers=headers, json=body)
        except httpx.HTTPError as e:
            return None, f"network error: {e}"
    if not (200 <= r.status_code < 300):
        return None, f"agentphone {r.status_code}: {r.text[:300]}"
    try:
        data = r.json()
    except ValueError:
        return None, f"agentphone non-JSON response: {r.text[:300]}"

    nested = data.get("data") if isinstance(data, dict) else None
    payload = nested if isinstance(nested, dict) else data
    call_id = (
        payload.get("callId")
        or payload.get("call_id")
        or payload.get("id")
    )
    if not isinstance(call_id, str):
        return None, f"agentphone response missing call id: {payload!r}"
    return call_id, None


# ---------- Status transitions -----------------------------------------------


async def update_outbound_status(
    outbound_call_id: UUID,
    *,
    status: str | None = None,
    agentphone_call_id: str | None = None,
    error: str | None = None,
    end_reason: str | None = None,
    set_ended_at: bool = False,
    call_log_id: UUID | None = None,
) -> OutboundCall | None:
    async with session_scope() as s:
        row = await s.get(OutboundCall, outbound_call_id)
        if row is None:
            return None
        if status is not None:
            row.status = status
        if agentphone_call_id is not None:
            row.agentphone_call_id = agentphone_call_id
        if error is not None:
            row.error = error
        if end_reason is not None:
            row.end_reason = end_reason
        if set_ended_at and row.ended_at is None:
            row.ended_at = datetime.now(timezone.utc)
        if call_log_id is not None:
            row.call_log_id = call_log_id
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row


# ---------- Watchdog ----------------------------------------------------------


_watchdogs: dict[UUID, asyncio.Task[None]] = {}


async def _watchdog(outbound_call_id: UUID, timeout_s: int) -> None:
    try:
        await asyncio.sleep(timeout_s)
    except asyncio.CancelledError:
        return

    async with session_scope() as s:
        row = await s.get(OutboundCall, outbound_call_id)
        if row is None or row.status in ("completed", "failed"):
            return
        ap_call_id = row.agentphone_call_id or ""

    if ap_call_id:
        await hangup_agentphone_call(ap_call_id)
    log_call_event(
        None, "outbound_watchdog", "timeout",
        {"outbound_call_id": str(outbound_call_id), "timeout_s": timeout_s},
    )
    await update_outbound_status(
        outbound_call_id,
        status="completed",
        end_reason="timeout",
        set_ended_at=True,
    )


def arm_watchdog(outbound_call_id: UUID, timeout_s: int | None = None) -> None:
    """Schedule a one-shot hangup. Replaces any prior watchdog for this call."""
    existing = _watchdogs.pop(outbound_call_id, None)
    if existing is not None and not existing.done():
        existing.cancel()
    secs = timeout_s if timeout_s is not None else settings.OUTBOUND_CALL_TIMEOUT_S
    task = asyncio.create_task(_watchdog(outbound_call_id, secs))
    _watchdogs[outbound_call_id] = task


def cancel_watchdog(outbound_call_id: UUID) -> None:
    task = _watchdogs.pop(outbound_call_id, None)
    if task is not None and not task.done():
        task.cancel()


__all__ = [
    "arm_watchdog",
    "cancel_watchdog",
    "get_active_outbound_call_by_caller_agent_id",
    "hangup_agentphone_call",
    "place_agentphone_call",
    "resolve_target",
    "update_outbound_status",
]
