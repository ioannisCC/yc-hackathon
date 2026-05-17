"""Business onboarding + retrieval endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db import get_session
from app.models import Business, CallLog
from app.services.onboarding_svc import OnboardingError, onboard_business

router = APIRouter(prefix="/businesses", tags=["businesses"])


class OnboardRequest(BaseModel):
    url: str


@router.post("", response_model=Business)
async def onboard(req: OnboardRequest) -> Business:
    try:
        return await onboard_business(req.url)
    except OnboardingError as e:
        raise HTTPException(
            status_code=502,
            detail={"step": e.step, "error": f"{type(e.cause).__name__}: {e.cause}"},
        )


@router.get("/{business_id}", response_model=Business)
async def get_business(
    business_id: UUID, db: AsyncSession = Depends(get_session)
) -> Business:
    row = (
        await db.execute(select(Business).where(Business.id == business_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="business not found")
    return row


@router.get("/{business_id}/calls", response_model=list[CallLog])
async def list_calls(
    business_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> list[CallLog]:
    rows = (
        await db.execute(
            select(CallLog)
            .where(CallLog.business_id == business_id)
            .order_by(CallLog.started_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)
