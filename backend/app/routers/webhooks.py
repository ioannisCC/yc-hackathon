"""AgentPhone webhook — verify signature, run Claude tool loop, stream NDJSON.

AgentPhone uses GitHub-style HMAC-SHA256, NOT Standard Webhooks. The
verifier below runs all 9 plausible (secret-format × payload-shape)
combinations and accepts on any match, logging which combo won so we
can collapse to a single one once observed in production logs.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
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


def verify_agentphone_webhook(
    raw_body: bytes, headers: dict[str, str], secret_full: str
) -> bool:
    """Try every plausible (secret, payload) pair until one matches.

    Logs each attempt's outcome and the winning combo so we can collapse
    this to a single canonical pair once we've observed real traffic."""
    sig_header = headers.get("x-webhook-signature", "")
    ts = headers.get("x-webhook-timestamp", "")
    wh_id = headers.get("x-webhook-id", "")

    if not sig_header.startswith("sha256="):
        print(
            f"[VERIFY] Missing or unexpected sig header: {sig_header!r}",
            file=sys.stderr, flush=True,
        )
        return False
    provided_hex = sig_header.removeprefix("sha256=")

    try:
        b64_key = base64.urlsafe_b64decode(
            secret_full.removeprefix("whsec_") + "==="
        )
    except Exception as e:
        print(f"[VERIFY] base64 decode failed: {e}", file=sys.stderr, flush=True)
        b64_key = b""

    secret_variants = {
        "full": secret_full.encode(),
        "stripped": secret_full.removeprefix("whsec_").encode(),
        "b64_urlsafe": b64_key,
    }
    payload_variants = {
        "body_only": raw_body,
        "ts_dot_body": f"{ts}.".encode() + raw_body,
        "id_dot_ts_dot_body": f"{wh_id}.{ts}.".encode() + raw_body,
    }

    for s_name, s_key in secret_variants.items():
        if not s_key:
            continue
        for p_name, payload in payload_variants.items():
            computed = hmac.new(s_key, payload, hashlib.sha256).hexdigest()
            match = hmac.compare_digest(computed, provided_hex)
            print(
                f"[VERIFY] secret={s_name} payload={p_name} match={match}",
                file=sys.stderr, flush=True,
            )
            if match:
                print(
                    f"[VERIFY] *** WINNER: secret={s_name} payload={p_name} ***",
                    file=sys.stderr, flush=True,
                )
                return True
    return False


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

        # Checkpoint 4: 9-way HMAC discovery
        if not verify_agentphone_webhook(raw_body, headers_dict, secret):
            raise HTTPException(status_code=401, detail="invalid signature")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as e:
            print(f"[4] JSON DECODE FAILED: {e}", file=sys.stderr, flush=True)
            raise HTTPException(status_code=400, detail="invalid json")
        print(
            f"[4] PAYLOAD type={payload.get('type', payload.get('event', 'unknown'))}",
            file=sys.stderr, flush=True,
        )

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
