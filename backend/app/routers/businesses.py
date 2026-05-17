"""Business onboarding + dashboard read endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db import get_session
from app.models import Business, CallLog
from app.services.onboarding_svc import (
    create_stub_business,
    schedule_onboarding,
)

router = APIRouter(prefix="/businesses", tags=["businesses"])


# ---------- Schemas ----------------------------------------------------------


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)


class OnboardRequest(StrictModel):
    url: str


class OnboardAcceptedResponse(StrictModel):
    id: UUID
    status: str  # always "scraping" when first accepted


class OnboardingStatusResponse(StrictModel):
    current_step: str
    completed_steps: list[str]
    error: dict[str, str] | None


class CallSummary(StrictModel):
    id: UUID
    caller_phone: str
    caller_name: str | None
    status: str
    outcome: str | None
    started_at: datetime
    ended_at: datetime | None
    summary: str | None


class StatsResponse(StrictModel):
    calls_today: int
    bookings_today: int
    escalations_today: int


# ---------- Onboarding -------------------------------------------------------


@router.post("", status_code=202, response_model=OnboardAcceptedResponse)
async def onboard(req: OnboardRequest) -> OnboardAcceptedResponse:
    """Accept the URL, persist a stub row, return immediately. The actual
    6-step pipeline runs as a background task; clients poll the status
    endpoint for progress."""
    business_id = await create_stub_business(req.url)
    schedule_onboarding(business_id, req.url)
    return OnboardAcceptedResponse(id=business_id, status="scraping")


@router.get("/{business_id}/onboarding-status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    business_id: UUID, db: AsyncSession = Depends(get_session),
) -> OnboardingStatusResponse:
    biz = await db.get(Business, business_id)
    if biz is None:
        raise HTTPException(status_code=404, detail="business not found")
    s: dict[str, Any] = dict(biz.onboarding_status or {})
    return OnboardingStatusResponse(
        current_step=s.get("current_step", "scraping"),
        completed_steps=list(s.get("completed_steps") or []),
        error=s.get("error"),
    )


@router.get("/{business_id}", response_model=Business)
async def get_business(
    business_id: UUID, db: AsyncSession = Depends(get_session),
) -> Business:
    row = await db.get(Business, business_id)
    if row is None:
        raise HTTPException(status_code=404, detail="business not found")
    return row


# ---------- Dashboard reads --------------------------------------------------


@router.get("/{business_id}/calls", response_model=list[CallSummary])
async def list_calls(
    business_id: UUID,
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> list[CallSummary]:
    rows = (
        await db.execute(
            select(CallLog)
            .where(CallLog.business_id == business_id)
            .order_by(CallLog.started_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        CallSummary(
            id=r.id,
            caller_phone=r.caller_phone,
            caller_name=r.caller_name,
            status=r.status,
            outcome=r.outcome,
            started_at=r.started_at,
            ended_at=r.ended_at,
            summary=r.summary,
        )
        for r in rows
    ]


@router.get("/{business_id}/stats", response_model=StatsResponse)
async def get_stats(
    business_id: UUID, db: AsyncSession = Depends(get_session),
) -> StatsResponse:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    base = select(CallLog).where(
        CallLog.business_id == business_id,
        CallLog.started_at >= today,
    )

    calls_today = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    bookings_today = (
        await db.execute(
            select(func.count()).select_from(
                base.where(CallLog.outcome == "booked").subquery()
            )
        )
    ).scalar_one()

    escalations_today = (
        await db.execute(
            select(func.count()).select_from(
                base.where(CallLog.outcome == "escalated").subquery()
            )
        )
    ).scalar_one()

    return StatsResponse(
        calls_today=int(calls_today),
        bookings_today=int(bookings_today),
        escalations_today=int(escalations_today),
    )
