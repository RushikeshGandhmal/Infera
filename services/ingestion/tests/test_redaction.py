"""Tests for the regex redaction engine (always available, no extra deps)."""

from __future__ import annotations

from app.redaction import RegexRedactor, redact_event
from infera.schemas import InferenceLogEvent, InferenceStatus


def test_scrubs_common_pii():
    r = RegexRedactor()
    text = "Reach John at john.doe@example.com or +1 415 555 2671, SSN 123-45-6789."
    out, changed = r.redact(text)
    assert changed
    assert "[EMAIL]" in out and "[PHONE]" in out and "[SSN]" in out
    assert "john.doe@example.com" not in out
    assert "123-45-6789" not in out


def test_clean_text_unchanged():
    r = RegexRedactor()
    out, changed = r.redact("The capital of France is Paris.")
    assert not changed
    assert out == "The capital of France is Paris."


def test_redact_event_sets_flag_and_preserves_dedup_key():
    event = InferenceLogEvent(
        request_id="req_x",
        provider="openai",
        model="gpt-4o-mini",
        status=InferenceStatus.SUCCESS,
        input_preview="my email is a@b.com",
        output_preview="no pii here",
    )
    original_created_at = event.created_at
    redact_event(event)
    assert event.redacted is True
    assert "[EMAIL]" in event.input_preview
    assert event.output_preview == "no pii here"
    # dedup key must be untouched
    assert event.request_id == "req_x"
    assert event.created_at == original_created_at
