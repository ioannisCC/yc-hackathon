"""Call detail + SSE stream endpoints for the live dashboard."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db import get_session, session_scope
from app.models import CallLog

log = logging.getLogger(__name__)
router = APIRouter(prefix="/calls", tags=["calls"])

POLL_INTERVAL_S = 0.5
HEARTBEAT_S = 15
STREAM_HARD_TIMEOUT_S = 60 * 30  # never hold an SSE longer than 30 min


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)


class CallDetail(StrictModel):
    id: UUID
    business_id: UUID
    caller_phone: str
    caller_name: str | None
    status: str
    outcome: str | None
    summary: str | None
    started_at: datetime
    ended_at: datetime | None
    transcript: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


@router.get("/{call_id}", response_model=CallDetail)
async def get_call(
    call_id: UUID, db: AsyncSession = Depends(get_session),
) -> CallDetail:
    row = await db.get(CallLog, call_id)
    if row is None:
        raise HTTPException(status_code=404, detail="call not found")
    return CallDetail(
        id=row.id,
        business_id=row.business_id,
        caller_phone=row.caller_phone,
        caller_name=row.caller_name,
        status=row.status,
        outcome=row.outcome,
        summary=row.summary,
        started_at=row.started_at,
        ended_at=row.ended_at,
        transcript=list(row.transcript or []),
        tool_calls=list(row.tool_calls or []),
    )


@router.get("/{call_id}/stream")
async def stream_call(call_id: UUID) -> EventSourceResponse:
    """SSE stream of transcript chunks, tool calls, and status changes.

    Implementation: poll the row every 500ms; emit any new transcript entries,
    new tool calls, or status changes since last tick. sse-starlette handles
    heartbeats (ping=HEARTBEAT_S) and client reconnection."""

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        last_transcript_len = 0
        last_tool_len = 0
        last_status: str | None = None
        started = asyncio.get_event_loop().time()

        while True:
            # Hard cap so a runaway client can't pin a worker forever
            if asyncio.get_event_loop().time() - started > STREAM_HARD_TIMEOUT_S:
                yield {"event": "close", "data": "timeout"}
                return

            try:
                async with session_scope() as s:
                    call = await s.get(CallLog, call_id)
                    if call is None:
                        yield {"event": "error", "data": "call_not_found"}
                        return

                    transcript = list(call.transcript or [])
                    tools = list(call.tool_calls or [])
                    status = call.status
            except Exception as e:
                log.exception("stream_call db read failed")
                yield {"event": "error", "data": f"{type(e).__name__}"}
                await asyncio.sleep(POLL_INTERVAL_S * 2)
                continue

            for chunk in transcript[last_transcript_len:]:
                yield {"event": "transcript", "data": json.dumps(chunk, default=str)}
            last_transcript_len = len(transcript)

            for tc in tools[last_tool_len:]:
                yield {"event": "tool_call", "data": json.dumps(tc, default=str)}
            last_tool_len = len(tools)

            if status != last_status:
                yield {"event": "status", "data": status}
                last_status = status

            if status in ("completed", "failed"):
                yield {"event": "close", "data": status}
                return

            await asyncio.sleep(POLL_INTERVAL_S)

    return EventSourceResponse(event_generator(), ping=HEARTBEAT_S)
