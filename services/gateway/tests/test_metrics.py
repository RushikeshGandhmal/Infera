from __future__ import annotations

import math

from app.routers.metrics import _empty, _float, _int


def test_clickhouse_number_coercion_handles_empty_aggregate_values() -> None:
    assert _int(None) == 0
    assert _int(math.nan) == 0
    assert _int("12") == 12
    assert _int("not-a-number") == 0

    assert _float(None) == 0.0
    assert _float(math.nan) == 0.0
    assert _float("12.5") == 12.5
    assert _float("not-a-number") == 0.0


def test_empty_metrics_summary_shape_matches_metrics_response() -> None:
    data = _empty("24h", "unreachable")

    assert data["window"] == "24h"
    assert data["error"] == "unreachable"
    assert data["totals"]["requests"] == 0
    assert data["totals"]["total_cost_usd"] == 0.0
    assert data["timeseries"] == []
    assert data["by_provider"] == []
    assert data["by_model"] == []
