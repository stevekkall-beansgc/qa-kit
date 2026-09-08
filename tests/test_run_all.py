"""Selection must execute tests before QA can report success."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import run_all


class SelectionTests(unittest.TestCase):
    def run_selection(self, rows, *args):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory)
            with mock.patch.object(run_all, "load_manifest", return_value={"repos": rows}), \
                 mock.patch.object(run_all, "LOGS", logs), \
                 mock.patch.object(sys, "argv", ["run_all.py", *args]), \
                 mock.patch.object(run_all, "check_docs", side_effect=lambda r: {
                     "repo": r["name"], "kind": "docs", "ok": True, "secs": 0, "tail": ""}), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                run_all.main()
            report = json.loads(next(logs.glob("run-*.json")).read_text())
            return stopped.exception.code, report

    def test_unknown_repo_fails(self):
        code, report = self.run_selection([], "--only", "typo")
        self.assertEqual(code, 1)
        self.assertTrue(any(not r["ok"] for r in report["results"]))

    def test_planned_only_fails_even_when_included(self):
        self.assertEqual(self.run_selection([{"name": "later", "status": "planned"}], "--include-planned")[0], 1)

    def test_docs_alone_cannot_pass_missing_selected_tier(self):
        row = {"name": "fixture", "status": "active", "path": "/tmp", "unit": {"cmd": [sys.executable, "-c", "pass"]}}
        self.assertEqual(self.run_selection([row], "--e2e")[0], 1)
        self.assertEqual(self.run_selection([row], "--all")[0], 0)

    def test_missing_unit_cannot_hide_behind_another_repo(self):
        rows = [{"name": "missing", "status": "active", "path": "/tmp"},
                {"name": "valid", "status": "active", "path": "/tmp", "unit": {"cmd": [sys.executable, "-c", "pass"]}}]
        self.assertEqual(self.run_selection(rows)[0], 1)

    def test_empty_manifest_fails(self):
        self.assertEqual(self.run_selection([])[0], 1)
