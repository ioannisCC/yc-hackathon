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
    return "".join(getattr(b, "text", "") for b in blocks if getattr(b, "type", "") == "text")


async def run_turn(
    business: Business,
    caller_phone: str,
    caller_text: str,
    history: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Run one turn of the voice agent. Returns (reply_text, tools_used_names).

    `history` is the list of prior Anthropic messages and is mutated in place
    to include this turn's user/assistant/tool_result blocks.
    """
    history.append({"role": "user", "content": caller_text})
    tools_used: list[str] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = await client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=business.system_prompt,
            tools=TOOL_SCHEMAS,
            messages=history,
        )

        # Append the assistant's full message (text + any tool_use blocks) to history
        history.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})

        if resp.stop_reason == "end_turn":
            return _text_from_blocks(resp.content) or FALLBACK_REPLY, tools_used

        if resp.stop_reason == "tool_use":
            tool_calls = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            # Dispatch all tool calls for this turn in parallel
            results = await asyncio.gather(
                *[
                    run_tool(tc.name, business, caller_phone, tc.input or {})
                    for tc in tool_calls
                ],
                return_exceptions=False,
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

        # Any other stop_reason (e.g., max_tokens) — return what we have
        return _text_from_blocks(resp.content) or FALLBACK_REPLY, tools_used

    log.warning("Tool loop exhausted %d iterations", MAX_TOOL_ITERATIONS)
    return FALLBACK_REPLY, tools_used


__all__ = ["run_turn", "MODEL", "FALLBACK_REPLY", "DISPATCH"]
