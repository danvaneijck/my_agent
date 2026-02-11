"""Configuration management using Pydantic Settings."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_list(v: object) -> list[str]:
    """Parse a list from either a JSON array string, comma-separated string, or list."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        if v.startswith("["):
            return json.loads(v)
        return [item.strip() for item in v.split(",") if item.strip()]
    return list(v)  # type: ignore[arg-type]


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
    working_memory_messages: int = 12
    # Reduced history for standalone messages (no prior-context references)
    minimal_memory_messages: int = 2

    # Token efficiency
    # Max characters for a single tool result before truncation (in context)
    tool_result_max_chars: int = 3000
    # Max characters for tool_result messages loaded from DB history
    history_tool_result_max_chars: int = 1500
    # Cosine distance threshold for semantic memories (0.0 = identical, 2.0 = opposite)
    # Memories with distance above this are too irrelevant to include
    memory_relevance_threshold: float = 0.75
    # Estimated tokens consumed by tool definitions (subtracted from context budget)
    tool_schema_token_budget: int = 4000

    # Admin portal
    admin_api_key: str = ""

    # Injective — provide EITHER private key (hex) OR mnemonic, not both
    injective_private_key: str = ""
    injective_mnemonic: str = ""
    injective_network: str = "testnet"  # "mainnet" or "testnet"
    # Custom gRPC/LCD endpoints (leave empty to use SDK defaults)
    injective_exchange_grpc: str = ""   # e.g. "sentry.exchange.grpc.injective.network:443"
    injective_chain_grpc: str = ""      # e.g. "sentry.chain.grpc.injective.network:443"
    injective_lcd: str = ""             # e.g. "https://sentry.lcd.injective.network:443"
    # Path to custom tokens JSON file (same format as injective-lists)
    injective_custom_tokens: str = ""

    # Renpho
    renpho_email: str = ""
    renpho_password: str = ""

    # Garmin
    garmin_email: str = ""
    garmin_password: str = ""

    # Atlassian
    atlassian_url: str = ""
    atlassian_username: str = ""
    atlassian_api_token: str = ""
    atlassian_cloud: bool = True
    confluence_default_space: str = ""

    # OwnTracks
    owntracks_endpoint_url: str = "https://your-agent.com/pub"

    # Defaults for new users
    default_guest_token_budget: int = 5000
    # Stored as str to avoid pydantic-settings JSON parse issues with env vars.
    # Use parse_list() at the point of use.
    default_guest_modules: str = "research,file_manager,code_executor,knowledge,injective"

    # Module services (set via JSON in .env if overriding)
    module_services: dict[str, str] = {
        "research": "http://research:8000",
        "file_manager": "http://file-manager:8000",
        "injective": "http://injective:8000",
        "code_executor": "http://code-executor:8000",
        "knowledge": "http://knowledge:8000",
        "atlassian": "http://atlassian:8000",
        "renpho_biometrics": "http://renpho-biometrics:8000",
        "garmin": "http://garmin:8000",
        "claude_code": "http://claude-code:8000",
        "deployer": "http://deployer:8000",
        "scheduler": "http://scheduler:8000",
        "location": "http://location:8000",
    }

    # Model routing (set via JSON in .env if overriding)
    model_routing: dict[str, str] = {
        "default": "claude-sonnet-4-20250514",
        "summarization": "gpt-4o-mini",
        "complex_reasoning": "claude-sonnet-4-20250514",
        "embedding": "text-embedding-3-small",
        "memory_summarization": "gpt-4o-mini",
    }
    # Stored as str — comma-separated or JSON array.
    fallback_chain: str = "claude-sonnet-4-20250514,gpt-4o,gemini-2.0-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        """Sync top-level model settings into model_routing.

        The ``SUMMARIZATION_MODEL``, ``DEFAULT_MODEL``, and ``EMBEDDING_MODEL``
        env vars are the user-facing knobs.  ``model_routing`` is the internal
        dispatch table.  Keep them in sync so task_type-based routing honours
        the env vars.
        """
        self.model_routing["default"] = self.default_model
        self.model_routing["summarization"] = self.summarization_model
        self.model_routing["memory_summarization"] = self.summarization_model
        self.model_routing["embedding"] = self.embedding_model


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
