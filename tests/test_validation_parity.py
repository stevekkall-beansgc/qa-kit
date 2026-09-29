"""Synthetic parity contracts: reject drift before any repo test executes."""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import check_validation as parity
import run_all


class ValidationParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-parity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in (".qa", ".github/workflows", "scripts"):
            (self.root / folder).mkdir(parents=True)
        (self.root / "scripts/validate.sh").write_text("set -eu\nprintf validated > unit-ran\n")
        (self.root / "README.md").write_text("Synthetic fixture. See AGENTS.md.\n")
        (self.root / "AGENTS.md").write_text("## Test commands\n`bash scripts/validate.sh`\n")
        self.spec = {
            "version": 1, "command": ["bash", "scripts/validate.sh"],
            "workflow": ".github/workflows/ci.yml", "workflow_name": "CI",
            "job_id": "validate", "runtimes": {"python": "3.12", "node": "22"},
        }
        self.row = {"name": "synthetic", "path": str(self.root), "status": "active",
                    "unit": {"cmd": self.spec["command"][:]},
                    "validation": {"contract": parity.CONTRACT}}
        self.save()

    def save(self):
        (self.root / parity.CONTRACT).write_text(json.dumps(self.spec))
        (self.root / self.spec["workflow"]).write_text(parity.render_workflow(self.spec))

    def test_same_entrypoint_and_runtime_pins_pass_without_execution(self):
        self.assertEqual(parity.check(self.row), [])
        self.assertFalse((self.root / "unit-ran").exists())

    def test_yaml_reserved_words_are_quoted_as_identifiers(self):
        self.spec["workflow_name"] = "null"
        self.spec["job_id"] = "true"
        self.save()
        workflow = (self.root / self.spec["workflow"]).read_text()
        self.assertIn('name: "null"\n', workflow)
        self.assertIn('  "true":\n', workflow)
        self.assertEqual(parity.check(self.row), [])

    def test_workflow_weakening_and_runtime_drift_are_rejected(self):
        original = parity.render_workflow(self.spec)
        for altered in (
            original.replace("ubuntu-latest", "beans-mac"),
            original.replace('python-version: "3.12"', 'python-version: "3.14"'),
            original.replace('node-version: "22"', 'node-version: "24"'),
            original + "      - run: echo extra-check\n",
            original.replace("        shell: bash", "        continue-on-error: true\n        shell: bash"),
            original.replace("bash scripts/validate.sh", "bash scripts/validate.sh || true"),
        ):
            with self.subTest(altered=altered):
                (self.root / self.spec["workflow"]).write_text(altered)
                self.assertTrue(parity.check(self.row))

    def test_manifest_command_setup_and_environment_drift_rejected(self):
        for fields in (
            {"unit": {"cmd": ["bash", "scripts/validate.sh", "--skip"]}},
            {"setup": {"cmd": ["bash", "install.sh"]}},
            {"unit": {"cmd": self.spec["command"], "env": {"CI": "true"}}},
        ):
            with self.subTest(fields=fields):
                self.assertTrue(parity.check({**self.row, **fields}))

    def test_missing_malformed_and_duplicate_contracts_fail_closed(self):
        target = self.root / parity.CONTRACT
        for text in ("{", "[]", '{"version":1,"version":1}', '{}'):
            target.write_text(text)
            self.assertTrue(parity.check(self.row))
        target.unlink()
        self.assertTrue(parity.check(self.row))

    def test_command_paths_cannot_escape_or_be_options(self):
        for name in ("../escape.sh", "/tmp/outside.sh", "-c"):
            with self.subTest(name=name):
                self.spec["command"][1] = name
                self.save()
                self.assertTrue(parity.check(self.row))

    def test_symlink_entrypoint_refused(self):
        target = self.root / "scripts/validate.sh"
        target.unlink()
        target.symlink_to(self.root / parity.CONTRACT)
        self.assertTrue(parity.check(self.row))

    def test_expressions_and_unknown_fields_refused(self):
        self.spec["command"].append("${{ github.event.pull_request.title }}")
        self.save()
        self.assertTrue(parity.check(self.row))
        self.spec["command"].pop()
        self.spec["allow_failure"] = True
        self.save()
        self.assertTrue(parity.check(self.row))

    def test_unadopted_rows_unchanged_but_invalid_registration_fails(self):
        self.assertEqual(parity.check({"path": "/does-not-exist"}), [])
        for registration in (None, {}, {"contract": "elsewhere.json"}):
            self.assertTrue(parity.check({**self.row, "validation": registration}))

    def test_runtime_checks_refuse_mismatch_missing_and_timeout(self):
        good = [subprocess.CompletedProcess([], 0, "Python 3.12.14\n"),
                subprocess.CompletedProcess([], 0, "v22.18.0\n")]
        with mock.patch.object(parity.subprocess, "run", side_effect=good):
            self.assertEqual(parity.check_runtimes(self.spec), [])
        for failure in (subprocess.CompletedProcess([], 0, "wrong-version"),
                        FileNotFoundError(), subprocess.TimeoutExpired([], 10)):
            with mock.patch.object(parity.subprocess, "run", side_effect=[failure, failure]):
                self.assertEqual(len(parity.check_runtimes(self.spec)), 2)

    def run_qa(self, runtime_issues=None):
        with mock.patch.object(run_all, "load_manifest", return_value={"repos": [self.row]}), \
             mock.patch.object(run_all, "LOGS", self.root / "reports"), \
             mock.patch.object(sys, "argv", ["run_all.py", "--all"]), \
             mock.patch.object(parity, "check_runtimes", return_value=runtime_issues or []), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
            run_all.main()
        reports = sorted((self.root / "reports").glob("*.json"))
        return result.exception.code, json.loads(reports[-1].read_text())["results"]

    def test_qa_reports_parity_and_executes_shared_entrypoint_on_pass(self):
        code, checks = self.run_qa()
        self.assertEqual(code, 0)
        self.assertEqual([c["kind"] for c in checks], ["docs", "validation", "unit"])
        self.assertEqual((self.root / "unit-ran").read_text(), "validated")

    def test_qa_drift_blocks_unit_and_e2e_and_records_failure(self):
        (self.root / self.spec["workflow"]).write_text("# broken workflow\n")
        self.row["e2e"] = {"cmd": ["bash", "scripts/validate.sh"]}
        code, checks = self.run_qa()
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "unit-ran").exists())
        self.assertEqual([c["kind"] for c in checks], ["docs", "validation", "unit", "e2e"])
        self.assertTrue(all(not c["ok"] for c in checks[1:]))

    def test_qa_runtime_mismatch_blocks_execution(self):
        code, checks = self.run_qa(["python: expected 3.12"])
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "unit-ran").exists())
        self.assertIn("expected 3.12", checks[1]["tail"])

    def test_qa_malformed_adopted_unit_fails_with_report(self):
        self.row["unit"] = ["invalid"]
        code, checks = self.run_qa()
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "unit-ran").exists())
        self.assertFalse(checks[1]["ok"])
        self.assertIn("must be objects", checks[1]["tail"])

    def test_cli_unknown_or_unadopted_selection_cannot_claim_green(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"repos": [{k: v for k, v in self.row.items() if k != "validation"}]}))
        result = subprocess.run([sys.executable, str(Path(parity.__file__)), "--root", str(self.root),
                                 "--manifest", str(manifest), "--repo", "synthetic"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
