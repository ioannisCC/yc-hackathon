"""Browser Use v3 — URL → typed BusinessInfo Pydantic."""
from __future__ import annotations

import asyncio

from browser_use_sdk.v3 import AsyncBrowserUse
from pydantic import BaseModel, Field

from app.config import settings


class ServiceInfo(BaseModel):
    name: str
    price_usd: float | None = None
    duration_minutes: int | None = None


class BusinessInfo(BaseModel):
    name: str
    phone: str | None = None
    address: str | None = None
    hours: dict[str, str] = Field(default_factory=dict)
    services: list[ServiceInfo] = Field(default_factory=list)
    booking_policy: str | None = None
    description: str = ""


_client: AsyncBrowserUse | None = None


def client() -> AsyncBrowserUse:
    global _client
    if _client is None:
        _client = AsyncBrowserUse(api_key=settings.BROWSER_USE_API_KEY)
    return _client


async def extract_business(url: str, timeout_s: float = 90.0) -> BusinessInfo:
    """Scrape the URL into a validated BusinessInfo."""
    task = (
        f"Visit {url}. Extract the business information: "
        "name, phone, address, hours of operation (day->time string), "
        "list of services offered (with price and typical duration if visible), "
        "booking/cancellation policy if stated, and a one-sentence description."
    )
    result = await asyncio.wait_for(
        client().run(task, output_schema=BusinessInfo),
        timeout=timeout_s,
    )
    info = getattr(result, "output", None)
    if info is None:
        raise RuntimeError("Browser Use returned no parsed output")
    if isinstance(info, BusinessInfo):
        return info
    if isinstance(info, dict):
        return BusinessInfo.model_validate(info)
    raise RuntimeError(f"Unexpected Browser Use output type: {type(info).__name__}")
