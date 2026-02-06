"""Configuration management using Pydantic Settings."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_list(v: object) -> list[str]:
    """Parse a list field from either JSON or comma-separated string."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        # Try JSON first
        if v.startswith("["):
            return json.loads(v)
        # Fall back to comma-separated
        return [item.strip() for item in v.split(",") if item.strip()]
    return list(v)  # type: ignore[arg-type]


def _parse_dict(v: object) -> dict[str, str]:
    """Parse a dict field from a JSON string or pass through."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        return json.loads(v)
    return dict(v)  # type: ignore[arg-type]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://agent:changeme@postgres:5432/agent"

    # Redis
    redis_url: str = "redis://redis:6379"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "changeme"
    minio_bucket: str = "agent-files"
    minio_public_url: str = "https://yourdomain.com/files"

    # LLM API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # LLM Defaults
    default_model: str = "claude-sonnet-4-20250514"
    summarization_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # Platform tokens
    discord_token: str = ""
    telegram_token: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""

    # Agent
    orchestrator_url: str = "http://core:8000"
    max_agent_iterations: int = 10
    conversation_timeout_minutes: int = 30
    working_memory_messages: int = 20

    # Defaults for new users
    default_guest_token_budget: int = 5000
    default_guest_modules: list[str] = ["research"]

    # Module services
    module_services: dict[str, str] = {
        "research": "http://research:8000",
        "file_manager": "http://file-manager:8000",
        "injective": "http://injective:8000",
    }

    # Model routing
    model_routing: dict[str, str] = {
        "default": "claude-sonnet-4-20250514",
        "summarization": "gpt-4o-mini",
        "complex_reasoning": "claude-sonnet-4-20250514",
        "embedding": "text-embedding-3-small",
        "memory_summarization": "gpt-4o-mini",
    }
    fallback_chain: list[str] = [
        "claude-sonnet-4-20250514",
        "gpt-4o",
        "gemini-2.0-flash",
    ]

    # Validators for fields that can be set as comma-separated strings in .env
    @field_validator("default_guest_modules", "fallback_chain", mode="before")
    @classmethod
    def parse_list_field(cls, v: object) -> list[str]:
        return _parse_list(v)

    @field_validator("module_services", "model_routing", mode="before")
    @classmethod
    def parse_dict_field(cls, v: object) -> dict[str, str]:
        return _parse_dict(v)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
