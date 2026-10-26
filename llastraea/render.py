"""Terminal rendering: modern panels and a justice-scale gauge.

Colours are used only when output is a TTY and colours are not disabled.
When piped, output is plain ASCII so it can be parsed, grepped, and saved
without escape codes. The gauge and verdict cards are unicode in TTY mode
and ASCII in piped mode, so the layout stays readable in both cases.
"""

from __future__ import annotations

from .models import Verdict

COLOURS = {
    "Trusted": "\033[32m",
    "Caution": "\033[33m",
    "Guilty": "\033[31m",
    "Dismissed": "\033[90m",
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[90m",
}

WIDTH = 62


def _colour(name: str, text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{COLOURS.get(name, '')}{text}{COLOURS['reset']}"


def gauge(score: int, tty: bool) -> str:
    filled = round(score / 100 * 20)
    if tty:
        bar = "█" * filled + "░" * (20 - filled)
    else:
        bar = "#" * filled + "-" * (20 - filled)
    return f"[{bar}] {score}/100"


def shorten_middle(text: str, max_len: int = 58) -> str:
    """Shorten a long path in the middle, keeping start and end visible."""
    if len(text) <= max_len:
        return text
    keep = (max_len - 3) // 2
    return f"{text[:keep]}...{text[-keep:]}"


def render_text(verdict: Verdict, use_colour: bool) -> str:
    tty = use_colour
    side = "║" if tty else "|"
    top = f"╔{'═' * WIDTH}╗" if tty else "+" + "-" * WIDTH + "+"
    sep = f"╠{'─' * WIDTH}╣" if tty else f"{side}{'-' * WIDTH}{side}"
    bottom = f"╚{'═' * WIDTH}╝" if tty else "+" + "-" * WIDTH + "+"

    def panel(plain: str, display: str | None = None) -> str:
        shown = display if display is not None else plain
        pad = max(0, WIDTH - len(plain))
        return f"{side}{shown}{' ' * pad}{side}"

    lines: list[str] = []
    lines.append(top)
    title_plain = f" llastraea -- trust court for {shorten_middle(verdict.target, 30)}"
    lines.append(panel(title_plain))
    lines.append(sep)
    overall_plain = f" VERDICT: {verdict.overall.upper()}"
    overall_display = f" VERDICT: {_colour(verdict.overall, verdict.overall.upper(), use_colour)}"
    lines.append(panel(overall_plain, overall_display))
    scale_plain = f" JUSTICE SCALE: {gauge(verdict.score, tty)}"
    lines.append(panel(scale_plain))
    lines.append(bottom)
    lines.append("")
    for trial in verdict.trials:
        verdict_word = _colour(trial.verdict, trial.verdict, use_colour)
        lines.append(f"[{trial.name}]  {verdict_word}")
        if trial.note:
            lines.append(f"  {trial.note}")
        if not trial.findings:
            lines.append("  No findings.")
        for finding in trial.findings:
            sev_name = "Guilty" if finding.severity in ("critical", "high") else "Caution"
            sev = _colour(sev_name, finding.severity.upper(), use_colour)
            lines.append(f"  - [{sev}] {finding.message}")
            if finding.evidence:
                lines.append(f"      evidence: {finding.evidence}")
            if finding.remediation:
                lines.append(f"      fix: {finding.remediation}")
        lines.append("")
    if verdict.remediation:
        lines.append("Remediation checklist:")
        for i, item in enumerate(verdict.remediation, 1):
            lines.append(f"  {i}. {item}")
        lines.append("")
    return "\n".join(lines)


def render_markdown(verdict: Verdict) -> str:
    lines: list[str] = []
    lines.append(f"# llastraea verdict: {verdict.target}")
    lines.append("")
    lines.append(f"- **Score:** {verdict.score}/100")
    lines.append(f"- **Overall verdict:** {verdict.overall}")
    lines.append("")
    lines.append("| Trial | Verdict | Findings |")
    lines.append("| --- | --- | --- |")
    for trial in verdict.trials:
        lines.append(f"| {trial.name} | {trial.verdict} | {len(trial.findings)} |")
    lines.append("")
    for trial in verdict.trials:
        if not trial.findings:
            continue
        lines.append(f"## {trial.name} ({trial.verdict})")
        lines.append("")
        for finding in trial.findings:
            lines.append(f"- **{finding.severity}** — {finding.message}")
            if finding.evidence:
                lines.append(f"  - Evidence: `{finding.evidence}`")
            if finding.remediation:
                lines.append(f"  - Fix: {finding.remediation}")
        lines.append("")
    if verdict.remediation:
        lines.append("## Remediation checklist")
        lines.append("")
        for item in verdict.remediation:
            lines.append(f"- [ ] {item}")
        lines.append("")
    return "\n".join(lines)


def is_tty(stream) -> bool:
    try:
        return stream.isatty()
    except Exception:
        return False
