"""AgentMail — inbox per business, send, and WebSocket subscriber."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from agentmail import AgentMail, AsyncAgentMail, MessageReceivedEvent, Subscribe
from agentmail.inboxes.types.create_inbox_request import CreateInboxRequest

from app.config import settings

log = logging.getLogger(__name__)

_sync: AgentMail | None = None
_async: AsyncAgentMail | None = None


def client() -> AgentMail:
    global _sync
    if _sync is None:
        _sync = AgentMail(api_key=settings.AGENTMAIL_API_KEY)
    return _sync


def async_client() -> AsyncAgentMail:
    global _async
    if _async is None:
        _async = AsyncAgentMail(api_key=settings.AGENTMAIL_API_KEY)
    return _async


async def create_inbox(business_name: str, business_id_short: str) -> str:
    """Create an inbox for a business. Returns inbox_id (the email address)."""
    inbox = await asyncio.to_thread(
        client().inboxes.create,
        request=CreateInboxRequest(
            username=f"receptionist-{business_id_short}",
            display_name=f"{business_name} via AI Receptionist",
        ),
    )
    return inbox.inbox_id


async def send_email(
    inbox_id: str,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> str:
    """Send a transactional email from the business inbox."""
    resp = await asyncio.to_thread(
        client().inboxes.messages.send,
        inbox_id,
        to=to,
        subject=subject,
        text=text,
        html=html,
    )
    return getattr(resp, "message_id", "") or str(resp)


async def reply_to_message(
    inbox_id: str, message_id: str, text: str
) -> str:
    resp = await asyncio.to_thread(
        client().inboxes.messages.reply,
        inbox_id,
        message_id,
        text=text,
    )
    return getattr(resp, "message_id", "") or str(resp)


async def run_ws_subscriber(
    inbox_ids: list[str],
    on_message: Callable[[MessageReceivedEvent], Awaitable[None]],
    stop: asyncio.Event,
) -> None:
    """Open a WS, subscribe to message.received for the given inbox_ids,
    and dispatch each event to `on_message`. Returns when `stop` is set."""
    if not inbox_ids:
        await stop.wait()
        return

    backoff = 1.0
    while not stop.is_set():
        try:
            async with async_client().websockets.connect() as ws:
                await ws.send_subscribe(
                    Subscribe(
                        event_types=["message.received"],
                        inbox_ids=inbox_ids,
                    )
                )
                backoff = 1.0
                log.info("AgentMail WS subscribed to %d inbox(es)", len(inbox_ids))
                while not stop.is_set():
                    event = await asyncio.wait_for(ws.recv(), timeout=30)
                    if isinstance(event, MessageReceivedEvent):
                        asyncio.create_task(_safe_dispatch(on_message, event))
        except asyncio.TimeoutError:
            continue  # idle ping cycle
        except Exception as e:
            log.warning("AgentMail WS dropped: %s; reconnecting in %.1fs", e, backoff)
            try:
                await asyncio.wait_for(stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)


async def _safe_dispatch(
    on_message: Callable[[MessageReceivedEvent], Awaitable[None]],
    event: MessageReceivedEvent,
) -> None:
    try:
        await on_message(event)
    except Exception:
        log.exception("AgentMail message handler failed")
