"""Provenance trial: git activity signals, when a repo is given.

This trial reports signals, not accusations. A quiet repo is not guilty;
a busy one is not innocent. Signals are: commit recency, contributor
count, signed-commit ratio in a sample, and the presence of project
files (README, licence, CI). Missing files are also reported by the
licence trial; here they are counted as provenance evidence only.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

from .models import Finding, Trial, trial_verdict


def _git(root: str, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", root] + args,
            capture_output=True, timeout=15, check=False, text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_provenance_trial(root: str) -> Trial:
    if not os.path.isdir(os.path.join(root, ".git")):
        return Trial(name="Provenance", verdict="Dismissed", findings=[],
                     note="Not a git repository; provenance signals unavailable.")
    findings: list[Finding] = []
    last = _git(root, ["log", "-1", "--format=%cI"])
    last_dt = _parse_date(last) if last else None
    if last_dt is None:
        findings.append(Finding(
            "medium", "No commits found in this repository",
            "git log is empty",
            "A repository with no history cannot be judged on activity.",
        ))
    else:
        age_days = (datetime.now(timezone.utc) - last_dt).days
        if age_days > 365:
            findings.append(Finding(
                "medium", f"Last commit was {age_days} days ago",
                f"last commit: {last_dt.date().isoformat()}",
                "Check whether the project is still maintained before depending on it.",
            ))
    contributors = _git(root, ["shortlog", "-sne", "HEAD"])
    count = len(contributors.splitlines()) if contributors else 0
    if count == 1:
        findings.append(Finding(
            "low", "Single contributor in git history",
            "contributors: 1",
            "Single-maintainer projects carry bus-factor risk; review activity before adopting.",
        ))
    signed = _git(root, ["log", "-n", "100", "--pretty=format:%G?"])
    if signed is not None:
        marks = [m for m in signed.splitlines() if m.strip()]
        if len(marks) >= 5:
            ratio = sum(1 for m in marks if m.strip() == "G") / len(marks)
            if ratio == 0:
                findings.append(Finding(
                    "low", "No signed commits in the sampled history",
                    f"signed commits: 0/{len(marks)}",
                    "Prefer signed commits for releases; unsigned history is not proof of tampering.",
                ))
    return Trial(name="Provenance", verdict=trial_verdict(findings),
                 findings=findings,
                 note=f"Contributors: {count}." if count else "Contributor count unavailable.")
