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
