import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llastraea.licence import detect_licence, run_licence_trial
from llastraea.models import Finding, Trial, build_verdict, trial_verdict


class TestVerdict(unittest.TestCase):
    def test_trial_verdict_mapping(self):
        self.assertEqual(trial_verdict([]), "Trusted")
        self.assertEqual(trial_verdict([Finding("medium", "m")]), "Caution")
        self.assertEqual(trial_verdict([Finding("high", "m")]), "Guilty")
        self.assertEqual(trial_verdict([], skipped=True), "Dismissed")

    def test_score_and_overall(self):
        trials = [
            Trial("Secrets", "Guilty", [Finding("critical", "leak")]),
            Trial("Dependencies", "Trusted", []),
        ]
        verdict = build_verdict("demo", trials)
        self.assertEqual(verdict.score, 75)
        self.assertEqual(verdict.overall, "Guilty")
        self.assertEqual(verdict.to_dict()["score"], 75)

    def test_licence_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "LICENSE"), "w") as fh:
                fh.write("MIT License\n\nPermission is hereby granted, free of charge\n")
            self.assertEqual(detect_licence(tmp), "MIT")
            trial = run_licence_trial(tmp)
            self.assertNotIn("No licence", " ".join(f.message for f in trial.findings))

    def test_cli_json_no_secret_leak(self):
        secret = "AKIA" + "Z7Q9W2X4K5M8N1P3"
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "config.py"), "w") as fh:
                fh.write(f"KEY = '{secret}'\n")
            with open(os.path.join(tmp, "README.md"), "w") as fh:
                fh.write("# Demo\n")
            with open(os.path.join(tmp, "LICENSE"), "w") as fh:
                fh.write("MIT License\n\nPermission is hereby granted, free of charge\n")
            proc = subprocess.run(
                [sys.executable, "-m", "llastraea", tmp, "--format", "json", "--no-color"],
                capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), ".."),
            )
            self.assertNotIn(secret, proc.stdout)
            data = json.loads(proc.stdout)
            self.assertIn("score", data)
            self.assertEqual(data["overall_verdict"], "Guilty")


if __name__ == "__main__":
    unittest.main()
