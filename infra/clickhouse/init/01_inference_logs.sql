-- Inference logs: one row per LLM call, shipped by the Infera SDK.
--
-- This is high-volume, append-only analytics data — the reason we use ClickHouse
-- here instead of Postgres. The table is tuned for the queries the dashboards run:
-- time-range scans grouped by provider/model (latency percentiles, throughput,
-- error rate, token usage, cost).
--
-- The columns mirror the SDK's InferenceLogEvent so the contract stays 1:1 from
-- SDK -> ingestion -> storage -> dashboards.

CREATE DATABASE IF NOT EXISTS infera;

CREATE TABLE IF NOT EXISTS infera.inference_logs
(
    -- identity / tracing
    request_id        String,                         -- unique per call; links to a Postgres message
    session_id        String DEFAULT '',
    conversation_id   String DEFAULT '',

    -- which model answered. Few distinct values, so LowCardinality stores them as
    -- a small dictionary -> big compression win and faster GROUP BY.
    provider          LowCardinality(String),
    model             LowCardinality(String),

    -- outcome of the call
    status            LowCardinality(String),         -- success | error | cancelled
    error_type        String DEFAULT '',
    error_message     String DEFAULT '',

    -- latency
    latency_ms        Float64,
    ttft_ms           Nullable(Float64),              -- time-to-first-token; only set for streaming

    -- usage / cost
    prompt_tokens     UInt32 DEFAULT 0,
    completion_tokens UInt32 DEFAULT 0,
    total_tokens      UInt32 DEFAULT 0,
    cost_usd          Nullable(Float64),              -- not every provider reports cost

    -- short debugging snippets (PII-redacted before they reach this table)
    input_preview     String DEFAULT '',
    output_preview    String DEFAULT '',
    redacted          UInt8  DEFAULT 0,

    -- timing: client time vs server ingest time. The gap measures pipeline lag.
    created_at        DateTime64(3, 'UTC'),
    ingested_at       DateTime64(3, 'UTC') DEFAULT now64(3),

    -- free-form extras (app version, flags, ...) kept as JSON text for flexibility
    metadata          String DEFAULT '{}'
)
-- ReplacingMergeTree collapses rows sharing the ORDER BY key, keeping the latest
-- by `ingested_at`. Because a redelivered event carries the same request_id and
-- created_at, duplicate deliveries from the broker eventually dedupe themselves —
-- our idempotency safety net for at-least-once delivery.
ENGINE = ReplacingMergeTree(ingested_at)
-- Daily partitions: time-range queries prune to just the days they need, and
-- dropping old data (via TTL) becomes a cheap whole-partition drop.
PARTITION BY toYYYYMMDD(created_at)
-- Sort key doubles as the dedup key. Leading with created_at makes the common
-- "last N hours, grouped by provider/model" queries fast range scans.
ORDER BY (created_at, provider, model, request_id)
-- Retention: keep 90 days of raw logs, then auto-expire. Adjust per cost/compliance.
TTL toDateTime(created_at) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
