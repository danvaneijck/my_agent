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

    # Production mode — enables strict validation of required secrets at startup
    production_mode: bool = False

    # Database (no default password — must be set via env)
    database_url: str = "postgresql+asyncpg://agent:CHANGEME@postgres:5432/agent"

    # Redis (set REDIS_PASSWORD in .env for production)
    redis_url: str = "redis://redis:6379"
    redis_password: str = ""

    # MinIO (no default credentials — must be set via env)
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "CHANGEME"

    # Inter-service authentication token (required for production)
    service_auth_token: str = ""
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
    slack_signing_secret: str = ""

    # Agent
    orchestrator_url: str = "http://core:8000"
    max_agent_iterations: int = 10
    conversation_timeout_minutes: int = 30
    working_memory_messages: int = 12
    # Reduced history for standalone messages (no prior-context references)
    minimal_memory_messages: int = 2

    # Tool execution timeout (seconds) for module HTTP calls
    tool_execution_timeout: int = 120
    # Modules that need extra time (Selenium, long-running tasks)
    # uses tool_execution_timeout; all others use 30s default
    slow_modules: str = "garmin,renpho_biometrics,claude_code,deployer"

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

    # Web portal
    portal_api_key: str = ""
    portal_user_id: str = ""
    portal_base_url: str = "http://localhost:8080"  # Frontend base URL (no trailing slash)
    # Discord OAuth2 (for portal login)
    discord_client_id: str = ""
    discord_client_secret: str = ""
    portal_oauth_redirect_uri: str = "http://localhost:8080/auth/callback"
    portal_jwt_secret: str = ""

    # Google OAuth2 (for portal login)
    google_client_id: str = ""
    google_client_secret: str = ""

    # Slack OAuth2 (for portal login)
    slack_client_id: str = ""
    slack_client_secret: str = ""

    # Credential encryption (Fernet key for encrypting user credentials at rest)
    credential_encryption_key: str = ""

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

    # Benchmarker (fallback credentials - users can configure per-user credentials in portal)
    benchmarker_api_url: str = ""
    benchmarker_api_key: str = ""

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

    # Git Platform (GitHub / Bitbucket)
    git_platform_provider: str = "github"  # "github" or "bitbucket"
    git_platform_token: str = ""  # GitHub PAT or Bitbucket app password
    git_platform_username: str = ""  # Required for Bitbucket (app password owner)
    git_platform_base_url: str = "https://api.github.com"  # or "https://api.bitbucket.org/2.0"

    # Deployment banner — shown in the portal when the configured workflow is running
    # Set DEPLOY_WORKFLOW_REPO_OWNER and DEPLOY_WORKFLOW_REPO_NAME to the GitHub repo
    # that runs the deployment workflow (e.g. "danvaneijck" / "my_agent").
    # DEPLOY_WORKFLOW_NAME is the workflow's "name:" field in the YAML file.
    # Uses git_platform_token for authentication (works on public repos without a token too).
    deploy_workflow_repo_owner: str = ""
    deploy_workflow_repo_name: str = ""
    deploy_workflow_name: str = "Build and Push Docker Images"

    # GitHub OAuth (for portal git credential setup)
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    # Bitbucket OAuth (for portal git credential setup)
    bitbucket_oauth_client_id: str = ""
    bitbucket_oauth_client_secret: str = ""

    # Git OAuth redirect base (provider-specific path appended: /github/oauth/callback, /bitbucket/oauth/callback)
    git_oauth_redirect_uri: str = "http://localhost:8080/api/settings/credentials"

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
        "git_platform": "http://git-platform:8000",
        "project_planner": "http://project-planner:8000",
        "skills_modules": "http://skills-modules:8000",
        "weather": "http://weather:8000",
        "benchmarker": "http://benchmarker:8000",
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
        """Post-init hook to sync derived settings.

        - Syncs top-level model settings into model_routing
        - Injects redis_password into redis_url if provided
        - Validates required secrets in production mode
        """
        self.model_routing["default"] = self.default_model
        self.model_routing["summarization"] = self.summarization_model
        self.model_routing["memory_summarization"] = self.summarization_model
        self.model_routing["embedding"] = self.embedding_model

        # Inject Redis password into URL if set and not already in URL
        if self.redis_password and ":@" not in self.redis_url and "@" not in self.redis_url:
            # redis://redis:6379 → redis://:password@redis:6379
            self.redis_url = self.redis_url.replace("redis://", f"redis://:{self.redis_password}@", 1)

        # Strict validation in production mode
        if self.production_mode:
            errors: list[str] = []
            if not self.service_auth_token:
                errors.append("SERVICE_AUTH_TOKEN must be set in production")
            if not self.credential_encryption_key:
                errors.append("CREDENTIAL_ENCRYPTION_KEY must be set in production")
            if not self.portal_jwt_secret:
                errors.append("PORTAL_JWT_SECRET must be set in production")
            if "CHANGEME" in self.database_url:
                errors.append("DATABASE_URL still contains default CHANGEME password")
            if self.minio_secret_key in ("CHANGEME", "minioadmin"):
                errors.append("MINIO_SECRET_KEY must be changed from default")
            if errors:
                raise ValueError(
                    "Production mode validation failed:\n  - " + "\n  - ".join(errors)
                )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
