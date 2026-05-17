"""Supermemory wrapper — per-caller memory keyed on phone number."""
from __future__ import annotations

import asyncio
from typing import Any

from supermemory import Supermemory

from app.config import settings

_client: Supermemory | None = None


def client() -> Supermemory:
    global _client
    if _client is None:
        _client = Supermemory(api_key=settings.SUPERMEMORY_API_KEY)
    return _client


def container_for(phone: str) -> str:
    return f"caller_{phone}"


async def remember(phone: str, fact: str) -> None:
    await asyncio.to_thread(
        client().add, content=fact, container_tag=container_for(phone)
    )


async def profile(phone: str) -> dict[str, Any]:
    prof = await asyncio.to_thread(
        client().profile, container_tag=container_for(phone)
    )
    if prof is None:
        return {}
    if hasattr(prof, "model_dump"):
        return prof.model_dump()
    if isinstance(prof, dict):
        return prof
    return {"raw": str(prof)}
