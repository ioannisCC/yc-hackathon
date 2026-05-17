"""Background-task onboarding pipeline.

POST /businesses creates a stub Business row with status="scraping" and
immediately kicks off run_onboarding(business_id, url) as an asyncio task.
Each of the 6 steps writes one status transition to the DB so the frontend
can poll /onboarding-status and animate the loader from real progress.

On any step exception: status.current_step = "failed", status.error is set
to {step, message}, and we return cleanly without crashing the task."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import select

from app.agent.system_prompt import build_system_prompt
from app.config import settings
from app.db import session_scope
from app.models import Business
from app.services import agentphone_svc, browser_svc, calcom_svc, mail_svc, moss_svc
from app.services.logging_svc import log_call_event

log = logging.getLogger(__name__)

# Step keys in execution order — also drive the frontend's 6-card UI.
STEPS = ["scraping", "moss", "inbox", "calcom", "agent", "live"]


class OnboardingError(RuntimeError):
    def __init__(self, step: str, cause: BaseException) -> None:
        super().__init__(f"onboarding failed at {step}: {cause}")
        self.step = step
        self.cause = cause


# ---------- Status helpers ----------------------------------------------------


async def _set_current_step(business_id: UUID, step: str) -> None:
    async with session_scope() as s:
        biz = await s.get(Business, business_id)
        if biz is None:
            return
        status = dict(biz.onboarding_status or {})
        status["current_step"] = step
        biz.onboarding_status = status
        s.add(biz)
        await s.commit()


async def _mark_step_done(business_id: UUID, step: str) -> None:
    async with session_scope() as s:
        biz = await s.get(Business, business_id)
        if biz is None:
            return
        status = dict(biz.onboarding_status or {})
        completed = list(status.get("completed_steps") or [])
        if step not in completed:
            completed.append(step)
        status["completed_steps"] = completed
        biz.onboarding_status = status
        s.add(biz)
        await s.commit()


async def _set_failure(business_id: UUID, step: str, message: str) -> None:
    async with session_scope() as s:
        biz = await s.get(Business, business_id)
        if biz is None:
            return
        status = dict(biz.onboarding_status or {})
        status["current_step"] = "failed"
        status["error"] = {"step": step, "message": message}
        biz.onboarding_status = status
        s.add(biz)
        await s.commit()


async def _patch_business(business_id: UUID, **fields: Any) -> None:
    async with session_scope() as s:
        biz = await s.get(Business, business_id)
        if biz is None:
            return
        for k, v in fields.items():
            setattr(biz, k, v)
        s.add(biz)
        await s.commit()


# ---------- Public API --------------------------------------------------------


async def create_stub_business(url: str) -> UUID:
    """Insert a stub Business row with status=scraping and return its id.
    Must complete in <100ms so the POST returns immediately."""
    business_id = uuid4()
    async with session_scope() as s:
        biz = Business(
            id=business_id,
            website_url=url,
            onboarding_status={
                "current_step": "scraping",
                "completed_steps": [],
                "error": None,
            },
        )
        s.add(biz)
        await s.commit()
    log_call_event(business_id, "system", "onboarding_started", {"url": url})
    return business_id


def schedule_onboarding(business_id: UUID, url: str) -> asyncio.Task[None]:
    """Fire-and-forget background task. Caller does not await."""
    return asyncio.create_task(run_onboarding(business_id, url))


async def run_onboarding(business_id: UUID, url: str) -> None:
    """The 6-step pipeline. Wraps every step in graceful error handling."""
    if not settings.PUBLIC_BACKEND_URL:
        await _set_failure(business_id, "preflight", "PUBLIC_BACKEND_URL unset")
        return

    short = business_id.hex[:8]

    # STEP 1 — Browser Use scrape
    info: browser_svc.BusinessInfo
    try:
        await _set_current_step(business_id, "scraping")
        t0 = time.monotonic()
        info = await browser_svc.extract_business(url)
        log_call_event(business_id, "system", "step_done",
                       {"step": "scraping", "ms": int((time.monotonic() - t0) * 1000)})
        await _patch_business(business_id, name=info.name, extra={"scraped": info.model_dump()})
        await _mark_step_done(business_id, "scraping")
    except Exception as e:
        log.exception("onboarding scrape failed")
        await _set_failure(business_id, "scraping", f"{type(e).__name__}: {e}")
        return

    # STEP 2 — Moss index (best-effort; skips on REST-only deploys)
    index_name = f"biz_{short}"
    try:
        await _set_current_step(business_id, "moss")
        t0 = time.monotonic()
        await moss_svc.create_business_index(index_name, _docs_from_business(info))
        await _patch_business(business_id, moss_index_name=index_name)
        log_call_event(business_id, "system", "step_done",
                       {"step": "moss", "ms": int((time.monotonic() - t0) * 1000)})
    except NotImplementedError as e:
        log_call_event(business_id, "system", "step_skipped",
                       {"step": "moss", "reason": str(e)})
        await _patch_business(business_id, moss_index_name="")
    except Exception as e:
        log.exception("onboarding moss failed")
        await _set_failure(business_id, "moss", f"{type(e).__name__}: {e}")
        return
    await _mark_step_done(business_id, "moss")

    # STEP 3 — AgentMail inbox
    try:
        await _set_current_step(business_id, "inbox")
        t0 = time.monotonic()
        inbox_id = await mail_svc.create_inbox(info.name, short)
        await _patch_business(business_id, agentmail_inbox_id=inbox_id)
        log_call_event(business_id, "system", "step_done",
                       {"step": "inbox", "ms": int((time.monotonic() - t0) * 1000)})
        await _mark_step_done(business_id, "inbox")
    except Exception as e:
        log.exception("onboarding inbox failed")
        await _set_failure(business_id, "inbox", f"{type(e).__name__}: {e}")
        return

    # STEP 4 — Cal.com event types (parallel, capped)
    services = info.services or [
        browser_svc.ServiceInfo(name="Consultation", duration_minutes=30)
    ]
    sem = asyncio.Semaphore(4)

    async def _bounded(coro: Any) -> int:
        async with sem:
            return await coro

    try:
        await _set_current_step(business_id, "calcom")
        t0 = time.monotonic()
        event_type_ids = await asyncio.gather(*[
            _bounded(calcom_svc.create_event_type(
                str(business_id), info.name, s.name, s.duration_minutes or 30
            ))
            for s in services
        ])
        await _patch_business(business_id, cal_event_type_ids=list(event_type_ids))
        log_call_event(business_id, "system", "step_done",
                       {"step": "calcom", "ms": int((time.monotonic() - t0) * 1000)})
        await _mark_step_done(business_id, "calcom")
    except Exception as e:
        log.exception("onboarding calcom failed")
        await _set_failure(business_id, "calcom", f"{type(e).__name__}: {e}")
        return

    # STEP 5 — AgentPhone agent + number
    try:
        await _set_current_step(business_id, "agent")
        t0 = time.monotonic()
        system_prompt = build_system_prompt(info, "America/Los_Angeles")
        provision = await agentphone_svc.provision_for_business(info.name, system_prompt)
        await _patch_business(
            business_id,
            phone_number=provision.phone_number,
            agentphone_agent_id=provision.agent_id,
            agentphone_number_id=provision.number_id,
            system_prompt=system_prompt,
        )
        log_call_event(business_id, "system", "step_done",
                       {"step": "agent", "ms": int((time.monotonic() - t0) * 1000)})
        await _mark_step_done(business_id, "agent")
    except Exception as e:
        log.exception("onboarding agent failed")
        await _set_failure(business_id, "agent", f"{type(e).__name__}: {e}")
        return

    # STEP 6 — Live
    await _set_current_step(business_id, "live")
    await _mark_step_done(business_id, "live")
    await _set_current_step(business_id, "done")
    log_call_event(business_id, "system", "onboarding_complete", {})


# ---------- Helpers -----------------------------------------------------------


def _docs_from_business(info: browser_svc.BusinessInfo) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for s in info.services:
        bits = [s.name]
        if s.duration_minutes:
            bits.append(f"{s.duration_minutes} minutes")
        if s.price_usd is not None:
            bits.append(f"${s.price_usd:g}")
        slug = s.name.lower().replace(" ", "_")[:32]
        docs.append({"id": f"svc_{slug}", "text": " — ".join(bits)})
    if info.hours:
        docs.append({
            "id": "hours",
            "text": "Hours: " + ", ".join(f"{d}: {h}" for d, h in info.hours.items()),
        })
    if info.booking_policy:
        docs.append({"id": "policy", "text": f"Booking policy: {info.booking_policy}"})
    if info.description:
        docs.append({"id": "about", "text": info.description})
    if not docs:
        docs.append({"id": "about", "text": info.name})
    return docs
