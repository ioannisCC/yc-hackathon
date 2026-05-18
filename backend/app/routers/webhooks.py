"""AgentPhone webhook — verify, dedup, route by event, generate reply."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agent.brain import FALLBACK_REPLY, run_turn
from app.agent.tools import OUTBOUND_TOOL_SCHEMAS, CallContext
from app.config import settings
from app.db import session_scope
from app.models import Business, CallLog, OutboundCall
from app.services.logging_svc import log_call_event
from app.services.outbound_svc import (
    cancel_watchdog,
    get_active_outbound_call_by_caller_agent_id,
    hangup_agentphone_call,
    update_outbound_status,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# AgentPhone webhook timeout is short (~30s). Cap the brain so we always
# get a reply text out the door in time.
BRAIN_TIMEOUT_S = 25.0


# ---------- Signature verification (winning combo) ----------------------------


def verify_agentphone_webhook(
    raw_body: bytes, headers: dict[str, str], secret: str
) -> bool:
    """Collapsed to the proven combination from prod logs:
       HMAC-SHA256(secret_full_with_whsec_prefix, f"{ts}.{body}")"""
    sig_header = headers.get("x-webhook-signature", "")
    ts = headers.get("x-webhook-timestamp", "")
    if not sig_header.startswith("sha256="):
        return False
    provided_hex = sig_header.removeprefix("sha256=")
    signed = f"{ts}.".encode() + raw_body
    computed = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, provided_hex)


# ---------- Idempotency cache (LRU keyed on x-webhook-id) ---------------------
# AgentPhone may retry on transport failure. Re-running brain.py would
# double-bill Claude tokens and double-write transcripts. We cache the full
# response so duplicates return byte-identical answers without re-work.

_DEDUP_MAX = 1000
_seen_responses: OrderedDict[str, dict[str, Any]] = OrderedDict()
_seen_lock = threading.Lock()


def _check_dedup(webhook_id: str) -> dict[str, Any] | None:
    if not webhook_id:
        return None
    with _seen_lock:
        cached = _seen_responses.get(webhook_id)
        if cached is not None:
            _seen_responses.move_to_end(webhook_id)
            return cached
    return None


def _record_response(webhook_id: str, response: dict[str, Any]) -> None:
    if not webhook_id:
        return
    with _seen_lock:
        _seen_responses[webhook_id] = response
        while len(_seen_responses) > _DEDUP_MAX:
            _seen_responses.popitem(last=False)


# ---------- DB helpers --------------------------------------------------------


async def get_business_by_agent_id(agent_id: str) -> Business | None:
    async with session_scope() as s:
        r = await s.execute(
            select(Business).where(Business.agentphone_agent_id == agent_id)
        )
        return r.scalar_one_or_none()


async def _find_active_call_log_for_caller(
    *, business_id: UUID, call_id: str | None, caller_phone: str,
) -> CallLog | None:
    """Pre-brain lookup for the inbound idempotency context. The CallLog
    row is created by _persist_chunk on the first turn — on later turns we
    fetch it here so book_appointment can read/write cal_booking_uid."""
    async with session_scope() as s:
        return await _find_existing_call(
            s, business_id=business_id, call_id=call_id, caller_phone=caller_phone,
        )


async def _find_existing_call(
    s: AsyncSession,
    *,
    business_id: UUID,
    call_id: str | None,
    caller_phone: str,
) -> CallLog | None:
    if call_id:
        r = await s.execute(
            select(CallLog).where(CallLog.conversation_id == call_id)
        )
        existing = r.scalar_one_or_none()
        if existing is not None:
            return existing
    # AgentPhone sometimes sends callId=null on the first message of a call.
    # Fall back to "most recent in_progress call for this caller_phone".
    if caller_phone:
        r = await s.execute(
            select(CallLog)
            .where(CallLog.business_id == business_id)
            .where(CallLog.caller_phone == caller_phone)
            .where(CallLog.status == "in_progress")
            .order_by(CallLog.started_at.desc())
            .limit(1)
        )
        return r.scalar_one_or_none()
    return None


# ---------- Main handler ------------------------------------------------------


@router.post("/agentphone")
async def agentphone_webhook(request: Request) -> dict[str, Any]:
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    secret = settings.AGENTPHONE_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=500, detail="webhook secret not configured")

    if not verify_agentphone_webhook(raw_body, headers, secret):
        raise HTTPException(status_code=401, detail="invalid signature")

    webhook_id = headers.get("x-webhook-id", "")
    cached = _check_dedup(webhook_id)
    if cached is not None:
        return cached

    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")

    event_type = headers.get("x-webhook-event") or payload.get("event") or ""
    agent_id = payload.get("agentId") or ""
    data: dict[str, Any] = payload.get("data") or {}
    call_id_value = data.get("callId")
    call_id: str | None = call_id_value if isinstance(call_id_value, str) else None
    call_status = data.get("status")

    log.info(
        "agentphone_webhook event=%s agent_id=%s call_id=%s status=%s",
        event_type, agent_id, call_id, call_status,
    )

    if not agent_id:
        return _ack(webhook_id, {"ok": True})

    # Resolve the agent: inbound (Business) first, then outbound (OutboundCall).
    business = await get_business_by_agent_id(agent_id)
    outbound_call: OutboundCall | None = None
    outbound_target: Business | None = None
    if business is None:
        active = await get_active_outbound_call_by_caller_agent_id(agent_id)
        if active is not None:
            outbound_call, outbound_target = active
            # For the brain, the "active business context" is the TARGET we're
            # dialing — that's what the synthesized prompt references. The
            # caller agent does not use the target's tool list though.
            business = outbound_target

    if business is None:
        log.warning("webhook for unknown agent_id=%s — returning 200", agent_id)
        return _ack(webhook_id, {"ok": True})

    if event_type == "agent.message":
        caller_transcript = str(data.get("transcript") or "")
        caller_number = str(data.get("from") or "")
        recent_history = payload.get("recentHistory") or []

        # Resolve the row tools should read/write idempotency state on.
        # Outbound: the OutboundCall is already loaded above.
        # Inbound: find the active CallLog for this caller (created on the
        # first turn by _persist_chunk; None on the very first turn, which
        # is OK because the agent hasn't booked anything yet).
        call_context: CallContext | None
        if outbound_call is not None:
            system_prompt_override: str | None = outbound_call.dynamic_system_prompt
            tools_override: list[Any] | None = OUTBOUND_TOOL_SCHEMAS
            call_context = outbound_call
        else:
            system_prompt_override = None
            tools_override = None
            call_context = await _find_active_call_log_for_caller(
                business_id=business.id,
                call_id=call_id,
                caller_phone=caller_number,
            )

        end_call = False
        try:
            reply_text, tools_used, end_call = await asyncio.wait_for(
                run_turn(
                    business=business,
                    caller_number=caller_number,
                    caller_transcript=caller_transcript,
                    recent_history=recent_history,
                    system_prompt_override=system_prompt_override,
                    tools_override=tools_override,
                    call_context=call_context,
                ),
                timeout=BRAIN_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            log.warning("brain.run_turn timed out after %.0fs", BRAIN_TIMEOUT_S)
            reply_text, tools_used = FALLBACK_REPLY, []
        except Exception as e:
            log.exception("brain.run_turn failed")
            log_call_event(
                business.id, "agent", "turn_failed",
                {"err": f"{type(e).__name__}: {e}"},
            )
            reply_text, tools_used = FALLBACK_REPLY, []

        # Fire-and-forget persistence so the spoken reply isn't blocked on DB I/O.
        asyncio.create_task(
            _persist_chunk(
                business_id=business.id,
                call_id=call_id,
                caller_phone=caller_number,
                caller_text=caller_transcript,
                reply_text=reply_text,
                tools_used=tools_used,
                outbound_call_id=outbound_call.id if outbound_call else None,
            )
        )

        if outbound_call is not None:
            # First inbound transcript flips ringing → in_progress.
            if outbound_call.status in ("initiating", "ringing"):
                asyncio.create_task(
                    update_outbound_status(outbound_call.id, status="in_progress")
                )
            if end_call:
                asyncio.create_task(
                    _finalize_outbound_call(
                        outbound_call_id=outbound_call.id,
                        agentphone_call_id=outbound_call.agentphone_call_id,
                        end_reason="agent_hangup",
                    )
                )
                return _ack(webhook_id, {"text": reply_text, "interim": False, "end_call": True})

        return _ack(webhook_id, {"text": reply_text, "interim": False})

    if event_type == "agent.call_ended":
        asyncio.create_task(
            _persist_call_ended(
                business_id=business.id,
                call_id=call_id,
                caller_phone=str(data.get("from") or ""),
            )
        )
        if outbound_call is not None:
            asyncio.create_task(
                _finalize_outbound_call(
                    outbound_call_id=outbound_call.id,
                    agentphone_call_id=None,  # already ended remotely
                    end_reason="agentphone_event",
                )
            )
        return _ack(webhook_id, {"ok": True})

    log.warning("unknown webhook event_type=%s — returning 200", event_type)
    return _ack(webhook_id, {"ok": True})


def _ack(webhook_id: str, response: dict[str, Any]) -> dict[str, Any]:
    """Cache + return — single exit point so dedup stays in sync."""
    _record_response(webhook_id, response)
    return response


# ---------- Persistence -------------------------------------------------------


async def _persist_chunk(
    business_id: UUID,
    call_id: str | None,
    caller_phone: str,
    caller_text: str,
    reply_text: str,
    tools_used: list[str],
    outbound_call_id: UUID | None = None,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    new_chunks: list[dict[str, Any]] = []
    if caller_text:
        # On outbound calls the "caller" voice on the line is the TARGET
        # business's AI receptionist. Tag the role so the dashboard can render.
        role = "target_agent" if outbound_call_id else "caller"
        new_chunks.append({"role": role, "text": caller_text, "ts": now_iso})
    new_chunks.append({"role": "agent", "text": reply_text, "ts": now_iso})

    new_tool_records: list[dict[str, Any]] = [
        {"name": t, "ts": now_iso} for t in tools_used
    ]

    try:
        async with session_scope() as s:
            existing: CallLog | None = None
            if outbound_call_id is not None:
                outbound = await s.get(OutboundCall, outbound_call_id)
                if outbound is not None and outbound.call_log_id is not None:
                    existing = await s.get(CallLog, outbound.call_log_id)
            if existing is None:
                existing = await _find_existing_call(
                    s, business_id=business_id, call_id=call_id, caller_phone=caller_phone,
                )
            if existing is None:
                row = CallLog(
                    business_id=business_id,
                    caller_phone=caller_phone,
                    conversation_id=call_id,
                    status="in_progress",
                    transcript=new_chunks,
                    tool_calls=new_tool_records,
                    tools_used=list(dict.fromkeys(tools_used)),
                )
                s.add(row)
                await s.flush()
                if outbound_call_id is not None:
                    outbound = await s.get(OutboundCall, outbound_call_id)
                    if outbound is not None and outbound.call_log_id is None:
                        outbound.call_log_id = row.id
                        s.add(outbound)
            else:
                existing.transcript = (existing.transcript or []) + new_chunks
                existing.tool_calls = (existing.tool_calls or []) + new_tool_records
                existing.tools_used = list(
                    dict.fromkeys((existing.tools_used or []) + tools_used)
                )
                existing.status = "in_progress"
                if call_id and not existing.conversation_id:
                    existing.conversation_id = call_id
                s.add(existing)
                if outbound_call_id is not None:
                    outbound = await s.get(OutboundCall, outbound_call_id)
                    if outbound is not None and outbound.call_log_id is None:
                        outbound.call_log_id = existing.id
                        s.add(outbound)
            await s.commit()
    except Exception:
        log.exception("persist_chunk failed (call still served)")


async def _finalize_outbound_call(
    *,
    outbound_call_id: UUID,
    agentphone_call_id: str | None,
    end_reason: str,
) -> None:
    """Mark an OutboundCall completed + cancel watchdog + best-effort hangup."""
    cancel_watchdog(outbound_call_id)
    if agentphone_call_id:
        try:
            await hangup_agentphone_call(agentphone_call_id)
        except Exception:
            log.exception("hangup failed for outbound_call=%s", outbound_call_id)
    await update_outbound_status(
        outbound_call_id,
        status="completed",
        end_reason=end_reason,
        set_ended_at=True,
    )
    log_call_event(
        None, "outbound", "finalized",
        {"outbound_call_id": str(outbound_call_id), "reason": end_reason},
    )


async def _persist_call_ended(
    business_id: UUID,
    call_id: str | None,
    caller_phone: str,
) -> None:
    try:
        async with session_scope() as s:
            existing = await _find_existing_call(
                s, business_id=business_id, call_id=call_id, caller_phone=caller_phone,
            )
            if existing is None:
                return
            existing.status = "completed"
            existing.ended_at = datetime.now(timezone.utc)
            if call_id and not existing.conversation_id:
                existing.conversation_id = call_id
            s.add(existing)
            await s.commit()
    except Exception:
        log.exception("persist_call_ended failed")
