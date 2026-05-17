"""AgentPhone webhook — verify signature, run Claude tool loop, stream NDJSON."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
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
    # NUCLEAR DIAGNOSTIC — print() to stderr bypasses uvicorn/loguru filters
    # and Railway captures stderr unconditionally. flush=True so nothing
    # is buffered when the handler raises.
    print("==== AGENTPHONE WEBHOOK START ====", file=sys.stderr, flush=True)
    try:
        # Checkpoint 1: headers
        headers_dict = {k.lower(): v for k, v in request.headers.items()}
        print(f"[1] HEADERS: {headers_dict}", file=sys.stderr, flush=True)

        # Checkpoint 2: body read
        try:
            raw_body = await request.body()
            print(f"[2] BODY len={len(raw_body)}", file=sys.stderr, flush=True)
            print(f"[2] BODY first 1000: {raw_body[:1000]!r}", file=sys.stderr, flush=True)
        except Exception as e:
            print(
                f"[2] BODY READ FAILED: {type(e).__name__}: {e}",
                file=sys.stderr, flush=True,
            )
            raise

        # Checkpoint 3: secret loaded
        secret = settings.AGENTPHONE_WEBHOOK_SECRET
        print(
            f"[3] SECRET prefix={secret[:10]!r} len={len(secret)}",
            file=sys.stderr, flush=True,
        )
        if not secret:
            raise HTTPException(status_code=500, detail="webhook secret not configured")

        # Checkpoint 4: attempt verify (lowercased headers first, then original casing)
        try:
            wh = Webhook(secret)
            payload = wh.verify(raw_body, headers_dict)
            print(
                f"[4] VERIFY OK payload_type={payload.get('type', payload.get('event', 'unknown'))}",
                file=sys.stderr, flush=True,
            )
        except WebhookVerificationError as e:
            print(f"[4] VERIFY FAILED: {e}", file=sys.stderr, flush=True)
            print(f"[4] VERIFY FAILED type: {type(e).__name__}", file=sys.stderr, flush=True)
            # Casing fallback — in case the SDK is case-sensitive on the headers dict
            try:
                wh.verify(raw_body, dict(request.headers))
                print("[4b] VERIFY with original casing OK", file=sys.stderr, flush=True)
            except WebhookVerificationError as e2:
                print(
                    f"[4b] VERIFY with original casing also failed: {e2}",
                    file=sys.stderr, flush=True,
                )
            raise HTTPException(status_code=401, detail="invalid signature")
        except Exception as e:
            print(
                f"[4] UNEXPECTED EXCEPTION: {type(e).__name__}: {e}",
                file=sys.stderr, flush=True,
            )
            raise

        # ---- existing handler logic continues here -------------------------
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

    except HTTPException:
        raise
    except Exception as e:
        print(
            f"[X] HANDLER CRASHED: {type(e).__name__}: {e}",
            file=sys.stderr, flush=True,
        )
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    finally:
        print("==== AGENTPHONE WEBHOOK END ====", file=sys.stderr, flush=True)


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
