"""Kafka/Redpanda producer lifecycle.

One producer per process, started on app startup and stopped on shutdown. We use
acks="all" + idempotent delivery so a produced event isn't silently lost and isn't
duplicated by producer-side retries.
"""

from __future__ import annotations

from aiokafka import AIOKafkaProducer

from .config import get_settings

_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    global _producer
    settings = get_settings()
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        acks="all",  # wait for the broker to durably accept the record
        enable_idempotence=True,  # producer retries won't create duplicates
        linger_ms=5,  # tiny batching window for throughput
    )
    await _producer.start()


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


def get_producer() -> AIOKafkaProducer:
    if _producer is None:
        raise RuntimeError("producer not started")
    return _producer
