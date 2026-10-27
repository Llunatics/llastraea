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

## Round 3 — Tuesday audit (2026-10-27)

Independent audit of the Monday build; 8 findings, all fixed, each
with a regression test (suite 17 → 25):

1. **Extras without a version were not flagged unpinned.**
   `requests[security]` parsed to spec `[security]`, which is
   non-empty, so the unpinned check passed it. Fixed: extras are
   stripped in `parse_requirement`, so bare-name-with-extras counts
   as unpinned like a bare name.
2. **Placeholder check had substring false negatives.** A credential
   merely containing a placeholder word was dismissed:
   `MySecretKey99` contains `secret`, `contest-token-…` contains
   `test` and `token`. Fixed: only the first word counts
   (`example-key-…`, `changeme123`, `test-key-…` still placeholders).
3. **PyPI marker-only dependencies were not flagged unpinned.**
   `requests; python_version > "3.8"` passed because the `>` in the
   marker looked like a version operator, and the dependency name
   itself came out as `requests;`. Fixed: markers and extras are
   stripped before the version-operator check, and the name is
   parsed with a regex.
4. **Terminal injection via PyPI summary.** A summary containing ESC
   bytes and newlines was printed verbatim into piped text output.
   Fixed: text and Markdown renderers strip control characters from
   targets, notes, messages, evidence, and remediation. JSON output
   was already safe (`json.dumps` escapes control characters).
5. **Terminal injection via crafted filenames.** A file named with
   ESC bytes holding a real-format secret printed raw ESC bytes in
   piped output. Fixed by the same renderer filter (finding 4).
6. **Unwritable `--output` produced a traceback.** Fixed: OSError
   on write is now a clean `error:` message with exit code 2.
7. **Malformed `pyproject.toml` hallucinated dependencies.** The
   regex fallback parsed any quoted string in the file when the word
   `dependencies` appeared anywhere, including comments, inventing a
   `requests` dependency. Fixed: with a real TOML parser available,
   malformed TOML yields no dependencies; the regex fallback (kept
   for Python 3.10) only reads strings inside an explicit
   `dependencies = [...]` list.
8. **Licence detection walked into `.venv`.** A LICENSE inside
   `.venv` was reported as the project's licence. Fixed: the finder
   now skips `.venv`, `venv`, `dist`, `build`, `.tox`, and `.eggs`
   like the other trials, and no longer stops after the first
   subdirectory. The deps walker skips the same directories.

Also fixed along the way: the first version of the new regression
test itself contained literal credential-assignment lines, which
tripped the tool's own self-scan (67/Caution); the values are now
built at runtime, and self-scan is back to 94/Trusted.

Cases that passed unchanged: target-is-a-file (clean rc 2),
non-UTF-8 git author names (no provenance crash), binary and
oversized files, and the full Round 2 adversarial set (re-run via
the suite). One doc correction: the deps note and README sample
no longer promise PyPI version checks from `--check-latest`, which
is a documented no-op.

Re-audit: 25/25 tests green in the working tree and in a fresh
copy; self-scan 94/Trusted (only the known single-contributor and
no-CI low findings).

## Verdict

**Pass.** 25 unit tests green. Adversarial cases above pass. No secret
value leaks into text, JSON, or Markdown output in any tested case.
Known limits are stated in the README: pattern-based secret detection
is not proof of absence, typosquat flags are signals, and provenance
signals describe activity, not quality.
