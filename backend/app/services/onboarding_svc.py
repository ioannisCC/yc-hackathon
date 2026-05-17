"""URL → live business in <90s. Orchestrates all 6 onboarding steps."""
from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from moss import DocumentInfo
from sqlmodel import select

from app.agent.system_prompt import build_system_prompt
from app.config import settings
from app.db import session_scope
from app.models import Business
from app.services import agentphone_svc, browser_svc, calcom_svc, mail_svc, moss_svc
from app.services.logging_svc import log_call_event


class OnboardingError(RuntimeError):
    def __init__(self, step: str, cause: Exception):
        super().__init__(f"onboarding failed at {step}: {cause}")
        self.step = step
        self.cause = cause


async def _step(business_id, step_name: str, coro):
    t0 = time.monotonic()
    try:
        result = await coro
        log_call_event(
            business_id, "system", "onboarding_step",
            {"step": step_name, "duration_ms": int((time.monotonic() - t0) * 1000), "ok": True},
        )
        return result
    except Exception as e:
        log_call_event(
            business_id, "system", "onboarding_step",
            {"step": step_name, "duration_ms": int((time.monotonic() - t0) * 1000),
             "ok": False, "err": f"{type(e).__name__}: {e}"},
        )
        raise OnboardingError(step_name, e) from e


def _docs_from_business(info: browser_svc.BusinessInfo) -> list[DocumentInfo]:
    docs: list[DocumentInfo] = []
    for s in info.services:
        bits = [s.name]
        if s.duration_minutes:
            bits.append(f"{s.duration_minutes} minutes")
        if s.price_usd is not None:
            bits.append(f"${s.price_usd:g}")
        slug = s.name.lower().replace(" ", "_")[:32]
        docs.append(DocumentInfo(id=f"svc_{slug}", text=" — ".join(bits)))
    if info.hours:
        hours_text = "Hours: " + ", ".join(f"{d}: {h}" for d, h in info.hours.items())
        docs.append(DocumentInfo(id="hours", text=hours_text))
    if info.booking_policy:
        docs.append(DocumentInfo(id="policy", text=f"Booking policy: {info.booking_policy}"))
    if info.description:
        docs.append(DocumentInfo(id="about", text=info.description))
    if not docs:
        docs.append(DocumentInfo(id="about", text=info.name))
    return docs


async def onboard_business(url: str) -> Business:
    if not settings.PUBLIC_BACKEND_URL:
        raise OnboardingError("preflight", RuntimeError("PUBLIC_BACKEND_URL is unset"))

    business_id = uuid4()
    short = business_id.hex[:8]
    log_call_event(business_id, "system", "onboarding_start", {"url": url})

    # STEP 1 — Browser Use scrape
    info: browser_svc.BusinessInfo = await _step(
        business_id, "browser_scrape", browser_svc.extract_business(url)
    )

    # STEP 2 — Moss index
    index_name = f"biz_{short}"
    await _step(
        business_id, "moss_index",
        moss_svc.create_business_index(index_name, _docs_from_business(info)),
    )

    # STEP 3 — AgentMail inbox
    inbox_id: str = await _step(
        business_id, "agentmail_inbox", mail_svc.create_inbox(info.name, short)
    )

    # STEP 4 — Cal.com event types (parallel)
    services = info.services or [browser_svc.ServiceInfo(name="Consultation", duration_minutes=30)]
    event_type_ids: list[int] = await _step(
        business_id, "calcom_event_types",
        asyncio.gather(
            *[
                calcom_svc.create_event_type(
                    str(business_id), info.name, s.name, s.duration_minutes or 30
                )
                for s in services
            ]
        ),
    )

    # STEP 5 — AgentPhone agent + number
    system_prompt = build_system_prompt(info, "America/Los_Angeles")
    provision = await _step(
        business_id, "agentphone_provision",
        agentphone_svc.provision_for_business(info.name, system_prompt),
    )

    # STEP 6 — Persist
    business = Business(
        id=business_id,
        phone_number=provision.phone_number,
        name=info.name,
        website_url=url,
        timezone="America/Los_Angeles",
        cal_event_type_ids=event_type_ids,
        moss_index_name=index_name,
        agentmail_inbox_id=inbox_id,
        agentphone_agent_id=provision.agent_id,
        agentphone_number_id=provision.number_id,
        system_prompt=system_prompt,
        extra={"scraped": info.model_dump()},
    )
    async with session_scope() as s:
        s.add(business)
        await s.commit()
        await s.refresh(business)

    log_call_event(
        business_id, "system", "onboarding_complete",
        {"phone_number": provision.phone_number, "event_types": len(event_type_ids)},
    )
    return business
