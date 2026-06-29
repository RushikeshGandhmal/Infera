"""PII redaction for stored previews.

Previews (the short input/output snippets) can contain personal data. We scrub
them here, server-side, just before they're written to ClickHouse — so sensitive
values never reach storage. This is the strong second layer; the SDK does a
light client-side pass first (defense in depth).

Redaction only rewrites preview text. It never touches request_id or created_at,
so the ClickHouse dedup key is unaffected.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Protocol

from infera.schemas import InferenceLogEvent

from .config import get_settings

logger = logging.getLogger("infera.redaction")


class Redactor(Protocol):
    def redact(self, text: str) -> tuple[str, bool]:
        """Return (scrubbed_text, was_anything_redacted)."""
        ...


_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")

# Order matters: the looser phone pattern can swallow IPs/cards, so the more
# specific rules run first.
_RULES = (
    (_EMAIL_RE, "[EMAIL]"),
    (_SSN_RE, "[SSN]"),
    (_CARD_RE, "[CARD]"),
    (_IP_RE, "[IP]"),
    (_PHONE_RE, "[PHONE]"),
)


class RegexRedactor:
    """Deterministic, dependency-free scrub of common structured identifiers."""

    def redact(self, text: str) -> tuple[str, bool]:
        if not text:
            return text, False
        changed = False
        for pattern, token in _RULES:
            text, n = pattern.subn(token, text)
            if n:
                changed = True
        return text, changed


class PresidioRedactor:
    """Deep PII detection via Microsoft Presidio (optional dependency).

    Constructing this imports Presidio and loads its NLP model. If either is
    missing, construction raises and the factory falls back to the regex engine.
    """

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()

    def redact(self, text: str) -> tuple[str, bool]:
        if not text:
            return text, False
        results = self._analyzer.analyze(text=text, language="en")
        if not results:
            return text, False
        scrubbed = self._anonymizer.anonymize(text=text, analyzer_results=results)
        return scrubbed.text, True


class _NoopRedactor:
    def redact(self, text: str) -> tuple[str, bool]:
        return text, False


@lru_cache
def get_redactor() -> Redactor:
    """Build the configured redactor once per process (falls back gracefully)."""
    engine = get_settings().redaction_engine.lower()
    if engine == "none":
        logger.info("PII redaction disabled")
        return _NoopRedactor()
    if engine == "presidio":
        try:
            redactor = PresidioRedactor()
            logger.info("PII redaction: Presidio engine")
            return redactor
        except Exception as exc:  # noqa: BLE001 - any import/model error -> fall back
            logger.warning("Presidio unavailable (%s); using regex engine", exc)
            return RegexRedactor()
    logger.info("PII redaction: regex engine")
    return RegexRedactor()


def redact_event(event: InferenceLogEvent) -> InferenceLogEvent:
    """Scrub the event's previews in place; set `redacted=True` if anything changed."""
    redactor = get_redactor()
    changed = False
    if event.input_preview:
        event.input_preview, c = redactor.redact(event.input_preview)
        changed = changed or c
    if event.output_preview:
        event.output_preview, c = redactor.redact(event.output_preview)
        changed = changed or c
    if changed:
        event.redacted = True
    return event
