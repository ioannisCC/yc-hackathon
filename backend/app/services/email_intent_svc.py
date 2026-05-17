"""Classify an inbound email reply as cancel / reschedule / confirm / other,
then dispatch the corresponding Cal.com action."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from agentmail import MessageReceivedEvent
from anthropic import AsyncAnthropic
from sqlmodel import select

from app.config import settings
from app.db import session_scope
from app.models import Business
from app.services import calcom_svc, mail_svc
from app.services.logging_svc import log_call_event

log = logging.getLogger(__name__)

Intent = Literal["cancel", "reschedule", "confirm", "other"]

CLASSIFIER_SYSTEM = (
    "You read one email reply about a calendar booking and classify the sender's intent. "
    "Reply with ONLY a JSON object: "
    '{"intent": "cancel"|"reschedule"|"confirm"|"other", '
    '"new_start_iso": "<iso or null>", "reason": "<short>"}.'
)

_anthropic: AsyncAnthropic | None = None


def _client() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic


async def classify(text: str) -> dict[str, Any]:
    resp = await _client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": text[:2000]}],
    )
    raw = "".join(getattr(b, "text", "") for b in resp.content)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"intent": "other", "reason": "no json"}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"intent": "other", "reason": "bad json"}


def _extract_booking_uid_from_subject(subject: str | None) -> str | None:
    # Booking-confirmation subjects we send don't yet carry the uid;
    # Cal.com replies typically include something like "[uid:abc123]" — fallback to None.
    if not subject:
        return None
    m = re.search(r"\[uid:([^\]]+)\]", subject)
    return m.group(1) if m else None


async def handle_inbox_event(event: MessageReceivedEvent) -> None:
    msg = event.message
    inbox_id = getattr(msg, "inbox_id", None)
    text = getattr(msg, "text", "") or ""
    sender = getattr(msg, "from_", "") or getattr(msg, "from_address", "")
    subject = getattr(msg, "subject", None)
    message_id = getattr(msg, "message_id", None)

    if not inbox_id or not text:
        return

    async with session_scope() as s:
        biz = (
            await s.execute(
                select(Business).where(Business.agentmail_inbox_id == inbox_id)
            )
        ).scalar_one_or_none()

    if biz is None:
        log.info("inbound email for unknown inbox %s", inbox_id)
        return

    intent_data = await classify(text)
    intent: Intent = intent_data.get("intent", "other")
    log_call_event(
        biz.id, "system", "email_intent",
        {"intent": intent, "from": sender, "subject": subject},
    )

    booking_uid = _extract_booking_uid_from_subject(subject)
    reply_text: str | None = None

    if intent == "cancel" and booking_uid:
        try:
            await calcom_svc.cancel_booking(booking_uid, "Caller requested via email")
            reply_text = "Your appointment has been cancelled. Reply if you'd like to rebook."
        except Exception as e:
            reply_text = f"Sorry, I couldn't cancel that booking: {e}"
    elif intent == "reschedule" and booking_uid and intent_data.get("new_start_iso"):
        try:
            await calcom_svc.reschedule_booking(
                booking_uid, intent_data["new_start_iso"]
            )
            reply_text = f"Your appointment has been moved to {intent_data['new_start_iso']}."
        except Exception as e:
            reply_text = f"Sorry, I couldn't reschedule that booking: {e}"
    elif intent == "confirm":
        reply_text = "Thanks for confirming — see you then!"

    if reply_text and message_id:
        try:
            await mail_svc.reply_to_message(inbox_id, message_id, reply_text)
        except Exception:
            log.exception("failed to send email reply")
