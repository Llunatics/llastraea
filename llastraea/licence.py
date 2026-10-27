"""Licence and hygiene trial: licence detection and project files.

Licence names are detected from the licence file text, not from the
file name. A copyleft licence (GPL/AGPL) is reported as a note, not a
finding: it is a compatibility fact, not a security failure.
"""

from __future__ import annotations

import os
import re

from .models import Finding, Trial, trial_verdict

LICENCE_PATTERNS = [
    ("MIT", re.compile(r"MIT License|Permission is hereby granted, free of charge")),
    ("Apache-2.0", re.compile(r"Apache License.{0,30}Version 2\.0", re.DOTALL)),
    ("GPL-3.0", re.compile(r"GNU GENERAL PUBLIC LICENSE.{0,30}Version 3", re.DOTALL)),
    ("GPL-2.0", re.compile(r"GNU GENERAL PUBLIC LICENSE.{0,30}Version 2", re.DOTALL)),
    ("BSD-3-Clause", re.compile(r"Redistribution and use in source and binary forms")),
    ("BSD-2-Clause", re.compile(r"Redistribution and use in source and binary forms")),
    ("MPL-2.0", re.compile(r"Mozilla Public License Version 2\.0")),
    ("Unlicense", re.compile(r"This is free and unencumbered software released into the public domain")),
]


def _find_file(root: str, names: list[str]) -> str | None:
    """Find a project file, root first, skipping vendored directories.

    The root is yielded first by os.walk, so a root LICENSE/README
    always wins. Skipped directories match the secrets and deps
    trials: a LICENSE inside .venv is the environment's, not the
    project's, and must not be mistaken for it.
    """
    skip = (".git", "node_modules", ".venv", "venv",
            "dist", "build", ".tox", ".eggs")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if name.upper() in names:
                return os.path.join(dirpath, name)
    return None


def detect_licence(root: str) -> str | None:
    path = _find_file(root, {"LICENSE", "LICENSE.TXT", "LICENSE.MD", "LICENCE", "COPYING"})
    if not path:
        return None
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return None
    for name, pattern in LICENCE_PATTERNS:
        if pattern.search(text):
            return name
    return "Unknown"


def run_licence_trial(root: str) -> Trial:
    findings: list[Finding] = []
    licence = detect_licence(root)
    if licence is None:
        findings.append(Finding(
            "medium", "No licence file found",
            "LICENSE: missing",
            "Add a licence file so downstream users know how the code may be used.",
        ))
    elif licence == "Unknown":
        findings.append(Finding(
            "low", "Licence file present but type not recognised",
            "LICENSE: unrecognised text",
            "Use a standard licence text so tooling can identify it.",
        ))
    readme = _find_file(root, {"README", "README.MD", "README.TXT", "README.RST"})
    if readme is None:
        findings.append(Finding(
            "low", "No README found",
            "README: missing",
            "Add a README describing what the project does and how to use it.",
        ))
    ci = os.path.isdir(os.path.join(root, ".github", "workflows")) or os.path.exists(
        os.path.join(root, ".gitlab-ci.yml"))
    note_parts = []
    if licence:
        note_parts.append(f"Licence: {licence}.")
    if licence in ("GPL-3.0", "GPL-2.0"):
        note_parts.append("Copyleft licence: check compatibility before combining with closed code.")
    note_parts.append(f"CI configured: {'yes' if ci else 'no'}.")
    if not ci:
        findings.append(Finding(
            "low", "No CI configuration found",
            "CI: missing",
            "Add CI so tests run on every change; absence of CI is not proof of bad code.",
        ))
    return Trial(name="Licence & Hygiene", verdict=trial_verdict(findings),
                 findings=findings, note=" ".join(note_parts))
