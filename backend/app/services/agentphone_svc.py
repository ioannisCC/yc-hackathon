"""AgentPhone wrapper — agents, numbers, webhook."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from agentphone import AgentPhone

from app.config import settings

log = logging.getLogger(__name__)

_client: AgentPhone | None = None


def client() -> AgentPhone:
    global _client
    if _client is None:
        _client = AgentPhone(api_key=settings.AGENTPHONE_API_KEY)
    return _client


@dataclass
class ProvisionResult:
    agent_id: str
    number_id: str
    phone_number: str


async def ensure_account_webhook() -> str:
    """Idempotently set the account-level webhook URL and return the secret.

    Caller should paste the returned secret into AGENTPHONE_WEBHOOK_SECRET in .env.
    """
    if not settings.PUBLIC_BACKEND_URL:
        raise RuntimeError("PUBLIC_BACKEND_URL must be set before configuring webhook")
    url = f"{settings.PUBLIC_BACKEND_URL.rstrip('/')}/webhooks/agentphone"
    webhook = await asyncio.to_thread(client().webhooks.set, url=url)
    secret = getattr(webhook, "secret", "")
    if secret and secret != settings.AGENTPHONE_WEBHOOK_SECRET:
        log.warning(
            "AgentPhone webhook secret changed. Update .env AGENTPHONE_WEBHOOK_SECRET=%s",
            secret,
        )
    return secret


async def provision_for_business(
    business_name: str, system_prompt: str
) -> ProvisionResult:
    """Create an agent, attach a US number, return identifiers.

    voice_mode MUST be "webhook" or "hosted". Webhook routes incoming
    transcripts to our FastAPI /webhooks/agentphone so the Claude tool
    loop can run; hosted mode keeps reasoning on the AgentPhone side
    with no tool access."""
    agent_payload = {
        "name": business_name[:60],
        "system_prompt": system_prompt,
        "begin_message": f"Thanks for calling {business_name}, how can I help?",
        "voice_mode": "webhook",
    }
    # Log everything except the (long) system prompt so a future validation
    # error surfaces the exact body without flooding logs.
    log.info(
        "agentphone agents.create payload: %s",
        {**agent_payload, "system_prompt": f"<{len(system_prompt)} chars>"},
    )
    agent = await asyncio.to_thread(client().agents.create, **agent_payload)
    number = await asyncio.to_thread(
        client().numbers.buy, country="US", agent_id=agent.id
    )
    return ProvisionResult(
        agent_id=agent.id,
        number_id=number.id,
        phone_number=number.phone_number,
    )
