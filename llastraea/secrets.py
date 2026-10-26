"""Secrets trial: scan files and git history for leaked credentials.

Rules that keep false positives down:
- Files under .git, __pycache__, node_modules, .venv/venv, dist, and
  build are skipped, as are binary files and files over the size cap.
- A generic ``key = value`` assignment only counts when the variable name
  mentions key/token/secret/password and the value is long enough and is
  not a placeholder (see redact.is_placeholder).
- Specific prefixes (AWS, GitHub, Slack, private keys) count on their own.
- Output never contains a full secret value; see redact.redact_value.
"""

from __future__ import annotations

import os
import re
import subprocess

from .models import Finding, Trial, trial_verdict
from .redact import is_placeholder, redact_value

MAX_FILE_BYTES = 1_048_576
MAX_HISTORY_BYTES = 5_000_000

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".tox", ".eggs",
}
SKIP_EXTS = {
    ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf",
    ".mp3", ".mp4", ".so", ".dll", ".exe",
}

# Well-known documentation examples. These are published by vendors as
# examples and are not real credentials; flagging them is noise.
KNOWN_EXAMPLES = {
    "AKIAIOSFODNN7EXAMPLE",
    "AKIAI44QH8DHBEXAMPLE",
}

# (name, regex, severity)
PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}"), "critical"),
    ("GitHub token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "critical"),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "critical"),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "critical"),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "critical"),
    ("Generic API key", re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\"']?([A-Za-z0-9_\-./]{16,})[\"']?"), "high"),
    ("Password assignment", re.compile(r"(?i)(?:password|passwd|pwd)\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']?"), "high"),
]


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def _iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in SKIP_EXTS:
                continue
            yield os.path.join(dirpath, name)


def _scan_text(text: str, evidence_prefix: str) -> list[Finding]:
    findings: list[Finding] = []
    for name, pattern, severity in PATTERNS:
        for match in pattern.finditer(text):
            if name == "Private key":
                findings.append(Finding(
                    severity, "Private key material in file",
                    f"{evidence_prefix}: {name}",
                    "Remove the key from the project, rotate it, and use a secret manager.",
                ))
                continue
            # For generic patterns the secret is capture group 1 when present.
            secret = match.group(1) if match.lastindex else match.group(0)
            if secret in KNOWN_EXAMPLES:
                continue
            if name in ("Generic API key", "Password assignment"):
                if is_placeholder(secret):
                    continue
            masked = redact_value(secret)
            findings.append(Finding(
                severity, f"Possible leaked {name.lower()}",
                f"{evidence_prefix}: {name} {masked}",
                "Rotate this credential and move it out of the project.",
            ))
    return findings


def _scan_file(path: str, root: str) -> list[Finding]:
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return []
        if _is_binary(path):
            return []
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return []
    rel = os.path.relpath(path, root)
    out: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for finding in _scan_text(line, f"{rel}:{lineno}"):
            out.append(finding)
    return out


def _scan_history(root: str) -> list[Finding]:
    """Scan git history diffs, capped, with the same patterns and masking."""
    git_dir = os.path.join(root, ".git")
    if not os.path.isdir(git_dir):
        return []
    try:
        proc = subprocess.run(
            ["git", "-C", root, "log", "--all", "-p", "--no-color",
             "--no-ext-diff"],
            capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    text = proc.stdout.decode("utf-8", "ignore")[:MAX_HISTORY_BYTES]
    findings: list[Finding] = []
    current_commit = "unknown"
    for line in text.splitlines():
        if line.startswith("commit "):
            current_commit = line.split()[1][:12]
        elif line.startswith("+") and not line.startswith("+++"):
            for finding in _scan_text(line[1:], f"git history {current_commit}"):
                findings.append(finding)
    return findings


def run_secrets_trial(root: str, include_history: bool = True) -> Trial:
    findings: list[Finding] = []
    for path in _iter_files(root):
        findings.extend(_scan_file(path, root))
    if include_history:
        findings.extend(_scan_history(root))
    # De-duplicate identical (severity, message, evidence) findings.
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.severity, finding.message, finding.evidence)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return Trial(
        name="Secrets",
        verdict=trial_verdict(unique),
        findings=unique,
        note="Files scanned; binary files and files over 1 MiB skipped.",
    )
