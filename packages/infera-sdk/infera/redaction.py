"""Optional client-side scrubbing for previews.

The strong redaction runs server-side in the worker (Presidio). This is a light,
dependency-free first pass that removes obvious PII (emails, phones, card-like
numbers) before previews ever leave the app process.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

_REPLACEMENTS = (
    (_EMAIL_RE, "[EMAIL]"),
    (_CARD_RE, "[CARD]"),
    (_PHONE_RE, "[PHONE]"),
)


def redact(text: str) -> tuple[str, bool]:
    """Return (scrubbed_text, was_anything_redacted)."""
    if not text:
        return text, False
    redacted = False
    for pattern, token in _REPLACEMENTS:
        text, n = pattern.subn(token, text)
        if n:
            redacted = True
    return text, redacted


def preview(text: str, *, limit: int = 500, do_redact: bool = False) -> tuple[str, bool]:
    """Build a short snippet of `text`, optionally redacted. Returns (snippet, was_redacted)."""
    if not text:
        return "", False
    snippet = text[:limit]
    if do_redact:
        return redact(snippet)
    return snippet, False
