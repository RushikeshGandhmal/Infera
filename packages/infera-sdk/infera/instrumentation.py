"""A stopwatch for one LLM call.

Tracks two numbers that matter for LLM observability:
- latency_ms: total time for the call.
- ttft_ms: time until the first streamed token arrives (what users actually feel).
"""

from __future__ import annotations

from time import perf_counter
from typing import Optional


class CallTimer:
    """Times a single call. Uses a monotonic clock so it's unaffected by clock changes."""

    def __init__(self) -> None:
        self._start = perf_counter()
        self._first_token_at: Optional[float] = None
        self._end: Optional[float] = None

    def mark_first_token(self) -> None:
        """Call when the first streamed token arrives (only the first one counts)."""
        if self._first_token_at is None:
            self._first_token_at = perf_counter()

    def stop(self) -> None:
        """Call when the call finishes."""
        if self._end is None:
            self._end = perf_counter()

    @property
    def latency_ms(self) -> float:
        end = self._end if self._end is not None else perf_counter()
        return (end - self._start) * 1000.0

    @property
    def ttft_ms(self) -> Optional[float]:
        if self._first_token_at is None:
            return None
        return (self._first_token_at - self._start) * 1000.0
