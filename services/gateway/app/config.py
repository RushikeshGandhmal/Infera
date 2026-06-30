"""Gateway settings, read from environment variables (and a local .env file).

The same variable names are used in docker-compose, so the service runs the same
way locally and in a container. When running on the host (outside Docker), set
POSTGRES_HOST=localhost since "postgres" only resolves inside the compose network.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres connection
    postgres_user: str = "infera"
    postgres_password: str = "infera"
    postgres_db: str = "infera"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # LLM access (OpenRouter). If no key is set, the gateway falls back to a
    # mock provider so it still runs end-to-end without spending anything.
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_title: str | None = "Infera"
    openrouter_app_url: str | None = None
    default_model: str = "openai/gpt-4o-mini"

    # Where the SDK ships inference logs. None = don't ship (until ingestion exists).
    ingestion_url: str | None = None
    redact_previews: bool = False

    # ClickHouse (read-only) — powers the in-app /metrics page. Same names as the
    # ingestion service, so the value source is consistent across the stack.
    clickhouse_host: str = "localhost"
    clickhouse_http_port: int = 8123
    clickhouse_user: str = "infera"
    clickhouse_password: str = "infera"
    clickhouse_db: str = "infera"

    # How many recent messages to send back to the model as context.
    max_context_messages: int = 20

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached so the env is read once per process."""
    return Settings()
