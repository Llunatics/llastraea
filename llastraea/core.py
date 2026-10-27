"""Judge a local project directory, or a PyPI package by name."""

from __future__ import annotations

import json
import os
import re
import urllib.request

from .deps import run_deps_trial
from .licence import run_licence_trial
from .models import Finding, Trial, Verdict, build_verdict, trial_verdict
from .provenance import run_provenance_trial
from .secrets import run_secrets_trial


def judge_directory(root: str) -> Verdict:
    trials = [
        run_secrets_trial(root),
        run_deps_trial(root),
        run_provenance_trial(root),
        run_licence_trial(root),
    ]
    return build_verdict(os.path.abspath(root), trials)


def judge_pypi_package(name: str) -> Verdict:
    """Build a verdict from PyPI metadata only. No source is scanned."""
    url = f"https://pypi.org/pypi/{name}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "llastraea/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.load(response)
    except Exception as exc:  # network or unknown package
        raise ValueError(f"Could not fetch PyPI data for {name!r}: {exc}") from exc
    info = data.get("info", {}) or {}
    requires = info.get("requires_dist") or []
    findings: list[Finding] = []
    if not info.get("license"):
        findings.append(Finding(
            "low", "No licence declared on PyPI",
            "PyPI licence field: empty",
            "Check the project repository for a licence file.",
        ))
    licence_trial = Trial(
        name="Licence & Hygiene",
        verdict=trial_verdict(findings),
        findings=findings,
        note=f"PyPI licence: {info.get('license') or 'unknown'}. "
             f"Summary: {info.get('summary') or 'none'}.",
    )
    dep_findings: list[Finding] = []
    for req in requires:
        if not req:
            continue
        # Name: first word, before extras, markers, or version specs.
        name_match = re.match(r"([A-Za-z0-9_.\-]+)", req.strip())
        dep_name = name_match.group(1) if name_match else req
        # Pinned-ness: strip the environment marker (after ";") and any
        # extras, then look for a version operator in what remains.
        # A marker-only requirement (``requests; python_version > "3.8"``)
        # is unpinned: the ">" belongs to the marker, not to a version.
        base = req.split(";")[0].strip()
        base = re.sub(r"\[[^\]]*\]", "", base)
        versioned = any(op in base for op in
                         ("==", ">=", "<=", "~=", "!=", ">", "<", "(", "="))
        if not versioned:
            dep_findings.append(Finding(
                "medium", f"Unpinned dependency: {dep_name}",
                f"PyPI requires_dist: {dep_name}",
                f"Pin {dep_name} to an exact version.",
            ))
    deps_trial = Trial(
        name="Dependencies",
        verdict=trial_verdict(dep_findings),
        findings=dep_findings,
        note=f"{len(requires)} dependencies declared on PyPI.",
    )
    trials = [
        Trial(name="Secrets", verdict="Dismissed", findings=[],
              note="No source scanned for a package name; pass a local path to run the secrets trial."),
        deps_trial,
        Trial(name="Provenance", verdict="Dismissed", findings=[],
              note="No repository scanned for a package name; pass a local path to run the provenance trial."),
        licence_trial,
    ]
    return build_verdict(f"pypi:{name}", trials)
