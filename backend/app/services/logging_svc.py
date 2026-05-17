"""Structured event log — one JSON line per event, stdout only for Phase 2."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def log_call_event(
    business_id: UUID | str | None,
    actor: str,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Emit a structured event to stdout. Cheap, sync, non-blocking."""
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "business_id": str(business_id) if business_id else None,
        "actor": actor,  # "system" | "agent" | "caller" | "tool:<name>"
        "event": event,
        "payload": payload or {},
    }
    sys.stdout.write(json.dumps(line, default=str) + "\n")
    sys.stdout.flush()
