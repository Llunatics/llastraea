# llastraea

A command-line trust court for open-source projects. Give it a local
project directory or a PyPI package name and it returns a verdict, not a
raw list of findings: each charge is tried on its own evidence, and the
final score is explained by the trials behind it.

llastraea is written in Python with no third-party dependencies. It works
offline for local directories. It does not upload code anywhere.

## Install

```bash
git clone https://github.com/Llunatics/llastraea
cd llastraea
python -m venv .venv
.venv/bin/pip install .
```

Or run it without installing, from the repository root:

```bash
python -m llastraea <path>
```

Requires Python 3.10 or later.

## Usage

```bash
# Judge a local project
llastraea /path/to/project

# Judge a PyPI package (metadata only, no source scan)
llastraea requests

# Machine-readable output
llastraea /path/to/project --format json --output verdict.json

# Markdown report
llastraea /path/to/project --format markdown --output verdict.md
```

Exit code is `0` unless the overall verdict is Guilty, in which case it
is `1`. This makes the tool usable in scripts and CI: a Guilty verdict
fails the step.

### Sample output

```
+--------------------------------------------------------------+
| llastraea -- trust court for /tmp/demo-project               |
|--------------------------------------------------------------|
| VERDICT: TRUSTED                                             |
| JUSTICE SCALE: [####################] 100/100                |
+--------------------------------------------------------------+

[Secrets]  Trusted
  Files scanned; binary files and files over 1 MiB skipped.
  No findings.

[Dependencies]  Trusted
  1 direct dependencies parsed. Outdated checks are not run offline.
  No findings.

[Provenance]  Dismissed
  Not a git repository; provenance signals unavailable.
  No findings.

[Licence & Hygiene]  Trusted
  Licence: MIT. CI configured: yes.
  No findings.
```

When output is piped, colours are disabled automatically. Use
`--no-color` to force plain output on a terminal.

## The four trials

| Trial | What it checks | Skipped when |
| --- | --- | --- |
| Secrets | Files and git history for leaked tokens and keys, with file and line evidence. Values are masked in all output. | Never, for a local directory |
| Dependencies | `requirements.txt`, `pyproject.toml`, and `package.json`. Flags unpinned dependencies and names close to popular packages. | No manifest is found |
| Provenance | Git history: last commit age, contributor count, and signed-commit ratio in a sample of up to 100 commits. | Not a git repository |
| Licence & Hygiene | Licence detection from the licence file text, plus README and CI presence. | Never, for a local directory |

A trial with no data is marked **Dismissed**. That means "not judged",
not "passed". A Dismissed trial does not raise the score.

## Verdicts and scoring

Per-trial verdicts:

| Verdict | Meaning |
| --- | --- |
| Trusted | No findings, or only low-severity findings |
| Caution | At least one medium-severity finding |
| Guilty | At least one high- or critical-severity finding |
| Dismissed | No data to judge |

The overall score starts at 100 and subtracts points per finding:
critical 25, high 15, medium 8, low 3. The score is floored at 0.

The overall verdict is **Guilty** if any finding is critical or the
score falls below 50, **Caution** if any trial is Guilty or the score
falls below 80, and **Trusted** otherwise.

Every finding carries a remediation step. The text and Markdown reports
end with a deduplicated remediation checklist.

## Output formats

| Format | Use |
| --- | --- |
| `text` (default) | Human-readable verdict cards and the justice-scale gauge |
| `json` | Structured data: score, overall verdict, trials, findings, remediation |
| `markdown` | A report with a trial table and a remediation checklist |

## Limitations

- Secret detection is pattern-based. It catches common credential
  formats and obvious assignments, and it will miss secrets in formats
  it does not know. A Trusted secrets verdict is not proof that no
  secret is present.
- Typosquat detection compares names against a small list of popular
  packages. A flagged name is a signal to check, not proof of malice.
- Outdated-package checks are not run by default. The dependencies
  trial reports what is pinned and what is not; it does not query a
  registry unless a future `--check-latest` implementation is used.
- Provenance signals describe activity, not quality. A quiet project
  can be sound, and a busy one can be unsafe.
- For a PyPI package name, only metadata is available. The secrets
  and provenance trials are Dismissed in that mode; pass a local
  checkout for a full judgement.

## Security notes

- Secret values are never printed in full, in any output format.
  Evidence shows a pattern name, a file and line, and a masked value
  (first two and last two characters only).
- Binary files and files over 1 MiB are skipped during the secrets
  scan, as are `.git`, `__pycache__`, `node_modules`, and virtual
  environments. Git history scanning is capped at 5 MiB of diff output.
- Known vendor documentation examples, such as
  `AKIAIOSFODNN7EXAMPLE`, are not flagged.

## License

MIT. See [LICENSE](LICENSE).
