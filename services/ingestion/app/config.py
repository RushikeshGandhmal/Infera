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

    # Worker (consumer side)
    consumer_group: str = "infera-ingestion-worker"
    poll_timeout_ms: int = 1000  # how long a poll waits for records
    max_records: int = 500  # batch size pulled per poll (ClickHouse likes batches)
    insert_max_retries: int = 3  # retry a failed ClickHouse insert before giving up

    # ClickHouse connection (HTTP interface). On the host use localhost; inside
    # Docker use "clickhouse".
    clickhouse_host: str = "localhost"
    clickhouse_http_port: int = 8123
    clickhouse_user: str = "infera"
    clickhouse_password: str = "infera"
    clickhouse_db: str = "infera"


@lru_cache
def get_settings() -> Settings:
    """Cached so the env is read once per process."""
    return Settings()
