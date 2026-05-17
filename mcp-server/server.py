"""MCP server: agentphone-outbound.

Exposes two tools to Claude Code (or any MCP client):

    call_business(target_business_query, intent, caller_context)
    get_outbound_call_status(outbound_call_id)

call_business triggers the backend's /agents/outbound-call endpoint, which
synthesizes a per-call system prompt and places an outbound voice call from
Sir's caller agent to the target business's receptionist agent. The result
is two AI agents on a phone line, with the receiving agent doing the
booking via its existing tools (Cal.com, AgentMail, etc.)."""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BACKEND_URL = os.environ.get(
    "AGENTPHONE_BACKEND_URL",
    "http://localhost:8000",
).rstrip("/")

_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

mcp = FastMCP("agentphone-outbound")


@mcp.tool()
async def call_business(
    target_business_query: str,
    intent: str,
    caller_context: dict[str, Any],
) -> dict[str, Any]:
    """Place a real outbound phone call from Sir's AI agent to another business's AI receptionist.

    USE THIS TOOL when the user asks you to call a business on their behalf
    ("call Code Salon and book a haircut", "ring up Dr. Tran's office and
    cancel Tuesday", etc.). The call is REAL — a phone actually rings on the
    other end and two AI agents conduct an audio conversation.

    BEFORE INVOKING, gather context dynamically. The caller agent will be
    asked questions by the receiving agent, and it can only answer from
    facts in `caller_context`. Different business types ask different
    questions — DO NOT use a fixed checklist. Reason about what the
    receptionist will plausibly ask, then ask the user 2-5 short questions
    to fill the gaps. Examples (illustrative, not prescriptive):

      - veterinarian: pet name, breed/species, age, presenting symptoms
      - dentist: patient name, which tooth, pain level, last visit
      - hair salon: name, email, hair type/length, preferred stylist
      - plumber: name, address, what's broken, urgency
      - restaurant: party size, date/time window, dietary restrictions
      - law office: matter type, urgency, conflict-check parties

    Keep questions terse. If the user already gave a fact in their request,
    don't re-ask. If a fact is genuinely unknowable until they're on the
    line (e.g. exact slot times), don't ask — the agent will negotiate.

    Args:
        target_business_query: How to find the business in the backend. Can
            be a UUID, a business name fragment ("Code Salon"), or an E.164
            phone number ("+14155551212").
        intent: One-sentence statement of what the call should accomplish.
            Example: "Book a men's haircut for Tuesday May 19 around 2 PM."
        caller_context: Free-form key/value facts the agent can volunteer
            when asked. Include name, email, phone, plus everything you
            gathered above. Example:
                {
                  "caller_name": "Ioannis",
                  "caller_email": "n.ketselidis@gmail.com",
                  "preferred_window": "Tuesday May 19, 1:30-3:00 PM",
                  "service": "men's haircut",
                  "hair_type": "thick, wavy",
                }

    Returns the backend response including `outbound_call_id` (use it with
    get_outbound_call_status to watch progress), the `dial_target` phone
    number that was rung, and a `status` of "ringing" or "failed".
    """
    payload = {
        "target_business_query": target_business_query,
        "intent": intent,
        "caller_context": caller_context,
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as http:
        r = await http.post(f"{BACKEND_URL}/agents/outbound-call", json=payload)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text}
    if not (200 <= r.status_code < 300):
        return {
            "ok": False,
            "status_code": r.status_code,
            "error": body,
            "hint": (
                "404 → no business matched the query (try a different name or "
                "use the UUID). 409 → business has no phone number provisioned. "
                "500 → CALLER_AGENT_ID env var missing on the backend."
            ),
        }
    return {"ok": True, **body}


@mcp.tool()
async def get_outbound_call_status(outbound_call_id: str) -> dict[str, Any]:
    """Check the status and live transcript of an outbound call already in flight.

    Use this to poll a call you initiated with `call_business`. The
    transcript field shows the agent-to-agent conversation as it unfolds
    (role values: "agent" = our caller, "target_agent" = the receiving
    receptionist).

    Args:
        outbound_call_id: UUID returned by call_business.

    Returns the current status ("initiating", "ringing", "in_progress",
    "completed", "failed"), any error message, the end_reason if completed,
    and the full transcript so far.
    """
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as http:
        r = await http.get(f"{BACKEND_URL}/agents/outbound-call/{outbound_call_id}")
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text}
    if not (200 <= r.status_code < 300):
        return {"ok": False, "status_code": r.status_code, "error": body}
    return {"ok": True, **body}


if __name__ == "__main__":
    mcp.run()
