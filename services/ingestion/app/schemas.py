"""The ingestion request contract.

We reuse the SDK's InferenceLogEvent as the source of truth for a log's shape, so
the producer (SDK) and the receiver (this service) can never drift apart. FastAPI
validates incoming payloads against this automatically and rejects malformed ones
with a 422 before anything is produced.
"""

from __future__ import annotations

from infera.schemas import InferenceLogEvent
from pydantic import BaseModel


class LogBatch(BaseModel):
    """A batch of events, matching what the SDK shipper POSTs: {"events": [...]}."""

    events: list[InferenceLogEvent]
