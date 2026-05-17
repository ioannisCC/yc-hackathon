"""Dynamic outbound system prompt synthesis.

When Sir asks Claude (via MCP) to call a business, we don't ship a static
caller prompt — we synthesize one with Claude Haiku that bakes in Sir's
context, the intent, and the target business. The synthesized prompt is
stored on the OutboundCall row and used by brain.run_turn() ONLY for that
specific outbound call (routed by caller_agent_id in the webhook)."""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.models import Business

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024

_META_PROMPT = """You are a prompt engineer. Generate a SYSTEM PROMPT for a voice
AI agent that will place a phone call on behalf of a human (their name and
relevant facts are in CALLER_CONTEXT). The agent will speak with ANOTHER AI
receptionist on the line. Two AI agents, agent-to-agent.

Output ONLY the system prompt body — no preamble, no markdown headings, no
code fences. The prompt must:

1. Open with the agent's identity and that it is calling on behalf of the
   caller. Use the caller's name from CALLER_CONTEXT if present.
2. State the INTENT clearly and concisely so the receptionist understands
   the purpose of the call within the first turn.
3. Bake every key from CALLER_CONTEXT into the prompt as a fact the agent
   can volunteer when asked. Do not invent facts that aren't present.
4. Tell the agent it is on a live phone call talking to another AI:
   - keep replies short and conversational (one or two sentences per turn)
   - skip pleasantries, get to the point
   - answer the receptionist's questions directly from CALLER_CONTEXT
   - if the receptionist asks for something not in CALLER_CONTEXT, say so
     honestly rather than fabricating
5. Tell the agent that the RECEIVING agent is the one with booking tools.
   The caller's job is purely to provide info and confirm the booking.
6. End-of-call protocol: When the booking is confirmed (or you're told it's
   not possible), say a brief warm farewell and invoke the end_call tool in
   the SAME turn. Do not stay on the line after the goal is achieved.
7. List the single tool the agent has: end_call(farewell_message).

The TARGET business info is provided so the agent can reference it by name
("Hi, I'm calling Code Salon to book a haircut..."). Do not let the agent
quote prices/hours of the target — that's the receptionist's job.

CALLER_CONTEXT and TARGET and INTENT are below. Return only the system
prompt body."""


_client: AsyncAnthropic | None = None


def _anthropic() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def generate_outbound_system_prompt(
    *,
    target_business: Business,
    intent: str,
    caller_context: dict[str, Any],
) -> str:
    """Synthesize the dynamic system prompt for the outbound caller agent."""
    target_summary = {
        "name": target_business.name,
        "phone_number": target_business.phone_number,
        "timezone": target_business.timezone,
    }

    user_block = (
        f"TARGET BUSINESS:\n{json.dumps(target_summary, indent=2)}\n\n"
        f"INTENT:\n{intent}\n\n"
        f"CALLER_CONTEXT:\n{json.dumps(caller_context, indent=2, default=str)}"
    )

    log.info(
        "synthesizing outbound prompt for target=%s intent=%r context_keys=%s",
        target_business.id, intent, list(caller_context.keys()),
    )

    resp = await _anthropic().messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_META_PROMPT,
        messages=[{"role": "user", "content": user_block}],
    )
    text = "".join(
        getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
    ).strip()
    if not text:
        raise RuntimeError("outbound prompt synthesis returned empty text")
    return text


__all__ = ["generate_outbound_system_prompt"]
