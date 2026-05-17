"""AgentPhone webhook — verify signature, run Claude tool loop, stream NDJSON."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from agentphone import WebhookEvent, WebhookVerificationError, construct_event
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agent.brain import FALLBACK_REPLY, run_turn
from app.config import settings
from app.db import get_session, session_scope
from app.models import Business, CallLog
from app.services.logging_svc import log_call_event

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

INTERIM_FILLER = "One moment."


def _ndjson(chunk: dict[str, Any]) -> bytes:
    return (json.dumps(chunk) + "\n").encode()


@router.post("/agentphone")
async def agentphone_webhook(
    request: Request, db: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    secret = settings.AGENTPHONE_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=500, detail="webhook secret not configured")
    try:
        event: WebhookEvent = construct_event(body, signature, secret)
    except WebhookVerificationError:
        raise HTTPException(status_code=401, detail="invalid signature")

    data = event.data
    to_number = data.to_number
    from_number = data.from_number
    caller_text = data.message or ""

    business = (
        await db.execute(select(Business).where(Business.phone_number == to_number))
    ).scalar_one_or_none()
    if business is None:
        raise HTTPException(status_code=404, detail=f"no business for {to_number}")

    # Reconstruct history from recent_history (AgentPhone's rolling context).
    history: list[dict[str, Any]] = []
    for item in event.recent_history or []:
        role = "assistant" if getattr(item, "role", "") == "agent" else "user"
        text = getattr(item, "message", "") or getattr(item, "text", "")
        if text:
            history.append({"role": role, "content": text})

    async def stream() -> AsyncIterator[bytes]:
        yield _ndjson({"text": INTERIM_FILLER, "interim": True})
        try:
            reply, tools_used = await asyncio.wait_for(
                run_turn(business, from_number, caller_text, history),
                timeout=25,
            )
        except Exception as e:
            log.exception("voice turn failed")
            log_call_event(
                business.id, "agent", "turn_failed",
                {"err": f"{type(e).__name__}: {e}"},
            )
            reply, tools_used = FALLBACK_REPLY, []
        yield _ndjson({"text": reply, "interim": False})
        # Persist transcript turn out-of-band so streaming isn't blocked.
        asyncio.create_task(
            _persist_turn(
                business_id=business.id,
                caller_phone=from_number,
                conversation_id=data.conversation_id,
                caller_text=caller_text,
                reply=reply,
                tools_used=tools_used,
            )
        )

    return StreamingResponse(stream(), media_type="application/x-ndjson")


async def _persist_turn(
    business_id: UUID,
    caller_phone: str,
    conversation_id: str | None,
    caller_text: str,
    reply: str,
    tools_used: list[str],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    new_turns = [
        {"role": "caller", "text": caller_text, "ts": now},
        {"role": "agent", "text": reply, "ts": now, "tools": tools_used},
    ]
    async with session_scope() as s:
        existing = None
        if conversation_id:
            existing = (
                await s.execute(
                    select(CallLog).where(CallLog.conversation_id == conversation_id)
                )
            ).scalar_one_or_none()
        if existing is None:
            row = CallLog(
                business_id=business_id,
                caller_phone=caller_phone,
                conversation_id=conversation_id,
                transcript=new_turns,
                tools_used=list(tools_used),
            )
            s.add(row)
        else:
            existing.transcript = (existing.transcript or []) + new_turns
            existing.tools_used = list(
                dict.fromkeys((existing.tools_used or []) + tools_used)
            )
            s.add(existing)
        await s.commit()
