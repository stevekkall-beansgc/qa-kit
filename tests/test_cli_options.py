"""Regression tests for --manifest and --logs-dir CLI options.

Malformed or missing manifests and unwritable log paths must fail with a
clear, nonzero exit (no traceback, no false green).
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


def make_manifest(path, repo, *, cmd=None):
    unit = None if cmd is None else {"cmd": cmd}
    path.write_text(json.dumps({"repos": [{
        "name": "synthetic", "status": "active", "path": str(repo),
        "unit": unit}]}))


class CliOptionTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["run_all.py", *args]), \
             mock.patch.object(run_all, "check_docs", side_effect=lambda r: {
                 "repo": r["name"], "kind": "docs", "ok": True, "secs": 0, "tail": ""}), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
             self.assertRaises(SystemExit) as caught:
            run_all.main()
        return caught.exception.code, out.getvalue(), err.getvalue()

    def test_manifest_and_logs_dir_are_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            manifest = root / "manifest.json"
            logs = root / "reports"
            make_manifest(manifest, repo, cmd=[sys.executable, "-c", "pass"])
            code, _, _ = self.run_main(
                "--manifest", str(manifest), "--logs-dir", str(logs))
            self.assertEqual(code, 0)
            reports = list(logs.glob("run-*.json"))
            self.assertEqual(len(reports), 1)
            self.assertTrue(all(r["ok"] for r in json.loads(reports[0].read_text())["results"]))

    def test_failing_unit_still_writes_report_to_logs_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            manifest = root / "manifest.json"
            logs = root / "reports"
            make_manifest(manifest, repo, cmd=[sys.executable, "-c", "raise SystemExit(1)"])
            code, _, _ = self.run_main(
                "--manifest", str(manifest), "--logs-dir", str(logs))
            self.assertEqual(code, 1)
            reports = list(logs.glob("run-*.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertTrue(any(not r["ok"] for r in report["results"]))

    def test_default_manifest_still_used_without_flag(self):
        rows = [{"name": "x", "status": "active", "path": "/tmp",
                 "unit": {"cmd": [sys.executable, "-c", "pass"]}}]
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory)
            with mock.patch.object(run_all, "load_manifest", return_value={"repos": rows}), \
                 mock.patch.object(run_all, "LOGS", logs):
                code, _, _ = self.run_main()
            self.assertEqual(code, 0)
            self.assertEqual(len(list(logs.glob("run-*.json"))), 1)

    def test_missing_manifest_fails_cleanly(self):
        code, _, err = self.run_main("--manifest", "/nonexistent/nope.json")
        self.assertEqual(code, 2)
        self.assertIn("manifest not found", err)
        self.assertNotIn("Traceback", err)

    def test_malformed_manifest_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text("{not json")
            code, _, err = self.run_main("--manifest", str(bad))
        self.assertEqual(code, 2)
        self.assertIn("malformed manifest", err)
        self.assertNotIn("Traceback", err)

    def test_directory_manifest_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            code, _, err = self.run_main("--manifest", directory)
        self.assertEqual(code, 2)
        self.assertIn("cannot read manifest", err)
        self.assertNotIn("Traceback", err)

    def test_manifest_without_repos_list_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "no-repos.json"
            bad.write_text("{}")
            code, _, err = self.run_main("--manifest", str(bad))
        self.assertEqual(code, 2)
        self.assertIn("missing 'repos' list", err)
        self.assertNotIn("Traceback", err)

    def test_unwritable_logs_dir_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            blocker = root / "blocker"
            blocker.write_text("not a directory")
            manifest = root / "manifest.json"
            make_manifest(manifest, repo, cmd=[sys.executable, "-c", "pass"])
            code, _, err = self.run_main(
                "--manifest", str(manifest), "--logs-dir", str(blocker))
        self.assertEqual(code, 2)
        self.assertIn("cannot write report", err)
        self.assertNotIn("Traceback", err)

    def test_missing_readme_fails_docs_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "## Test commands\npython3 -m unittest discover -s tests\n")
            verdict = run_all.check_docs({
                "name": "synthetic", "path": str(root),
                "unit": {"cmd": ["python3", "-m", "unittest", "discover", "-s", "tests"]},
            })
        self.assertFalse(verdict["ok"])
        self.assertIn("missing README.md", verdict["tail"])


if __name__ == "__main__":
    unittest.main()
