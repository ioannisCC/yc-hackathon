"""Appointments router — thin facade over Cal.com. We do not store bookings."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("")
async def list_appointments(business_id: str) -> list[dict[str, str]]:
    """Phase 2 — proxies Cal.com /bookings filtered by business_id metadata."""
    _ = business_id
    raise NotImplementedError("Phase 2")
