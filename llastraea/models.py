"""Shared data types for trials, findings, and verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field


SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 8, "low": 3}


@dataclass
class Finding:
    severity: str  # critical | high | medium | low
    message: str
    evidence: str = ""
    remediation: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "remediation": self.remediation,
        }


@dataclass
class Trial:
    name: str
    verdict: str  # Trusted | Caution | Guilty | Dismissed
    findings: list[Finding] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "verdict": self.verdict,
            "note": self.note,
            "findings": [f.to_dict() for f in self.findings],
        }


def trial_verdict(findings: list[Finding], skipped: bool = False) -> str:
    """Verdict for one trial from its findings."""
    if skipped:
        return "Dismissed"
    severities = {f.severity for f in findings}
    if "critical" in severities or "high" in severities:
        return "Guilty"
    if "medium" in severities:
        return "Caution"
    return "Trusted"


@dataclass
class Verdict:
    score: int
    overall: str  # Trusted | Caution | Guilty
    trials: list[Trial] = field(default_factory=list)
    target: str = ""
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "score": self.score,
            "overall_verdict": self.overall,
            "trials": [t.to_dict() for t in self.trials],
            "remediation": self.remediation,
        }


def build_verdict(target: str, trials: list[Trial]) -> Verdict:
    """Score 100 minus finding weights, floored at 0, and overall verdict."""
    deduction = 0
    for trial in trials:
        for finding in trial.findings:
            deduction += SEVERITY_WEIGHTS.get(finding.severity, 3)
    score = max(0, 100 - deduction)
    has_critical = any(
        f.severity == "critical" for t in trials for f in t.findings
    )
    has_guilty = any(t.verdict == "Guilty" for t in trials)
    if has_critical or score < 50:
        overall = "Guilty"
    elif has_guilty or score < 80:
        overall = "Caution"
    else:
        overall = "Trusted"
    remediation: list[str] = []
    for trial in trials:
        for finding in trial.findings:
            if finding.remediation and finding.remediation not in remediation:
                remediation.append(finding.remediation)
    return Verdict(
        score=score, overall=overall, trials=trials,
        target=target, remediation=remediation,
    )
