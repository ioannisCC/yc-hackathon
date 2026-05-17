"""Outbound agent-to-agent endpoints. Used by the MCP server.

POST /agents/outbound-call — Sir's Claude (in his editor) drives this through
the MCP tool after gathering context dynamically. We:
  1. Resolve the target Business (UUID / name / phone).
  2. Synthesize the per-call system prompt with Claude Haiku.
  3. Insert OutboundCall row (status=initiating).
  4. POST to AgentPhone /v1/calls to actually dial.
  5. Arm a watchdog that hangs up after OUTBOUND_CALL_TIMEOUT_S.
  6. Return identifiers so the MCP can poll status."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.outbound_prompt import generate_outbound_system_prompt
from app.config import settings
from app.db import get_session, session_scope
from app.models import Business, CallLog, OutboundCall
from app.services.logging_svc import log_call_event
from app.services.outbound_svc import (
    arm_watchdog,
    place_agentphone_call,
    resolve_target,
    update_outbound_status,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ---------- Schemas ----------------------------------------------------------


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)


class OutboundCallRequest(StrictModel):
    target_business_query: str = Field(
        ..., description="UUID, business name fragment, or phone number."
    )
    intent: str = Field(
        ..., description="What Sir wants the agent to accomplish on the call."
    )
    caller_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Facts the agent can volunteer when asked (name, email, etc.).",
    )


class OutboundCallResponse(StrictModel):
    outbound_call_id: UUID
    status: str
    dial_target: str
    target_business_id: UUID
    target_business_name: str | None
    dashboard_url: str | None
    error: str | None


class TranscriptChunk(StrictModel):
    role: str
    text: str
    ts: str | None = None


class OutboundCallStatusResponse(StrictModel):
    outbound_call_id: UUID
    status: str
    error: str | None
    end_reason: str | None
    intent: str
    target_business_id: UUID
    target_business_name: str | None
    agentphone_call_id: str | None
    created_at: datetime
    ended_at: datetime | None
    dashboard_url: str | None
    transcript: list[TranscriptChunk]


# ---------- POST /agents/outbound-call ---------------------------------------


@router.post("/outbound-call", status_code=202, response_model=OutboundCallResponse)
async def create_outbound_call(req: OutboundCallRequest) -> OutboundCallResponse:
    if not settings.CALLER_AGENT_ID:
        raise HTTPException(status_code=500, detail="CALLER_AGENT_ID not configured")

    # 1. Resolve target.
    async with session_scope() as s:
        target = await resolve_target(s, req.target_business_query)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"no business matched query={req.target_business_query!r}",
        )
    if not target.phone_number:
        raise HTTPException(
            status_code=409,
            detail=f"business {target.id} has no phone number provisioned",
        )

    # 2. Synthesize dynamic system prompt.
    try:
        system_prompt = await generate_outbound_system_prompt(
            target_business=target,
            intent=req.intent,
            caller_context=req.caller_context,
        )
    except Exception as e:
        log.exception("outbound prompt synthesis failed")
        raise HTTPException(status_code=502, detail=f"prompt synthesis failed: {e}")

    # 3. Insert OutboundCall row.
    async with session_scope() as s:
        outbound = OutboundCall(
            target_business_id=target.id,
            caller_agent_id=settings.CALLER_AGENT_ID,
            intent=req.intent,
            caller_context=req.caller_context,
            dynamic_system_prompt=system_prompt,
            status="initiating",
        )
        s.add(outbound)
        await s.commit()
        await s.refresh(outbound)
        outbound_id = outbound.id

    log_call_event(
        target.id, "outbound", "created",
        {"outbound_call_id": str(outbound_id), "intent": req.intent},
    )

    # 4. Dial.
    call_id, dial_error = await place_agentphone_call(
        caller_agent_id=settings.CALLER_AGENT_ID,
        to_number=target.phone_number,
    )
    if dial_error is not None or call_id is None:
        await update_outbound_status(
            outbound_id, status="failed", error=dial_error or "unknown dial failure",
            set_ended_at=True, end_reason="dial_failed",
        )
        return OutboundCallResponse(
            outbound_call_id=outbound_id,
            status="failed",
            dial_target=target.phone_number,
            target_business_id=target.id,
            target_business_name=target.name,
            dashboard_url=_dashboard_url(outbound_id),
            error=dial_error,
        )

    # 5. Mark ringing + arm watchdog.
    await update_outbound_status(
        outbound_id, status="ringing", agentphone_call_id=call_id,
    )
    arm_watchdog(outbound_id)

    return OutboundCallResponse(
        outbound_call_id=outbound_id,
        status="ringing",
        dial_target=target.phone_number,
        target_business_id=target.id,
        target_business_name=target.name,
        dashboard_url=_dashboard_url(outbound_id),
        error=None,
    )


# ---------- GET /agents/outbound-call/{id} -----------------------------------


@router.get("/outbound-call/{outbound_call_id}", response_model=OutboundCallStatusResponse)
async def get_outbound_call(
    outbound_call_id: UUID, db: AsyncSession = Depends(get_session),
) -> OutboundCallStatusResponse:
    row = await db.get(OutboundCall, outbound_call_id)
    if row is None:
        raise HTTPException(status_code=404, detail="outbound call not found")

    target_name: str | None = None
    target = await db.get(Business, row.target_business_id)
    if target is not None:
        target_name = target.name

    chunks: list[TranscriptChunk] = []
    if row.call_log_id is not None:
        log_row = await db.get(CallLog, row.call_log_id)
        if log_row is not None:
            for raw in (log_row.transcript or []):
                if not isinstance(raw, dict):
                    continue
                chunks.append(
                    TranscriptChunk(
                        role=str(raw.get("role", "")),
                        text=str(raw.get("text", "")),
                        ts=raw.get("ts"),
                    )
                )

    return OutboundCallStatusResponse(
        outbound_call_id=row.id,
        status=row.status,
        error=row.error,
        end_reason=row.end_reason,
        intent=row.intent,
        target_business_id=row.target_business_id,
        target_business_name=target_name,
        agentphone_call_id=row.agentphone_call_id,
        created_at=row.created_at,
        ended_at=row.ended_at,
        dashboard_url=_dashboard_url(row.id),
        transcript=chunks,
    )


# ---------- helpers ----------------------------------------------------------


def _dashboard_url(outbound_call_id: UUID) -> str | None:
    base = (settings.PUBLIC_BACKEND_URL or "").rstrip("/")
    if not base:
        return None
    return f"{base}/agents/outbound-call/{outbound_call_id}"
