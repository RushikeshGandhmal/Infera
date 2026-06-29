"""Ingestion settings, read from environment variables (and a local .env file).

The same variable names are used in docker-compose, so the service runs the same
way locally and in a container. When running on the host (outside Docker), point
KAFKA_BOOTSTRAP_SERVERS at localhost:19092 — the broker's external listener.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Broker. Inside Docker this is "redpanda:9092"; on the host "localhost:19092".
    kafka_bootstrap_servers: str = "localhost:19092"

    # Topics. Raw events land here; anything we can't process goes to the DLQ.
    topic_raw: str = "inference.logs.raw"
    topic_dlq: str = "inference.logs.dlq"


@lru_cache
def get_settings() -> Settings:
    """Cached so the env is read once per process."""
    return Settings()
