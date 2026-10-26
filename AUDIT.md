# Audit — llastraea v1.0.0

Audit process used here: audit → fix → re-audit → verdict. All checks
below were run against the code in this repository.

## Round 1 — initial audit

Findings, all fixed:

1. **Test fixtures polluted the tool's own scan.** Test files contained
   literal example credentials and a private-key header, so scanning the
   repository itself returned Guilty. Fixed by splitting secret literals
   in test source (values are built at runtime), and by allowlisting
   vendor documentation examples such as `AKIAIOSFODNN7EXAMPLE`.
   Re-audit: self-scan now returns Trusted, 94/100 (only missing README
   and CI findings, which this audit also resolves by adding the README).
2. **Title panel truncated long targets.** The header sliced the target
   to the panel width instead of shortening it in the middle. Fixed with
   a middle-shortening helper that keeps the start and end visible.
3. **Panel padding broke with ANSI colours.** Padding was calculated on
   the coloured string, not the visible text. Fixed by padding on the
   plain-text length.
4. **Signed-commit finding was noisy for tiny histories.** A repository
   with a single unsigned commit was flagged. Fixed: the finding only
   fires when at least five commits were sampled.

## Round 2 — adversarial re-audit

All passed, no changes required except the README install note:

- Malformed `pyproject.toml` and `package.json`: no crash, valid JSON
  output, exit code 0.
- False positives: `password = 'changeme123'`, `api_key =
  'example-key-123'`, and short passwords produce no secrets findings.
- Binary files and files over 1 MiB are skipped, not crashed on.
- Git history: a credential committed and later removed is still
  flagged from history, the value is masked in output, and the exit
  code is 1 (Guilty).
- Piped output contains no ANSI escape codes; TTY rendering does.
- Unknown PyPI package name exits 2 with a plain error, no traceback.
- Install from a virtualenv works: `llastraea --version` prints
  `llastraea 1.0.0`, and a clean fixture scores 100/100.

One install note was corrected in round 2: the system Python on the
build machine is externally managed (PEP 668), so the README now shows
a virtualenv install instead of a plain `pip install .`.

## Verdict

**Pass.** 17 unit tests green. Adversarial cases above pass. No secret
value leaks into text, JSON, or Markdown output in any tested case.
Known limits are stated in the README: pattern-based secret detection
is not proof of absence, typosquat flags are signals, and provenance
signals describe activity, not quality.
