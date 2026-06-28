"""Basic SDK tests using the fake provider — no network or API key needed.

Run with:  uv run pytest   (from packages/infera-sdk)
"""

from __future__ import annotations

import pytest

from infera import InferaClient, InferenceStatus
from infera.providers import MockProvider
from infera.schemas import InferenceLogEvent


def _capture(client: InferaClient) -> list[InferenceLogEvent]:
    """Intercept events the client would ship, so we can assert on them."""
    events: list[InferenceLogEvent] = []
    client._emit = events.append  # type: ignore[method-assign]
    return events


@pytest.fixture
def client() -> InferaClient:
    # No ingestion_url -> the shipper is a no-op; we capture events directly.
    return InferaClient(provider=MockProvider(reply="hello there"), auto_start=False)


async def test_chat_returns_result_and_logs(client: InferaClient) -> None:
    events = _capture(client)
    result = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock/model",
        session_id="sess_1",
    )

    assert result.text == "hello there"
    assert result.status is InferenceStatus.SUCCESS
    assert result.latency_ms > 0
    assert result.usage.total_tokens > 0

    assert len(events) == 1
    ev = events[0]
    assert ev.session_id == "sess_1"
    assert ev.status is InferenceStatus.SUCCESS
    assert ev.provider == "mock"
    assert ev.total_tokens == result.usage.total_tokens


async def test_stream_yields_and_logs_ttft(client: InferaClient) -> None:
    events = _capture(client)
    pieces = [chunk async for chunk in client.stream(
        messages=[{"role": "user", "content": "hi"}],
        model="mock/model",
    )]

    assert "".join(pieces) == "hello there"
    assert len(events) == 1
    ev = events[0]
    assert ev.status is InferenceStatus.SUCCESS
    assert ev.ttft_ms is not None and ev.ttft_ms > 0  # first-token time captured


async def test_redaction_scrubs_previews() -> None:
    client = InferaClient(
        provider=MockProvider(reply="contact me at a@b.com"),
        redact_previews=True,
        auto_start=False,
    )
    events = _capture(client)
    await client.chat(messages=[{"role": "user", "content": "my email is x@y.com"}], model="mock/model")

    ev = events[0]
    assert ev.redacted is True
    assert "x@y.com" not in (ev.input_preview or "")
    assert "a@b.com" not in (ev.output_preview or "")
