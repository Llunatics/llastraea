"""Redaction helpers.

No secret value is ever printed in full. Evidence shows the pattern name,
the file and line, and a masked value: the first two and last two
characters, with the middle replaced by asterisks. Short values are fully
masked. This module is the single place where masking happens, so a change
here changes every output format.
"""

from __future__ import annotations


def redact_value(value: str) -> str:
    """Return a masked form of *value* that cannot be used to recover it."""
    value = value.strip().strip("\"'").strip()
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}****{value[-2:]}"


def redact_line(line: str, secret: str) -> str:
    """Replace *secret* in *line* with its masked form, if present."""
    if not secret or secret not in line:
        return line
    return line.replace(secret, redact_value(secret))


def is_placeholder(value: str) -> bool:
    """True for values that look like examples, not real credentials."""
    lowered = value.strip().lower()
    placeholders = (
        "example", "sample", "dummy", "test", "changeme", "change-me",
        "your-", "your_", "placeholder", "todo", "xxx", "xxxx",
        "password", "secret", "token", "123456", "abcdef",
    )
    if not lowered or len(lowered) < 8:
        return True
    return any(p in lowered for p in placeholders)
