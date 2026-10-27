"""Redaction helpers.

No secret value is ever printed in full. Evidence shows the pattern name,
the file and line, and a masked value: the first two and last two
characters, with the middle replaced by asterisks. Short values are fully
masked. This module is the single place where masking happens, so a change
here changes every output format.
"""

from __future__ import annotations

import re


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
    """True for values that look like examples, not real credentials.

    Only the leading word counts: a substring match would silently
    discard real credentials that merely contain a placeholder word
    (``MySecretKey99`` contains ``secret``; ``contest-token-…``
    contains ``test`` and ``token``). A value is a placeholder when
    its first word starts with a placeholder word (``example-key-…``,
    ``changeme123``, ``test-key-…``) or is shorter than 8 characters.
    """
    lowered = value.strip().lower()
    if not lowered or len(lowered) < 8:
        return True
    placeholders = (
        "example", "sample", "dummy", "test", "changeme", "change",
        "your", "placeholder", "todo", "xxx",
        "password", "secret", "token", "123456", "abcdef",
    )
    first = re.split(r"[^a-z0-9]+", lowered)[0]
    return any(first.startswith(p) for p in placeholders)
