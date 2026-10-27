import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import llastraea.core as core
from llastraea.licence import detect_licence, run_licence_trial
from llastraea.models import Finding, Trial, build_verdict, trial_verdict
from llastraea.render import render_markdown, render_text


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

    def test_pypi_marker_only_dep_is_unpinned(self):
        fake = {"info": {"license": "MIT", "summary": "Demo",
                         "requires_dist": ['requests; python_version > "3.8"',
                                            "numpy==1.26.0"]}}
        resp = io.BytesIO(json.dumps(fake).encode())
        resp.__enter__ = lambda self: self
        resp.__exit__ = lambda *a: False
        with mock.patch("urllib.request.urlopen", return_value=resp):
            verdict = core.judge_pypi_package("fakepkg")
        deps = [t for t in verdict.trials if t.name == "Dependencies"][0]
        messages = " ".join(f.message for f in deps.findings)
        self.assertIn("Unpinned dependency: requests", messages)
        self.assertNotIn("requests;", messages)
        self.assertNotIn("Unpinned dependency: numpy", messages)

    def test_render_strips_control_characters(self):
        verdict = build_verdict("demo", [
            Trial("Secrets", "Trusted", [],
                  note="Note with \x1b[31mcolour and\nforged line"),
        ])
        text = render_text(verdict, False)
        self.assertNotIn("\x1b", text)
        # Newline stripped: the forged second line cannot start a line.
        self.assertIn("andforged line", text)
        markdown = render_markdown(verdict)
        self.assertNotIn("\x1b", markdown)

    def test_licence_ignores_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".venv"))
            with open(os.path.join(tmp, ".venv", "LICENSE"), "w") as fh:
                fh.write("MIT License\n\nPermission is hereby granted, free of charge\n")
            self.assertIsNone(detect_licence(tmp))

    def test_cli_bad_output_is_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, "-m", "llastraea", tmp, "--format", "json",
                 "--output", "/nonexistent-dir-xyz/out.json"],
                capture_output=True, text=True,
                cwd=os.path.join(os.path.dirname(__file__), ".."),
            )
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)

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
