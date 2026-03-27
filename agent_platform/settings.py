import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = "agent-platform"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server settings
    server_host: str = "0.0.0.0"  # noqa: S104
    server_port: int = 5000
    server_root_path: str = ""

    # Logging
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_platform"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Pagination
    pagination_default_limit: int = 20
    pagination_max_limit: int = 100

    # Auth — JSON mapping of API keys to tenant IDs
    # Example: {"sk-tenant1-secret": "tenant_1", "sk-tenant2-secret": "tenant_2"}
    api_keys: str = "{}"

    # Run Agent
    run_max_iterations: int = 10
    allowed_models: str = (
        '["gpt-4o", "gpt-4o-mini", "gpt-4-turbo",'
        ' "claude-sonnet-4-5-20250514", "claude-haiku-4-5-20251001",'
        ' "gemini-2.5-flash", "gemini-2.5-pro"]'
    )

    @property
    def root_dir(self) -> str:
        """Return the root directory of the application."""
        return os.path.dirname(os.path.abspath(__file__))


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
