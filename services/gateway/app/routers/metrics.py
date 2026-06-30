"""Read-only metrics endpoint backed by ClickHouse.

Powers the in-app /metrics page: latency percentiles, throughput, error rate,
and per-provider / per-model breakdowns over a recent window. It reads the same
inference_logs table Grafana uses, but returns a small JSON shape the web app
can render directly (no Grafana embed needed).
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import clickhouse_connect
from fastapi import APIRouter, Query

from ..config import get_settings

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _int(value: Any) -> int:
    """Coerce a ClickHouse value to int, treating None/NaN as 0.

    Empty windows make aggregates like quantile() return NaN, which is truthy
    so an `x or 0` guard would not catch it and int(NaN) would raise.
    """
    if value is None:
        return 0
    try:
        if isinstance(value, float) and math.isnan(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    """Coerce a ClickHouse value to float, treating None/NaN as 0.0."""
    if value is None:
        return 0.0
    try:
        f = float(value)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0


# window -> (lookback hours, timeseries bucket in seconds)
_WINDOWS: dict[str, tuple[int, int]] = {
    "1h": (1, 60),        # 1-minute buckets
    "24h": (24, 1800),    # 30-minute buckets
    "7d": (168, 21600),   # 6-hour buckets
}


def _query_all(window: str) -> dict[str, Any]:
    hours, bucket = _WINDOWS.get(window, _WINDOWS["24h"])
    s = get_settings()
    client = clickhouse_connect.get_client(
        host=s.clickhouse_host,
        port=s.clickhouse_http_port,
        username=s.clickhouse_user,
        password=s.clickhouse_password,
        database=s.clickhouse_db,
    )
    since = f"now() - INTERVAL {hours} HOUR"
    try:
        totals = client.query(
            f"""
            SELECT
                count() AS requests,
                countIf(status = 'error') AS errors,
                round(quantile(0.50)(latency_ms)) AS p50,
                round(quantile(0.95)(latency_ms)) AS p95,
                round(quantile(0.99)(latency_ms)) AS p99,
                round(avgIf(ttft_ms, isNotNull(ttft_ms))) AS avg_ttft,
                sum(total_tokens) AS tokens,
                round(sum(cost_usd), 4) AS cost
            FROM inference_logs
            WHERE created_at >= {since}
            """
        ).first_row

        ts_rows = client.query(
            f"""
            SELECT
                toStartOfInterval(created_at, INTERVAL {bucket} SECOND) AS t,
                count() AS requests,
                countIf(status = 'error') AS errors,
                round(quantile(0.95)(latency_ms)) AS p95
            FROM inference_logs
            WHERE created_at >= {since}
            GROUP BY t ORDER BY t
            """
        ).result_rows

        by_provider = client.query(
            f"""
            SELECT provider, count() AS requests,
                   round(quantile(0.95)(latency_ms)) AS p95,
                   countIf(status = 'error') AS errors,
                   sum(total_tokens) AS tokens,
                   round(sum(cost_usd), 4) AS cost
            FROM inference_logs
            WHERE created_at >= {since}
            GROUP BY provider ORDER BY requests DESC
            """
        ).result_rows

        by_model = client.query(
            f"""
            SELECT model, count() AS requests,
                   round(quantile(0.95)(latency_ms)) AS p95,
                   countIf(status = 'error') AS errors,
                   sum(total_tokens) AS tokens
            FROM inference_logs
            WHERE created_at >= {since}
            GROUP BY model ORDER BY requests DESC
            """
        ).result_rows
    finally:
        client.close()

    requests = _int(totals[0])
    errors = _int(totals[1])
    error_rate = round(100 * errors / requests, 2) if requests else 0.0

    return {
        "window": window,
        "totals": {
            "requests": requests,
            "error_rate": error_rate,
            "p50_ms": _int(totals[2]),
            "p95_ms": _int(totals[3]),
            "p99_ms": _int(totals[4]),
            "avg_ttft_ms": _int(totals[5]),
            "total_tokens": _int(totals[6]),
            "total_cost_usd": _float(totals[7]),
        },
        "timeseries": [
            {
                "t": row[0].isoformat(),
                "requests": _int(row[1]),
                "errors": _int(row[2]),
                "p95_ms": _int(row[3]),
            }
            for row in ts_rows
        ],
        "by_provider": [
            {
                "provider": row[0],
                "requests": _int(row[1]),
                "p95_ms": _int(row[2]),
                "errors": _int(row[3]),
                "tokens": _int(row[4]),
                "cost_usd": _float(row[5]),
            }
            for row in by_provider
        ],
        "by_model": [
            {
                "model": row[0],
                "requests": _int(row[1]),
                "p95_ms": _int(row[2]),
                "errors": _int(row[3]),
                "tokens": _int(row[4]),
            }
            for row in by_model
        ],
    }


def _empty(window: str, error: str | None = None) -> dict[str, Any]:
    return {
        "window": window,
        "error": error,
        "totals": {
            "requests": 0, "error_rate": 0.0, "p50_ms": 0, "p95_ms": 0,
            "p99_ms": 0, "avg_ttft_ms": 0, "total_tokens": 0, "total_cost_usd": 0.0,
        },
        "timeseries": [],
        "by_provider": [],
        "by_model": [],
    }


@router.get("/summary")
async def metrics_summary(
    window: str = Query("24h", pattern="^(1h|24h|7d)$"),
) -> dict[str, Any]:
    """Aggregated inference metrics for the window. Read-only.

    The ClickHouse client is synchronous, so we run it in a worker thread to
    keep the event loop free. If ClickHouse is unreachable we degrade to empty
    data instead of failing the page.
    """
    try:
        return await asyncio.to_thread(_query_all, window)
    except Exception as exc:  # noqa: BLE001 - the UI should never hard-fail
        return _empty(window, str(exc))
