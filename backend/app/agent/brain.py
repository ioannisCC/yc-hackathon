"""Claude Haiku 4.5 tool-call loop for one voice turn."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.agent.tools import DISPATCH, TOOL_SCHEMAS, run_tool
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
) -> tuple[str, list[str]]:
    """Run one turn of the voice agent. Returns (reply_text, tool_names_used).

    `caller_transcript` is what the caller JUST said this turn.
    `recent_history` is AgentPhone's rolling context (excludes the new utterance).
    `caller_number` is the caller's phone — used by recall/remember tools."""
    if not business.system_prompt:
        log.warning("business %s has no system_prompt — returning fallback", business.id)
        return FALLBACK_REPLY, []

    history = _convert_recent_history(recent_history)
    history.append({"role": "user", "content": caller_transcript or "(silence)"})
    tools_used: list[str] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = await client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=business.system_prompt,
            tools=TOOL_SCHEMAS,
            messages=history,
        )

        history.append(
            {"role": "assistant", "content": [b.model_dump() for b in resp.content]}
        )

        if resp.stop_reason == "end_turn":
            return _text_from_blocks(resp.content) or FALLBACK_REPLY, tools_used

        if resp.stop_reason == "tool_use":
            tool_calls = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            results = await asyncio.gather(
                *[
                    run_tool(tc.name, business, caller_number, tc.input or {})
                    for tc in tool_calls
                ]
            )
            tool_result_blocks: list[dict[str, Any]] = []
            for tc, out in zip(tool_calls, results):
                tools_used.append(tc.name)
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
            continue

        # max_tokens or any other stop_reason — return whatever text we have
        return _text_from_blocks(resp.content) or FALLBACK_REPLY, tools_used

    log.warning("tool loop exhausted %d iterations", MAX_TOOL_ITERATIONS)
    return FALLBACK_REPLY, tools_used


__all__ = ["run_turn", "MODEL", "FALLBACK_REPLY", "DISPATCH"]
