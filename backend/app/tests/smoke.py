"""Smoke test runner — verifies every external service is reachable with our keys.

Run:  cd backend && python -m app.tests.smoke

Rules:
  - Must complete in <30 seconds total (all checks run in parallel).
  - Must NOT spend money (no number provisioning, no inbox creation, no paid
    Browser Use tasks against complex sites — HN is the smoke target).
  - One PASS / FAIL line per service with the error message on failure.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

from app.config import settings

PER_CHECK_TIMEOUT_S = 25.0


# ---------- Individual checks ----------------------------------------------------


async def check_agentphone() -> str:
    from agentphone import AgentPhone

    client = AgentPhone(api_key=settings.AGENTPHONE_API_KEY)
    numbers = await asyncio.to_thread(client.numbers.list)
    count = len(numbers) if hasattr(numbers, "__len__") else "?"
    return f"{count} number(s) on account"


async def check_anthropic() -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=5,
        messages=[{"role": "user", "content": "Say 'ok'."}],
    )
    first = msg.content[0] if msg.content else None
    text = getattr(first, "text", "") if first else ""
    return f"model={msg.model} reply={text!r}"


async def check_moss() -> str:
    from moss import DocumentInfo, MossClient, QueryOptions

    client = MossClient(
        project_id=settings.MOSS_PROJECT_ID,
        project_key=settings.MOSS_PROJECT_KEY,
    )
    index_name = f"smoke_test_{int(time.time())}"

    try:
        await client.create_index(
            index_name,
            [
                DocumentInfo(id="1", text="The receptionist is friendly."),
                DocumentInfo(id="2", text="Bookings are confirmed by email."),
            ],
            model_id="moss-minilm",
        )
        await client.load_index(index_name)
        results = await client.query(
            index_name,
            "how are bookings confirmed?",
            QueryOptions(top_k=1),
        )
        top_id = results.docs[0].id if results.docs else "none"
        return f"index={index_name} top_doc_id={top_id}"
    finally:
        try:
            await client.delete_index(index_name)
        except Exception:
            pass


async def check_supermemory() -> str:
    from supermemory import Supermemory

    client = Supermemory(api_key=settings.SUPERMEMORY_API_KEY)
    container = f"smoke_{int(time.time())}"

    await asyncio.to_thread(
        client.add, content="smoke test", container_tag=container
    )
    prof = await asyncio.to_thread(client.profile, container_tag=container)
    # best-effort cleanup
    for attr in ("delete_container", "delete"):
        fn = getattr(client, attr, None)
        if callable(fn):
            try:
                await asyncio.to_thread(fn, container_tag=container)
                break
            except Exception:
                pass
    return f"container={container} profile_ok={prof is not None}"


async def check_agentmail() -> str:
    from agentmail import AgentMail

    client = AgentMail(api_key=settings.AGENTMAIL_API_KEY)
    inboxes = await asyncio.to_thread(client.inboxes.list)
    count = len(inboxes) if hasattr(inboxes, "__len__") else "?"
    return f"{count} inbox(es) on account"


async def check_browser_use() -> str:
    from browser_use_sdk.v3 import AsyncBrowserUse

    class HN(BaseModel):
        top_title: str

    client = AsyncBrowserUse(api_key=settings.BROWSER_USE_API_KEY)
    result = await client.run(
        "Go to news.ycombinator.com and return the title of the first post in the main list.",
        output_schema=HN,
    )
    title = (result.output.top_title or "")[:60]
    return f"top_title='{title}'"


async def check_postgres() -> str:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.DATABASE_URL, future=True)
    try:
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT 1"))
            value = r.scalar()
        return f"SELECT 1 = {value}"
    finally:
        await engine.dispose()


async def check_calcom() -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://api.cal.com/v2/me",
            headers={
                "Authorization": f"Bearer {settings.CALCOM_API_KEY}",
                "cal-api-version": "2024-08-13",
            },
        )
        r.raise_for_status()
        body = r.json()
        data = body.get("data", body)
        email = (
            data.get("email")
            or data.get("user", {}).get("email")
            or "unknown"
        )
        return f"email={email}"


# ---------- Runner ---------------------------------------------------------------


@dataclass
class Result:
    name: str
    ok: bool
    detail: str
    seconds: float


async def _run_one(name: str, fn: Callable[[], Awaitable[str]]) -> Result:
    t0 = time.monotonic()
    try:
        detail = await asyncio.wait_for(fn(), timeout=PER_CHECK_TIMEOUT_S)
        return Result(name, True, detail, time.monotonic() - t0)
    except asyncio.TimeoutError:
        return Result(
            name, False, f"timed out after {PER_CHECK_TIMEOUT_S}s",
            time.monotonic() - t0,
        )
    except Exception as e:
        return Result(
            name, False, f"{type(e).__name__}: {e}".strip(),
            time.monotonic() - t0,
        )


CHECKS: list[tuple[str, Callable[[], Awaitable[str]]]] = [
    ("AgentPhone",  check_agentphone),
    ("Anthropic",   check_anthropic),
    ("Moss",        check_moss),
    ("Supermemory", check_supermemory),
    ("AgentMail",   check_agentmail),
    ("Browser Use", check_browser_use),
    ("Cal.com",     check_calcom),
    ("Postgres",    check_postgres),
]


async def main() -> int:
    print(f"Running {len(CHECKS)} smoke tests in parallel (budget <30s)\n")
    t0 = time.monotonic()
    results = await asyncio.gather(*[_run_one(n, f) for n, f in CHECKS])
    total = time.monotonic() - t0

    failed = 0
    for r in results:
        flag = "PASS" if r.ok else "FAIL"
        print(f"  [{flag}] {r.name:<12} ({r.seconds:5.2f}s)  {r.detail}")
        if not r.ok:
            failed += 1

    passed = len(results) - failed
    print(f"\n{passed}/{len(results)} passed in {total:.2f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
