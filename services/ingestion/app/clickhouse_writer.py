"""Writes inference events into ClickHouse in batches.

ClickHouse strongly prefers large inserts over many tiny ones, so the worker
hands us a whole batch at once. We map each event to a row in the exact column
order below (mirroring infra/clickhouse/init/01_inference_logs.sql).

Two columns are intentionally NOT written here:
  - ingested_at: filled by the table's DEFAULT now64(3) — this is the server-side
    arrival time, and the gap from created_at measures pipeline lag.
  - we always pass the event's ORIGINAL created_at (never "now"), because the
    dedup key includes created_at; regenerating it would silently break dedup.
"""

from __future__ import annotations

import json

from infera.schemas import InferenceLogEvent

from .config import get_settings

# Column order used for every insert. Must match the rows built in _to_row.
_COLUMNS = [
    "request_id",
    "session_id",
    "conversation_id",
    "provider",
    "model",
    "status",
    "error_type",
    "error_message",
    "latency_ms",
    "ttft_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "input_preview",
    "output_preview",
    "redacted",
    "created_at",
    "metadata",
]


class ClickHouseWriter:
    """Thin wrapper around a ClickHouse client for batch inserts."""

    def __init__(self) -> None:
        import clickhouse_connect

        s = get_settings()
        self._client = clickhouse_connect.get_client(
            host=s.clickhouse_host,
            port=s.clickhouse_http_port,
            username=s.clickhouse_user,
            password=s.clickhouse_password,
            database=s.clickhouse_db,
        )
        self._table = "inference_logs"

    def insert_events(self, events: list[InferenceLogEvent]) -> None:
        """Insert a batch of events. Raises on failure so the caller can retry."""
        rows = [self._to_row(e) for e in events]
        self._client.insert(self._table, rows, column_names=_COLUMNS)

    @staticmethod
    def _to_row(e: InferenceLogEvent) -> list:
        # Non-null string columns get "" instead of None; Nullable columns
        # (ttft_ms, cost_usd) keep None so they land as NULL.
        return [
            e.request_id,
            e.session_id or "",
            e.conversation_id or "",
            e.provider,
            e.model,
            e.status.value,
            e.error_type or "",
            e.error_message or "",
            e.latency_ms,
            e.ttft_ms,
            e.prompt_tokens,
            e.completion_tokens,
            e.total_tokens,
            e.cost_usd,
            e.input_preview or "",
            e.output_preview or "",
            1 if e.redacted else 0,
            e.created_at,  # original client time — preserved for dedup
            json.dumps(e.metadata or {}),
        ]

    def close(self) -> None:
        self._client.close()
