"""Ingestion worker: consumes inference events from Redpanda and stores them.

Flow per loop:
  1. pull a batch of messages from the raw topic
  2. parse/validate each into an InferenceLogEvent
     - good ones are PII-redacted and added to the batch to store
     - bad ones ("poison" messages) are routed to the DLQ so one malformed
       message never blocks the pipeline
  3. insert the good batch into ClickHouse (with a few retries)
  4. commit offsets ONLY after a successful store

Step 4 is what makes this at-least-once: if the worker crashes before committing,
those messages are re-read on restart and re-inserted. Duplicates are harmless
because ClickHouse's ReplacingMergeTree collapses rows with the same dedup key.

Run with:  python -m app.consumer
"""

from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from infera.schemas import InferenceLogEvent
from pydantic import ValidationError

from .clickhouse_writer import ClickHouseWriter
from .config import get_settings
from .redaction import redact_event

logger = logging.getLogger("infera.worker")


async def _insert_with_retry(writer: ClickHouseWriter, events: list[InferenceLogEvent]) -> bool:
    """Insert a batch, retrying with backoff. Returns True on success."""
    s = get_settings()
    for attempt in range(1, s.insert_max_retries + 1):
        try:
            # The ClickHouse client is sync; run it off the event loop so we
            # don't block other async work.
            await asyncio.to_thread(writer.insert_events, events)
            return True
        except Exception as exc:  # noqa: BLE001 - we want to retry on anything
            wait = 0.5 * (2 ** (attempt - 1))  # 0.5s, 1s, 2s, ...
            logger.warning(
                "ClickHouse insert failed (attempt %d/%d): %s; retrying in %.1fs",
                attempt,
                s.insert_max_retries,
                exc,
                wait,
            )
            await asyncio.sleep(wait)
    return False


async def run() -> None:
    s = get_settings()

    consumer = AIOKafkaConsumer(
        s.topic_raw,
        bootstrap_servers=s.kafka_bootstrap_servers,
        group_id=s.consumer_group,
        enable_auto_commit=False,  # we commit manually, only after storing
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=s.kafka_bootstrap_servers, acks="all")
    writer = ClickHouseWriter()

    await consumer.start()
    await producer.start()
    logger.info(
        "worker started: consuming '%s' (group=%s) -> ClickHouse %s:%d",
        s.topic_raw,
        s.consumer_group,
        s.clickhouse_host,
        s.clickhouse_http_port,
    )

    try:
        while True:
            batches = await consumer.getmany(
                timeout_ms=s.poll_timeout_ms, max_records=s.max_records
            )
            if not batches:
                continue

            valid: list[InferenceLogEvent] = []
            bad = 0
            for _tp, msgs in batches.items():
                for msg in msgs:
                    try:
                        event = InferenceLogEvent.model_validate_json(msg.value)
                        valid.append(redact_event(event))
                    except ValidationError as exc:
                        bad += 1
                        # Poison message: park it in the DLQ for later inspection
                        # and keep the pipeline moving.
                        await producer.send_and_wait(
                            s.topic_dlq, value=msg.value, key=msg.key
                        )
                        logger.warning("routed bad message to DLQ: %s", exc)

            if valid:
                ok = await _insert_with_retry(writer, valid)
                if not ok:
                    # Don't commit — leave offsets so these messages are
                    # reprocessed (by us after ClickHouse recovers, or by a
                    # restarted worker). Back off briefly before trying again.
                    logger.error(
                        "giving up on batch of %d after retries; not committing", len(valid)
                    )
                    await asyncio.sleep(2.0)
                    continue

            # Both the stored events and any DLQ-routed ones are now handled.
            await consumer.commit()
            logger.info("stored %d events (%d to DLQ)", len(valid), bad)
    finally:
        await consumer.stop()
        await producer.stop()
        writer.close()
        logger.info("worker stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
