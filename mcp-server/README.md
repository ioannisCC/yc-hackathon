# agentphone-outbound MCP

Lets Claude Code (or any MCP client) place outbound agent-to-agent voice
calls through the AI Receptionist backend.

Sir types something like:

> Call Code Salon and book me a haircut Tuesday at 2pm.

Claude asks 2-5 dynamic clarifying questions (different per business
type — vet, dentist, salon, plumber, restaurant, …), then invokes
`call_business`. The backend synthesizes a per-call system prompt, dials
the target business from Sir's caller agent, and two AI agents have a real
phone conversation: ours provides facts, theirs does the booking.

## Tools

- **`call_business(target_business_query, intent, caller_context)`** —
  trigger the outbound call. The docstring guides the LLM to gather
  context dynamically before invoking; do not pass a fixed schema.
- **`get_outbound_call_status(outbound_call_id)`** — poll status and the
  live transcript.

## Setup

```bash
cd mcp-server
uv sync
```

The server reads `AGENTPHONE_BACKEND_URL` from the environment (defaults
to `http://localhost:8000`). Point it at the live Railway backend in
production.

## Wire into Claude Code

Add to your Claude Code MCP config (`~/.claude/mcp.json` or the in-app
settings):

```json
{
  "mcpServers": {
    "agentphone-outbound": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/absolute/path/to/yc voice agents/mcp-server/server.py"
      ],
      "env": {
        "AGENTPHONE_BACKEND_URL": "https://yc-hackathon-backend-production.up.railway.app"
      }
    }
  }
}
```

Restart Claude Code. The two tools become available; try:

```
Call Code Salon and book me a men's haircut Tuesday around 2 PM.
```

## Local smoke test

```bash
uv run python server.py
```

The MCP runs on stdio. Pair with any MCP client (Claude Code, MCP
Inspector) to confirm the tools are discoverable.
