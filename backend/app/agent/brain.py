"""Claude Haiku 4.5 tool-call loop for one voice turn."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.agent.tools import DISPATCH, TOOL_SCHEMAS, CallContext, run_tool
from app.config import settings
from app.models import Business
from app.services.logging_svc import log_call_event

log = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
MAX_TOOL_ITERATIONS = 5
FALLBACK_REPLY = (
    "I'm sorry, I'm having trouble with that right now — "
    "would you like me to take a message?"
)

_client: AsyncAnthropic | None = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _text_from_blocks(blocks: list[Any]) -> str:
    return "".join(
        getattr(b, "text", "") for b in blocks if getattr(b, "type", "") == "text"
    )


def _convert_recent_history(recent_history: list[Any]) -> list[dict[str, Any]]:
    """AgentPhone sends history as [{role: 'agent'|'user', content: str}, ...].
    Anthropic expects [{role: 'assistant'|'user', content: str}, ...]."""
    out: list[dict[str, Any]] = []
    for item in recent_history:
        if not isinstance(item, dict):
            continue
        raw_role = item.get("role", "")
        role = "assistant" if raw_role == "agent" else "user"
        content = item.get("content") or item.get("text") or ""
        if content:
            out.append({"role": role, "content": str(content)})
    return out


async def run_turn(
    *,
    business: Business,
    caller_number: str,
    caller_transcript: str,
    recent_history: list[Any],
    system_prompt_override: str | None = None,
    tools_override: list[dict[str, Any]] | None = None,
    call_context: CallContext | None = None,
) -> tuple[str, list[str], bool]:
    """Run one turn of the voice agent.

    Returns (reply_text, tool_names_used, end_call).

    `caller_transcript` is what the caller JUST said this turn.
    `recent_history` is AgentPhone's rolling context (excludes the new utterance).
    `caller_number` is the caller's phone — used by recall/remember tools.

    `system_prompt_override` and `tools_override` are used by the OUTBOUND flow:
    when our caller agent is dialing a target business, the active prompt and
    the tool list live on the OutboundCall row, not on the Business row."""
    system_prompt = system_prompt_override or business.system_prompt
    if not system_prompt:
        log.warning("business %s has no system_prompt — returning fallback", business.id)
        return FALLBACK_REPLY, [], False

    tool_schemas = tools_override if tools_override is not None else TOOL_SCHEMAS

    history = _convert_recent_history(recent_history)
    history.append({"role": "user", "content": caller_transcript or "(silence)"})
    tools_used: list[str] = []
    end_call_requested = False

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = await client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tool_schemas,
            messages=history,
        )

        history.append(
            {"role": "assistant", "content": [b.model_dump() for b in resp.content]}
        )

        if resp.stop_reason == "end_turn":
            return _text_from_blocks(resp.content) or FALLBACK_REPLY, tools_used, end_call_requested

        if resp.stop_reason == "tool_use":
            tool_calls = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            results = await asyncio.gather(
                *[
                    run_tool(
                        tc.name, business, caller_number, tc.input or {},
                        call_context=call_context,
                    )
                    for tc in tool_calls
                ]
            )
            tool_result_blocks: list[dict[str, Any]] = []
            for tc, out in zip(tool_calls, results):
                tools_used.append(tc.name)
                if tc.name == "end_call":
                    end_call_requested = True
                log_call_event(
                    business.id, f"tool:{tc.name}", "called",
                    {"args": tc.input, "ok": "error" not in out},
                )
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": str(out),
                    }
                )
            history.append({"role": "user", "content": tool_result_blocks})

            # If the model called end_call, we already have its farewell text
            # in the SAME turn (the model is required to speak first then call
            # the tool). Return immediately so the webhook can hang up.
            if end_call_requested:
                # The farewell is the assistant text from the response that
                # contained the end_call tool_use block.
                farewell = _text_from_blocks(resp.content)
                if not farewell:
                    # Fall back to the tool's farewell_message arg.
                    for tc in tool_calls:
                        if tc.name == "end_call":
                            msg = (tc.input or {}).get("farewell_message", "")
                            if msg:
                                farewell = str(msg)
                                break
                return farewell or "Thanks, goodbye.", tools_used, True
            continue

        # max_tokens or any other stop_reason — return whatever text we have
        return _text_from_blocks(resp.content) or FALLBACK_REPLY, tools_used, end_call_requested

    log.warning("tool loop exhausted %d iterations", MAX_TOOL_ITERATIONS)
    return FALLBACK_REPLY, tools_used, end_call_requested


__all__ = ["run_turn", "MODEL", "FALLBACK_REPLY", "DISPATCH"]
