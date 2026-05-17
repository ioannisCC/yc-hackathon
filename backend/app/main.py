"""FastAPI entry point. Lifespan boots the AgentMail WS subscriber per business."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from app.db import init_db, session_scope
from app.models import Business
from app.routers import businesses, webhooks
from app.services import calcom_svc, mail_svc
from app.services.email_intent_svc import handle_inbox_event

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()

    async with session_scope() as s:
        inbox_ids = [
            row.agentmail_inbox_id
            for row in (await s.execute(select(Business))).scalars().all()
        ]

    stop = asyncio.Event()
    ws_task = asyncio.create_task(
        mail_svc.run_ws_subscriber(inbox_ids, handle_inbox_event, stop)
    )
    log.info("Started AgentMail WS subscriber for %d inbox(es)", len(inbox_ids))

    try:
        yield
    finally:
        stop.set()
        ws_task.cancel()
        try:
            await ws_task
        except (asyncio.CancelledError, Exception):
            pass
        await calcom_svc.close()


app = FastAPI(title="AI Receptionist", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(businesses.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
