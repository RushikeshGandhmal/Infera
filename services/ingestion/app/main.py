"""Ingestion API entrypoint.

The job here is deliberately small: validate the incoming batch, hand it to the
broker, and acknowledge fast. All the heavy work (parsing, PII redaction, storage)
happens later in the worker. This keeps the SDK's request path quick and lets the
broker absorb bursts.

Flow:  SDK  --POST /v1/logs-->  validate  -->  produce to Redpanda  -->  202
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .config import get_settings
from .producer import get_producer, start_producer, stop_producer
from .schemas import LogBatch


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_producer()
    try:
        yield
    finally:
        await stop_producer()


app = FastAPI(title="Infera Ingestion", lifespan=lifespan)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/logs", status_code=202, tags=["ingestion"])
async def ingest_logs(batch: LogBatch) -> dict[str, int]:
    """Accept a batch of inference logs and produce each to the raw topic.

    Returns 202 (Accepted) once the broker has durably taken the events. If the
    broker is unavailable we return 503 so the SDK keeps the events and retries —
    we never pretend to have stored something we didn't.
    """
    settings = get_settings()
    producer = get_producer()

    try:
        # Key by session (falling back to request_id) so all events for one
        # conversation land on the same partition and stay in order.
        futures = []
        for event in batch.events:
            key = (event.session_id or event.request_id).encode()
            value = event.model_dump_json().encode()
            futures.append(await producer.send(settings.topic_raw, value=value, key=key))
        await asyncio.gather(*futures)
    except Exception as exc:  # broker down / send failed
        raise HTTPException(status_code=503, detail="ingestion temporarily unavailable") from exc

    return {"accepted": len(batch.events)}
