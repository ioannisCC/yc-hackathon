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

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

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

_AGENTPHONE_API_BASE = "https://api.agentphone.ai/v1"
_TERMINAL_STATUSES = ("completed", "failed")

# SSE stream knobs — outbound calls are short by design.
_SSE_POLL_INTERVAL_S = 0.5
_SSE_HEARTBEAT_S = 15
_SSE_HARD_TIMEOUT_S = 60 * 5  # 5 min cap

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


# ---------- GET /agents/outbound-call/{id}/transcript ------------------------


class OutboundTranscriptResponse(StrictModel):
    outbound_call_id: UUID
    status: str
    ended_at: datetime | None
    end_reason: str | None
    intent: str
    target_business_name: str | None
    transcript: list[TranscriptChunk]


@router.get(
    "/outbound-call/{outbound_call_id}/transcript",
    response_model=OutboundTranscriptResponse,
)
async def get_outbound_transcript(
    outbound_call_id: UUID, db: AsyncSession = Depends(get_session),
) -> OutboundTranscriptResponse:
    """Bootstrap payload for the frontend — small, no system_prompt, no
    agentphone_call_id, no caller_context. Pair with the SSE stream for live
    updates after first paint."""
    row = await db.get(OutboundCall, outbound_call_id)
    if row is None:
        raise HTTPException(status_code=404, detail="outbound call not found")

    target_name: str | None = None
    target = await db.get(Business, row.target_business_id)
    if target is not None:
        target_name = target.name

    chunks = _load_transcript_chunks(
        await _load_call_log(db, row.call_log_id) if row.call_log_id else None
    )

    return OutboundTranscriptResponse(
        outbound_call_id=row.id,
        status=row.status,
        ended_at=row.ended_at,
        end_reason=row.end_reason,
        intent=row.intent,
        target_business_name=target_name,
        transcript=chunks,
    )


# ---------- GET /agents/outbound-call/{id}/stream ----------------------------


@router.get("/outbound-call/{outbound_call_id}/stream")
async def stream_outbound_call(outbound_call_id: UUID) -> EventSourceResponse:
    """SSE stream for the agent-to-agent call view.

    Mirrors GET /calls/{id}/stream but sources transcript from the linked
    CallLog and status from the OutboundCall row. Polls every 500ms, sends
    a 15s heartbeat, hard-closes after 5 minutes (outbound calls have a
    180s watchdog so this is generous)."""

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        last_transcript_len = 0
        last_status: str | None = None
        started = asyncio.get_event_loop().time()

        while True:
            if asyncio.get_event_loop().time() - started > _SSE_HARD_TIMEOUT_S:
                yield {"event": "close", "data": "timeout"}
                return

            try:
                async with session_scope() as s:
                    call = await s.get(OutboundCall, outbound_call_id)
                    if call is None:
                        yield {"event": "error", "data": "outbound_call_not_found"}
                        return
                    log_row = (
                        await s.get(CallLog, call.call_log_id)
                        if call.call_log_id else None
                    )
                    transcript = list((log_row.transcript or []) if log_row else [])
                    status = call.status
                    end_reason = call.end_reason
                    ended_at = call.ended_at
            except Exception as e:
                log.exception("stream_outbound_call db read failed")
                yield {"event": "error", "data": type(e).__name__}
                await asyncio.sleep(_SSE_POLL_INTERVAL_S * 2)
                continue

            for chunk in transcript[last_transcript_len:]:
                if not isinstance(chunk, dict):
                    continue
                yield {
                    "event": "transcript",
                    "data": json.dumps(
                        {
                            "role": chunk.get("role"),
                            "text": chunk.get("text"),
                            "ts": chunk.get("ts"),
                        },
                        default=str,
                    ),
                }
            last_transcript_len = len(transcript)

            if status != last_status:
                payload: dict[str, Any] = {"status": status}
                if end_reason is not None:
                    payload["end_reason"] = end_reason
                if ended_at is not None:
                    payload["ended_at"] = ended_at.isoformat()
                yield {"event": "status", "data": json.dumps(payload, default=str)}
                last_status = status

            if status in _TERMINAL_STATUSES:
                yield {"event": "close", "data": status}
                return

            await asyncio.sleep(_SSE_POLL_INTERVAL_S)

    return EventSourceResponse(event_generator(), ping=_SSE_HEARTBEAT_S)


# ---------- GET /agents/outbound-call/{id}/recording -------------------------


@router.get("/outbound-call/{outbound_call_id}/recording")
async def get_outbound_recording(outbound_call_id: UUID) -> StreamingResponse:
    """Proxy AgentPhone's recording so the frontend can <audio src="..."> it
    without ever seeing AGENTPHONE_API_KEY. Streams audio/wav back; 503 with
    Retry-After=30 if AgentPhone says the recording is still being processed."""
    async with session_scope() as s:
        row = await s.get(OutboundCall, outbound_call_id)
        if row is None:
            raise HTTPException(status_code=404, detail="outbound call not found")
        ap_call_id = row.agentphone_call_id

    if not ap_call_id:
        raise HTTPException(
            status_code=503,
            detail="call has no agentphone_call_id yet",
            headers={"Retry-After": "30"},
        )
    if not settings.AGENTPHONE_API_KEY:
        raise HTTPException(status_code=500, detail="AGENTPHONE_API_KEY not configured")

    upstream_url = f"{_AGENTPHONE_API_BASE}/calls/{ap_call_id}/recording"
    headers = {"Authorization": f"Bearer {settings.AGENTPHONE_API_KEY}"}

    # Pre-flight: open the upstream stream, branch on status BEFORE FastAPI
    # commits to a StreamingResponse status code. If we're good, hand the
    # already-open client + response to the streamer to drain.
    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    stream_cm = client.stream("GET", upstream_url, headers=headers)
    try:
        upstream = await stream_cm.__aenter__()
    except httpx.HTTPError as e:
        await client.aclose()
        log.exception("recording upstream connect failed")
        raise HTTPException(
            status_code=503,
            detail=f"agentphone unreachable: {e}",
            headers={"Retry-After": "30"},
        )

    async def _cleanup() -> None:
        try:
            await stream_cm.__aexit__(None, None, None)
        finally:
            await client.aclose()

    if upstream.status_code == 404:
        log.info(
            "recording 404 from agentphone for call=%s (still processing?)",
            ap_call_id,
        )
        await _cleanup()
        raise HTTPException(
            status_code=503,
            detail="recording not ready",
            headers={"Retry-After": "30"},
        )
    if not (200 <= upstream.status_code < 300):
        body = await upstream.aread()
        status_code = upstream.status_code
        await _cleanup()
        log.warning(
            "recording upstream %d for call=%s body=%r",
            status_code, ap_call_id, body[:300],
        )
        raise HTTPException(
            status_code=502,
            detail=f"agentphone returned {status_code}",
        )

    async def streamer() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            await _cleanup()

    return StreamingResponse(
        streamer(),
        media_type="audio/wav",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": (
                f'inline; filename="outbound-call-{outbound_call_id}.wav"'
            ),
        },
    )


# ---------- helpers ----------------------------------------------------------


async def _load_call_log(db: AsyncSession, call_log_id: UUID | None) -> CallLog | None:
    if call_log_id is None:
        return None
    return await db.get(CallLog, call_log_id)


def _load_transcript_chunks(log_row: CallLog | None) -> list[TranscriptChunk]:
    chunks: list[TranscriptChunk] = []
    if log_row is None:
        return chunks
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
    return chunks


def _dashboard_url(outbound_call_id: UUID) -> str | None:
    base = (settings.PUBLIC_BACKEND_URL or "").rstrip("/")
    if not base:
        return None
    return f"{base}/agents/outbound-call/{outbound_call_id}"
