"""Database models. Per CLAUDE.md: Postgres holds businesses + call_logs;
Supermemory holds callers; Cal.com holds bookings."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Business(SQLModel, table=True):
    __tablename__ = "businesses"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    phone_number: str = Field(index=True, unique=True)
    name: str
    website_url: str
    maps_url: str | None = None
    timezone: str = "America/Los_Angeles"

    cal_event_type_ids: list[int] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )
    moss_index_name: str
    agentmail_inbox_id: str
    agentphone_agent_id: str
    agentphone_number_id: str
    system_prompt: str

    extra: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict)
    )

    created_at: datetime = Field(default_factory=_utcnow)


class CallLog(SQLModel, table=True):
    __tablename__ = "call_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    business_id: UUID = Field(foreign_key="businesses.id", index=True)
    caller_phone: str = Field(index=True)
    conversation_id: str | None = Field(default=None, index=True)

    started_at: datetime = Field(default_factory=_utcnow)
    ended_at: datetime | None = None
    outcome: str | None = None  # booked | rescheduled | cancelled | info | escalated

    transcript: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )
    tools_used: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )
