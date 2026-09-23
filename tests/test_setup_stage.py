"""Regression tests for the setup stage.

Repos that declare a `setup` entrypoint must get it executed BEFORE their
selected unit/e2e tiers (once per repo), a failing setup must propagate to
the aggregate verdict and block that repo's tests, and repos without a setup
entrypoint must behave exactly as before (no setup verdict, no side effects).
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import run_all


def trace_cmd(trace_path, marker):
    return [sys.executable, "-c",
            "import sys; open(sys.argv[1], 'a').write(sys.argv[2] + chr(10))",
            str(trace_path), marker]


def fail_after_marker(evidence_path):
    return [sys.executable, "-c",
            "import sys; open(sys.argv[1], 'w').write('ran'); sys.exit(1)",
            str(evidence_path)]


class SetupStageTests(unittest.TestCase):
    def run_setup(self, rows, *args):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory)
            trace = Path(directory) / "touch"
            with mock.patch.object(run_all, "load_manifest", return_value={"repos": rows}), \
                 mock.patch.object(run_all, "LOGS", logs), \
                 mock.patch.object(sys, "argv", ["run_all.py", *args]), \
                 mock.patch.object(run_all, "check_docs", side_effect=lambda r: {
                     "repo": r["name"], "kind": "docs", "ok": True, "secs": 0, "tail": ""}), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 self.assertRaises(SystemExit) as stopped:
                run_all.main()
            report = json.loads(next(logs.glob("run-*.json")).read_text())
            return stopped.exception.code, report

    def add_repo(self, root, name, *, setup=None, unit=None, e2e=None):
        repo = root / name
        repo.mkdir()
        def wrap(cmd):
            return None if cmd is None else {"cmd": cmd}
        return {
            "name": name, "status": "active", "path": str(repo),
            "setup": wrap(setup), "unit": wrap(unit), "e2e": wrap(e2e),
        }

    def test_setup_runs_before_unit_before_e2e_and_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace"
            row = self.add_repo(
                root, "fixture",
                setup=trace_cmd(trace, "setup"),
                unit=trace_cmd(trace, "unit"),
                e2e=trace_cmd(trace, "e2e"))
            code, report = self.run_setup([row], "--all")
            self.assertEqual(code, 0)
            self.assertEqual(trace.read_text().splitlines(), ["setup", "unit", "e2e"])
            self.assertEqual([r["kind"] for r in report["results"]],
                             ["docs", "setup", "unit", "e2e"])

    def test_setup_runs_once_for_selected_unit_tier_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace"
            row = self.add_repo(
                root, "fixture",
                setup=trace_cmd(trace, "setup"),
                unit=trace_cmd(trace, "unit"),
                e2e=trace_cmd(trace, "e2e"))
            code, report = self.run_setup([row])  # default tier: unit
            self.assertEqual(code, 0)
            self.assertEqual(trace.read_text().splitlines(), ["setup", "unit"])

    def test_setup_runs_before_e2e_when_only_e2e_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace"
            row = self.add_repo(
                root, "fixture",
                setup=trace_cmd(trace, "setup"),
                unit=trace_cmd(trace, "unit"),
                e2e=trace_cmd(trace, "e2e"))
            code, report = self.run_setup([row], "--e2e")
            self.assertEqual(code, 0)
            self.assertEqual(trace.read_text().splitlines(), ["setup", "e2e"])
            self.assertNotIn("unit", [r["kind"] for r in report["results"]])

    def test_setup_failure_propagates_and_blocks_repo_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "fixture"
            repo.mkdir()
            row = {
                "name": "fixture", "status": "active", "path": str(repo),
                "setup": {"cmd": [sys.executable, "-c", "import sys; sys.exit(7)"]},
                "unit": {"cmd": [sys.executable, "-c", "open('unit-ran','w').write('x')"]},
                "e2e": {"cmd": [sys.executable, "-c", "open('e2e-ran','w').write('x')"]},
            }
            code, report = self.run_setup([row], "--all")
            self.assertEqual(code, 1)
            setups = [r for r in report["results"] if r["kind"] == "setup"]
            self.assertEqual(len(setups), 1)
            self.assertFalse(setups[0]["ok"])
            for r in report["results"]:
                if r["kind"] in ("unit", "e2e"):
                    self.assertFalse(r["ok"])
                    self.assertIn("setup", r["tail"])
            self.assertFalse((repo / "unit-ran").exists())
            self.assertFalse((repo / "e2e-ran").exists())

    def test_setup_not_run_when_no_selected_tier_runnable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace"
            row = self.add_repo(
                root, "fixture",
                setup=trace_cmd(trace, "setup"),
                e2e=trace_cmd(trace, "e2e"))
            code, report = self.run_setup([row])  # default tier: unit
            self.assertEqual(code, 1)
            self.assertNotIn("setup", [r["kind"] for r in report["results"]])
            self.assertFalse(trace.exists())

    def test_setup_absent_behaves_exactly_as_before(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "trace"
            row = self.add_repo(
                root, "fixture",
                unit=trace_cmd(trace, "unit"),
                e2e=trace_cmd(trace, "e2e"))
            code, report = self.run_setup([row], "--all")
            self.assertEqual(code, 0)
            self.assertNotIn("setup", [r["kind"] for r in report["results"]])
            self.assertEqual(trace.read_text().splitlines(), ["unit", "e2e"])

    def test_setup_absent_failing_unit_still_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "unit-evidence"
            row = self.add_repo(
                root, "fixture",
                unit=fail_after_marker(evidence),
                e2e=None)
            code, report = self.run_setup([row], "--all")
            self.assertEqual(evidence.read_text(), "ran")
            self.assertEqual(code, 1)
            self.assertNotIn("setup", [r["kind"] for r in report["results"]])
            self.assertTrue(any(r["kind"] == "unit" and not r["ok"] for r in report["results"]))


class BeanfitAppManifestTests(unittest.TestCase):
    def manifest(self):
        return json.loads(
            (Path(__file__).resolve().parents[1] / "manifest.json").read_text())

    def test_beanfit_app_declares_lockfile_pinned_setup(self):
        beanfit = next(r for r in self.manifest()["repos"]
                       if r["name"] == "beanfit-app")
        self.assertEqual(beanfit["setup"]["cmd"], ["npm", "ci"])


if __name__ == "__main__":
    unittest.main()