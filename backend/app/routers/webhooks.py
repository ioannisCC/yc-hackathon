"""AgentPhone webhook — verify signature, run Claude tool loop, stream NDJSON."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from standardwebhooks import Webhook
from standardwebhooks.webhooks import WebhookVerificationError

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
    # Raw body MUST be read before FastAPI tries to parse JSON — Standard
    # Webhooks signs the exact bytes the sender transmitted.
    raw_body = await request.body()

    # DIAGNOSTIC: dump exactly what AgentPhone is sending so we can stop guessing
    # the verification protocol. Remove once the 401 mystery is resolved.
    log.info(
        "agentphone_webhook_inbound headers=%s body_len=%d body_first_500=%r",
        {k.lower(): v for k, v in request.headers.items()},
        len(raw_body),
        raw_body[:500],
    )

    secret = settings.AGENTPHONE_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=500, detail="webhook secret not configured")
    try:
        # AgentPhone follows the Standard Webhooks spec (whsec_ prefix,
        # webhook-id / webhook-timestamp / webhook-signature headers).
        # standardwebhooks does the base64-keyed HMAC + tolerance check.
        payload = Webhook(secret).verify(raw_body, dict(request.headers))
        log.info("agentphone_webhook_verified ok=True")
    except WebhookVerificationError as e:
        log.error("agentphone_webhook_verify_failed reason=%s", str(e))
        raise HTTPException(status_code=401, detail="invalid signature")

    data = payload.get("data") or {}
    to_number = data.get("to_number") or ""
    from_number = data.get("from_number") or ""
    caller_text = data.get("message") or ""
    conversation_id = data.get("conversation_id")

    business = (
        await db.execute(select(Business).where(Business.phone_number == to_number))
    ).scalar_one_or_none()
    if business is None:
        raise HTTPException(status_code=404, detail=f"no business for {to_number}")

    # Reconstruct history from recent_history (AgentPhone's rolling context).
    history: list[dict[str, Any]] = []
    for item in payload.get("recent_history") or []:
        role = "assistant" if item.get("role") == "agent" else "user"
        text = item.get("message") or item.get("text") or ""
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
                conversation_id=conversation_id,
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
