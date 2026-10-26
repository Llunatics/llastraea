import os
import tempfile
import unittest

from llastraea.redact import is_placeholder, redact_value
from llastraea.secrets import run_secrets_trial


class TestRedact(unittest.TestCase):
    def test_masks_middle(self):
        masked = redact_value("ghp_" + "abcdefghijklmnopqrst")
        self.assertNotIn("abcdefghijklmnopqrst", masked)
        self.assertTrue(masked.startswith("gh"))
        self.assertTrue(masked.endswith("st"))

    def test_short_fully_masked(self):
        self.assertEqual(redact_value("abc"), "****")

    def test_placeholders(self):
        self.assertTrue(is_placeholder("example-key-123"))
        self.assertTrue(is_placeholder("changeme123"))
        self.assertFalse(is_placeholder("aB3$xY9qW2zR7tU"))


class TestSecretsTrial(unittest.TestCase):
    def _project(self, files):
        tmp = tempfile.TemporaryDirectory()
        for name, content in files.items():
            path = os.path.join(tmp.name, name)
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(name) else None
            mode = "wb" if isinstance(content, bytes) else "w"
            with open(path, mode) as fh:
                fh.write(content)
        return tmp

    def test_detects_aws_key_and_redacts(self):
        secret = "AKIA" + "Z7Q9W2X4K5M8N1P3"
        tmp = self._project({"config.py": f"KEY = '{secret}'\n"})
        try:
            trial = run_secrets_trial(tmp.name, include_history=False)
            self.assertTrue(trial.findings)
            for finding in trial.findings:
                self.assertNotIn(secret, finding.evidence)
            self.assertEqual(trial.verdict, "Guilty")
        finally:
            tmp.cleanup()

    def test_placeholder_not_flagged(self):
        tmp = self._project({"config.py": "password = 'changeme123'\napi_key = 'example-key-123'\n"})
        try:
            trial = run_secrets_trial(tmp.name, include_history=False)
            self.assertEqual(trial.findings, [])
            self.assertEqual(trial.verdict, "Trusted")
        finally:
            tmp.cleanup()

    def test_binary_file_skipped(self):
        tmp = self._project({"data.bin": b"\x00\x01" + b"AKIA" + b"Z7Q9W2X4K5M8N1P3" + b"\x00"})
        try:
            trial = run_secrets_trial(tmp.name, include_history=False)
            self.assertEqual(trial.findings, [])
        finally:
            tmp.cleanup()

    def test_huge_file_skipped(self):
        tmp = self._project({"big.txt": "x" * (1_048_577) + " " + "AKIA" + "Z7Q9W2X4K5M8N1P3"})
        try:
            trial = run_secrets_trial(tmp.name, include_history=False)
            self.assertEqual(trial.findings, [])
        finally:
            tmp.cleanup()

    def test_private_key_flagged_without_value(self):
        tmp = self._project({"key.pem": "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIBOgIBAA\n"})
        try:
            trial = run_secrets_trial(tmp.name, include_history=False)
            self.assertTrue(any(f.severity == "critical" for f in trial.findings))
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
