"""Dependencies trial: parse manifests, flag unpinned and lookalike names.

No network calls are made by default. With --check-latest the CLI may
optionally query PyPI, but the trial itself stays offline and deterministic:
unpinned dependencies are a supply-chain risk on their own, and a name one
edit away from a popular package is a typosquat signal worth flagging.
"""

from __future__ import annotations

import json
import os
import re
import sys

from .models import Finding, Trial, trial_verdict

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 fallback
    tomllib = None  # type: ignore

# A deliberately small, well-known list. It is a signal, not a blocklist:
# a name close to one of these is flagged for review, never declared
# malicious on spelling alone.
POPULAR = {
    # Python
    "requests", "numpy", "pandas", "django", "flask", "fastapi",
    "pytest", "pydantic", "sqlalchemy", "boto3", "click", "rich",
    "cryptography", "pillow", "beautifulsoup4", "lxml", "celery",
    "redis", "uvicorn", "gunicorn", "tornado", "scipy", "matplotlib",
    "tensorflow", "torch", "transformers", "openai", "httpx", "aiohttp",
    "pytest-asyncio", "setuptools", "wheel", "python-dotenv",
    # JavaScript
    "react", "vue", "angular", "express", "lodash", "axios", "next",
    "typescript", "webpack", "vite", "eslint", "prettier", "jest",
    "chalk", "commander", "moment", "jquery", "three", "socket.io",
}


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, capped early at 3 for speed."""
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def parse_requirement(line: str) -> tuple[str, str] | None:
    """Parse one requirement line into (name, spec) or None."""
    line = line.strip()
    if not line or line.startswith(("#", "-", "git+", "http")):
        return None
    match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(.*)$", line)
    if not match:
        return None
    name = match.group(1)
    spec = match.group(2).strip().strip(";")
    # Strip environment markers and trailing comments.
    spec = spec.split(";")[0].strip()
    return name, spec


def _parse_requirements_file(path: str) -> list[tuple[str, str]]:
    deps: list[tuple[str, str]] = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                parsed = parse_requirement(line.split("#")[0])
                if parsed:
                    deps.append(parsed)
    except OSError:
        pass
    return deps


def _parse_pyproject(path: str) -> list[tuple[str, str]]:
    deps: list[tuple[str, str]] = []
    try:
        if tomllib is not None:
            with open(path, "rb") as fh:
                data = tomllib.load(fh)
            project = data.get("project", {})
            for req in project.get("dependencies", []) or []:
                parsed = parse_requirement(str(req))
                if parsed:
                    deps.append(parsed)
            for group in (project.get("optional-dependencies", {}) or {}).values():
                for req in group or []:
                    parsed = parse_requirement(str(req))
                    if parsed:
                        deps.append(parsed)
            return deps
    except Exception:
        pass
    # Fallback: regex over the dependencies list.
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        for req in re.findall(r'"([A-Za-z0-9_.\-]+[^"]*)"', text):
            if "dependencies" in text:
                parsed = parse_requirement(req)
                if parsed:
                    deps.append(parsed)
    except OSError:
        pass
    return deps


def _parse_package_json(path: str) -> list[tuple[str, str]]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    deps: list[tuple[str, str]] = []
    for section in ("dependencies", "devDependencies"):
        for name, spec in (data.get(section) or {}).items():
            deps.append((str(name), str(spec)))
    return deps


def collect_dependencies(root: str) -> list[tuple[str, str, str]]:
    """Return (name, spec, source-file) for every manifest found."""
    out: list[tuple[str, str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", ".venv", "venv")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if name == "package.json":
                parsed = _parse_package_json(path)
            elif name == "pyproject.toml":
                parsed = _parse_pyproject(path)
            elif name.startswith("requirements") and name.endswith(".txt"):
                parsed = _parse_requirements_file(path)
            else:
                continue
            for dep_name, spec in parsed:
                out.append((dep_name, spec, rel))
    # De-duplicate by name, keeping the first source.
    seen: dict[str, tuple[str, str, str]] = {}
    for dep in out:
        seen.setdefault(dep[0].lower(), dep)
    return list(seen.values())


def _manifest_found(root: str) -> bool:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", ".venv", "venv")]
        for name in filenames:
            if name == "package.json" or name == "pyproject.toml" or (
                    name.startswith("requirements") and name.endswith(".txt")):
                return True
    return False


def run_deps_trial(root: str) -> Trial:
    deps = collect_dependencies(root)
    if not deps:
        if _manifest_found(root):
            return Trial(name="Dependencies", verdict="Trusted", findings=[],
                         note="Manifest found with no direct dependencies.")
        return Trial(name="Dependencies", verdict="Dismissed",
                     findings=[],
                     note="No requirements.txt, pyproject.toml, or package.json found.")
    findings: list[Finding] = []
    for name, spec, source in deps:
        lowered = name.lower()
        if not spec or spec in ("*", "latest"):
            findings.append(Finding(
                "medium", f"Unpinned dependency: {name}",
                f"{source}: {name}",
                f"Pin {name} to an exact version in {source}.",
            ))
        if lowered not in POPULAR:
            for popular in POPULAR:
                if edit_distance(lowered, popular) in (1, 2):
                    findings.append(Finding(
                        "high",
                        f"Possible typosquat: {name} looks like {popular}",
                        f"{source}: {name}",
                        f"Verify {name} is the intended package before using it.",
                    ))
                    break
    note = f"{len(deps)} direct dependencies parsed. Outdated checks are not run offline; use --check-latest for PyPI version checks."
    return Trial(name="Dependencies", verdict=trial_verdict(findings),
                 findings=findings, note=note)
