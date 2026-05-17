"""Application configuration loaded from .env via pydantic-settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/receptionist"
    )

    # LLM
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Voice + Phone
    AGENTPHONE_API_KEY: str = ""
    AGENTPHONE_WEBHOOK_SECRET: str = ""

    # Memory layers
    MOSS_PROJECT_ID: str = ""
    MOSS_PROJECT_KEY: str = ""
    SUPERMEMORY_API_KEY: str = ""

    # Email
    AGENTMAIL_API_KEY: str = ""

    # Browser
    BROWSER_USE_API_KEY: str = ""

    # Calendar
    CALCOM_API_KEY: str = ""

    # Public URL for AgentPhone webhook (filled after ngrok/cloudflared starts)
    PUBLIC_BACKEND_URL: str = "http://localhost:8000"


settings = Settings()
