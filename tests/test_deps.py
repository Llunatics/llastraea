import os
import tempfile
import unittest

from llastraea.deps import collect_dependencies, edit_distance, parse_requirement, run_deps_trial


class TestDeps(unittest.TestCase):
    def test_parse_requirement(self):
        self.assertEqual(parse_requirement("requests==2.31.0"), ("requests", "==2.31.0"))
        self.assertEqual(parse_requirement("flask"), ("flask", ""))
        self.assertIsNone(parse_requirement("# comment"))
        self.assertIsNone(parse_requirement(""))

    def test_edit_distance(self):
        self.assertEqual(edit_distance("reqeusts", "requests"), 2)
        self.assertEqual(edit_distance("requests", "requests"), 0)
        self.assertGreaterEqual(edit_distance("django", "flask"), 3)

    def test_typosquat_and_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "requirements.txt"), "w") as fh:
                fh.write("reqeusts==2.31.0\nflask\n")
            trial = run_deps_trial(tmp)
            messages = " ".join(f.message for f in trial.findings)
            self.assertIn("typosquat", messages)
            self.assertIn("Unpinned", messages)
            self.assertEqual(trial.verdict, "Guilty")

    def test_parse_requirement_extras(self):
        self.assertEqual(parse_requirement("requests[security]"), ("requests", ""))
        self.assertEqual(parse_requirement("requests[security]>=2.0"), ("requests", ">=2.0"))

    def test_extras_without_version_is_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "requirements.txt"), "w") as fh:
                fh.write("requests[security]\nflask[async]>=2.0\n")
            trial = run_deps_trial(tmp)
            messages = " ".join(f.message for f in trial.findings)
            self.assertIn("Unpinned dependency: requests", messages)
            self.assertNotIn("Unpinned dependency: flask", messages)

    def test_malformed_pyproject_no_hallucinated_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "pyproject.toml"), "w") as fh:
                fh.write('[project\nthis is not valid toml\nname = "requests"\n'
                         '# dependencies mentioned here\n')
            deps = collect_dependencies(tmp)
            self.assertFalse(any(name == "requests" for name, _, _ in deps))

    def test_collect_pyproject(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "pyproject.toml"), "w") as fh:
                fh.write('[project]\nname = "demo"\ndependencies = ["requests>=2.0"]\n')
            deps = collect_dependencies(tmp)
            self.assertTrue(any(name == "requests" for name, _, _ in deps))

    def test_no_manifest_dismissed(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial = run_deps_trial(tmp)
            self.assertEqual(trial.verdict, "Dismissed")


if __name__ == "__main__":
    unittest.main()
