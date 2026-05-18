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
# The dynamic part needs to fit roughly 700 chars so the full prompt
# (dynamic + 1208-char principles) stays well under 2000 chars. Capping
# max_tokens here is belt-and-braces in case Haiku ignores the explicit
# char limit in the meta-prompt.
_MAX_TOKENS = 300
_DYNAMIC_CHAR_BUDGET = 700


# Anti-drift principles appended verbatim to every synthesized prompt.
# These are non-negotiable, so we keep them in Python rather than asking
# Haiku to reproduce them every time. Empirically, when call-handling
# rules are left to the meta-LLM, it paraphrases or drops bullets —
# both of which have triggered the dup-booking + overstaying-the-call
# failure modes on stage. Hard-coding the principles fixes that.
_ANTI_DRIFT_PRINCIPLES = """\
HOW YOU HANDLE THE CALL

You're calling on someone's behalf — be warm but direct, like a thoughtful \
personal assistant. One or two sentences per turn. State who you are and \
what you need up front. When the receiving agent asks for details, give \
them straight from your context. If asked for something not in your \
context, say "I'll have to check with [name] on that" — never invent.

WHEN THE GOAL IS DONE, END THE CALL

The moment the receiver confirms the booking ("you're booked", \
"confirmation sent", "you're all set", "I'll send the email"), you're \
done. Say a quick "thanks, have a great day" and invoke end_call in the \
same turn. Don't re-confirm, don't ask follow-ups, don't engage further. \
The longer you stay on the line after success, the more room for the \
conversation to drift.

If 4+ turns pass without forward progress (receiver looping, agent \
confusion, tools failing), wrap up politely: "I'll have to call back, \
thanks for your time" + end_call.

Phone audio is noisy. If the receiver's words don't make sense, ask once \
to clarify. If still unclear, advance with what you have or end_call.

Don't repeat yourself. If you're about to say the same thing twice — stop \
and either advance or end."""


_META_PROMPT = """You are a prompt engineer. Generate a SYSTEM PROMPT for a voice
AI agent that will place a phone call on behalf of a human (their name and
relevant facts are in CALLER_CONTEXT). The agent will speak with ANOTHER AI
receptionist on the line. Two AI agents, agent-to-agent.

Output ONLY the system prompt body — no preamble, no markdown headings, no
code fences. Keep it VERY brief — STRICT MAXIMUM 700 characters. Aim for
4-6 short sentences total. The prompt must:

1. Open with the agent's identity and that it is calling on behalf of the
   caller. Use the caller's name from CALLER_CONTEXT if present.
2. State the INTENT clearly and concisely so the receptionist understands
   the purpose of the call within the first turn.
3. Bake every key from CALLER_CONTEXT into the prompt as a fact the agent
   can volunteer when asked. Do not invent facts that aren't present.
4. Mention that the RECEIVING agent owns the booking tools — the caller's
   job is to provide info and confirm.
5. Mention the single tool the agent has: end_call(farewell_message).

The TARGET business info is provided so the agent can reference it by name
("Hi, I'm calling Code Salon to book a haircut..."). Do not let the agent
quote prices/hours of the target — that's the receptionist's job.

IMPORTANT: Do NOT include call-handling rules, end-of-call protocol,
brevity rules, drift-handling, or "HOW YOU HANDLE" / "WHEN THE GOAL IS
DONE" sections — these are appended verbatim AFTER your output and must
not be duplicated or paraphrased. Focus only on identity, intent, facts,
and tool list.

CALLER_CONTEXT and TARGET and INTENT are below. Return only the dynamic
system prompt body."""


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
    dynamic_part = "".join(
        getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
    ).strip()
    if not dynamic_part:
        raise RuntimeError("outbound prompt synthesis returned empty text")

    # Defensive: if Haiku ignored the explicit char budget, trim on a
    # sentence boundary so the total fits inside _TOTAL_PROMPT_BUDGET. The
    # principles must always survive verbatim.
    if len(dynamic_part) > _DYNAMIC_CHAR_BUDGET:
        log.warning(
            "synthesized dynamic part %d chars > budget %d — truncating",
            len(dynamic_part), _DYNAMIC_CHAR_BUDGET,
        )
        truncated = dynamic_part[:_DYNAMIC_CHAR_BUDGET]
        last_period = truncated.rfind(". ")
        dynamic_part = truncated[: last_period + 1] if last_period > 0 else truncated

    # Append the anti-drift principles verbatim. They're guaranteed to be
    # present in the final prompt regardless of what Haiku decides to do.
    return f"{dynamic_part}\n\n{_ANTI_DRIFT_PRINCIPLES}"


__all__ = ["generate_outbound_system_prompt", "_ANTI_DRIFT_PRINCIPLES"]
