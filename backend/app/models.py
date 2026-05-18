"""Database models. Per CLAUDE.md: Postgres holds businesses + call_logs;
Supermemory holds callers; Cal.com holds bookings."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

OutboundCallStatus = Literal[
    "initiating", "ringing", "in_progress", "completed", "failed"
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# All timestamps are TIMESTAMPTZ — asyncpg refuses to bind tz-aware datetimes
# to tz-naive columns. Every datetime field must carry the DateTime(timezone=True)
# sa_column override.


# Onboarding status shape stored in Business.onboarding_status:
#   {
#     "current_step": "scraping" | "moss" | "inbox" | "calcom" | "agent" | "live" | "done" | "failed",
#     "completed_steps": ["scraping", ...],
#     "error": null | {"step": "X", "message": "Y"}
#   }
def _initial_onboarding_status() -> dict[str, Any]:
    return {"current_step": "scraping", "completed_steps": [], "error": None}


class Business(SQLModel, table=True):
    __tablename__ = "businesses"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    website_url: str
    timezone: str = "America/Los_Angeles"

    # Filled in as onboarding progresses — null until the relevant step completes.
    name: str | None = None
    phone_number: str | None = Field(default=None, index=True, unique=True)
    maps_url: str | None = None
    moss_index_name: str | None = None
    agentmail_inbox_id: str | None = None
    agentphone_agent_id: str | None = None
    agentphone_number_id: str | None = None
    system_prompt: str | None = None

    cal_event_type_ids: list[int] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )

    onboarding_status: dict[str, Any] = Field(
        default_factory=_initial_onboarding_status,
        sa_column=Column(JSONB, nullable=False, default=_initial_onboarding_status),
    )

    extra: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict)
    )

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CallLog(SQLModel, table=True):
    __tablename__ = "call_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    business_id: UUID = Field(foreign_key="businesses.id", index=True)
    caller_phone: str = Field(index=True)
    caller_name: str | None = None
    conversation_id: str | None = Field(default=None, index=True)

    # in_progress | completed | failed
    status: str = Field(default="in_progress", index=True)
    # booked | rescheduled | cancelled | info | escalated | none
    outcome: str | None = None
    summary: str | None = None

    started_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # Each chunk: {role: "caller"|"agent", text: str, ts: iso-string, tool_call?: {...}}
    transcript: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )
    # Each tool call: {name, args, result, ts}
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )
    # Compact list of tool names — useful for stats queries
    tools_used: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False, default=list)
    )

    # Idempotency anchor for book_appointment within this call. Once set, the
    # tool returns the cached uid instead of POSTing /bookings again, which
    # prevents the duplicate-booking loop when transcription drift makes the
    # agent call book_appointment a second time with the same args.
    cal_booking_uid: str | None = None


class OutboundCall(SQLModel, table=True):
    """An outbound call placed BY our caller agent ON BEHALF OF Sir, dialing a
    target Business's receptionist. The webhook router uses caller_agent_id +
    status to find the active OutboundCall for routing transcripts."""

    __tablename__ = "outbound_calls"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    target_business_id: UUID = Field(foreign_key="businesses.id", index=True)
    caller_agent_id: str = Field(index=True)
    intent: str
    caller_context: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict)
    )
    dynamic_system_prompt: str

    agentphone_call_id: str | None = Field(default=None, index=True)
    status: str = Field(default="initiating", index=True)
    error: str | None = None

    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    end_reason: str | None = None  # "agent_hangup" | "timeout" | "agentphone_event"

    # Links to the CallLog row used to persist the in-flight transcript.
    call_log_id: UUID | None = Field(
        default=None, foreign_key="call_logs.id", index=True
    )

    # See CallLog.cal_booking_uid — same idempotency anchor on the outbound side.
    cal_booking_uid: str | None = None
