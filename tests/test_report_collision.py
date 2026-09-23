"""Regression: same-second run-*.json overwrite loses prior failure."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import run_all


def make_manifest(path, repo, *, cmd=None):
    unit = None if cmd is None else {"cmd": cmd}
    path.write_text(json.dumps({"repos": [{
        "name": "synthetic", "status": "active", "path": str(repo),
        "unit": unit}]}))


class ReportCollisionTests(unittest.TestCase):
    def test_same_second_runs_do_not_overwrite_prior_failure(self):
        """Two runs in the same second must not clobber the earlier report."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            manifest_fail = root / "manifest-fail.json"
            manifest_pass = root / "manifest-pass.json"
            logs = root / "reports"
            make_manifest(manifest_fail, repo, cmd=[sys.executable, "-c", "raise SystemExit(1)"])
            make_manifest(manifest_pass, repo, cmd=[sys.executable, "-c", "pass"])

            fixed = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)

            class FixedDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return fixed

            # First run: failing — should create run-20260923T120000Z.json with failure
            with mock.patch.object(run_all, "datetime", FixedDateTime), \
                 mock.patch.object(run_all, "check_docs", side_effect=lambda r: {
                     "repo": r["name"], "kind": "docs", "ok": True, "secs": 0, "tail": ""}), \
                 mock.patch.object(sys, "argv", ["run_all.py", "--manifest", str(manifest_fail), "--logs-dir", str(logs)]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as e1:
                    run_all.main()
                self.assertEqual(e1.exception.code, 1)

            reports_after_first = sorted(logs.glob("run-*.json"))
            self.assertEqual(len(reports_after_first), 1, "first run should create exactly one report")
            first_report = json.loads(reports_after_first[0].read_text())
            self.assertTrue(any(not r["ok"] for r in first_report["results"]),
                            "first report must record failure")
            first_path = reports_after_first[0]
            first_content = first_path.read_text()

            # Second run: passing, same second — must NOT overwrite the failure report
            with mock.patch.object(run_all, "datetime", FixedDateTime), \
                 mock.patch.object(run_all, "check_docs", side_effect=lambda r: {
                     "repo": r["name"], "kind": "docs", "ok": True, "secs": 0, "tail": ""}), \
                 mock.patch.object(sys, "argv", ["run_all.py", "--manifest", str(manifest_pass), "--logs-dir", str(logs)]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as e2:
                    run_all.main()
                self.assertEqual(e2.exception.code, 0)

            reports_after_second = sorted(logs.glob("run-*.json"))
            # Must preserve prior failure: at least 2 files, original unchanged
            self.assertEqual(len(reports_after_second), 2,
                             f"second run same second must not overwrite; got {reports_after_second}")
            # Original file must still contain failure, unchanged
            self.assertTrue(first_path.exists(), "original report file must still exist")
            self.assertEqual(first_path.read_text(), first_content,
                             "original failure report must not be overwritten")
            self.assertTrue(any(not r["ok"] for r in json.loads(first_content)["results"]))

            # The new report should be distinct and record success
            new_paths = [p for p in reports_after_second if p != first_path]
            self.assertEqual(len(new_paths), 1)
            second_report = json.loads(new_paths[0].read_text())
            self.assertTrue(all(r["ok"] for r in second_report["results"]),
                            "second report should record success")
            # Ensure filenames are collision-safe (suffix or unique)
            self.assertNotEqual(first_path.name, new_paths[0].name)
            self.assertIn("20260923T120000Z", new_paths[0].name)


if __name__ == "__main__":
    unittest.main()
