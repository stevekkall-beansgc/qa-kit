import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples import synthetic_quickstart

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REPORT_URL = "https://github.com/stevekkall-beansgc/qa-kit/security/advisories/new"
SAMPLE_REPORT = ROOT / "examples" / "synthetic_quickstart_report.json"


class PublicDocumentationTests(unittest.TestCase):
    def test_standalone_quickstart_precedes_fleet_operations(self):
        readme = (ROOT / "README.md").read_text()
        command = "python3 examples/synthetic_quickstart.py"
        self.assertTrue((ROOT / "examples" / "synthetic_quickstart.py").is_file())
        self.assertIn(command, readme)
        self.assertLess(
            readme.index(command), readme.index("## Legume Labs fleet operations"))
        self.assertIn("## Exact limitations", readme)

    def test_security_policy_names_private_reporting_and_support_scope(self):
        security = (ROOT / "SECURITY.md").read_text()
        self.assertIn(PRIVATE_REPORT_URL, security)
        self.assertIn("Private vulnerability reporting is enabled", security)
        self.assertIn("current `main` branch and the latest tagged release", security)
        self.assertIn("external Legume Labs repositories", security)

    def test_contributing_is_self_contained_for_public_checkout(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text()
        for command in (
            "git clone https://github.com/stevekkall-beansgc/qa-kit.git",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/check_stdlib.py bin/",
            "CI=true bash bin/qa_selfcheck.sh",
            "python3 examples/synthetic_quickstart.py",
            "python3 examples/synthetic_quickstart.py --write-sample "
            "examples/synthetic_quickstart_report.json",
            "python3 examples/synthetic_quickstart.py --verify-sample "
            "examples/synthetic_quickstart_report.json",
        ):
            self.assertIn(command, contributing)
        self.assertIn(
            "`--write-sample` writes the report to the requested `PATH`; the command",
            contributing,
        )
        self.assertIn("overwrites the checked-in sample.", contributing)
        self.assertNotIn("Agency contribution guide", contributing)
        self.assertIn("do not edit the private fleet", contributing)

    def test_runtime_contract_matches_test_workflow(self):
        workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text()
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn('python-version: "3.12"', workflow)
        for document in ("README.md", "CONTRIBUTING.md"):
            text = (ROOT / document).read_text()
            self.assertIn("Python 3.12", text)
            self.assertRegex(text, r"not\s+claimed as supported")

    def test_public_sample_report_is_sanitized_and_stable(self):
        self.assertTrue(SAMPLE_REPORT.is_file())
        sample = json.loads(SAMPLE_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(set(sample), {"when", "results", "planned_skipped"})
        self.assertEqual(sample["when"], "20260924T000000Z")
        self.assertEqual(sample["planned_skipped"], [])
        self.assertEqual([result["kind"] for result in sample["results"]],
                         ["docs", "unit"])
        self.assertTrue(all(result["ok"] for result in sample["results"]))
        self.assertTrue(all(result["repo"].startswith("synthetic-")
                            for result in sample["results"]))
        self.assertIn("<elapsed>s", sample["results"][1]["tail"])
        serialized = json.dumps(sample)
        for private_value in ("/tmp", "~/beans", "stevekkall", "credential", "secret"):
            self.assertNotIn(private_value.lower(), serialized.lower())

    def test_public_sample_matches_a_real_quickstart_pass_report(self):
        sample = json.loads(SAMPLE_REPORT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="qa-kit-test-") as directory:
            code, report = synthetic_quickstart.run_scenario(
                Path(directory), "pass", docs_ok=True, unit_ok=True, expect_fail=False)
        self.assertEqual(code, 0)
        self.assertEqual(synthetic_quickstart.public_sample_report(report), sample)

    def test_full_quickstart_cli_verifies_all_scenarios_and_sample(self):
        child = subprocess.run(
            ["python3", "-c", "import json, sys; print(json.dumps({"
             "'version': sys.version.split()[0], "
             "'minor': list(sys.version_info[:2])}))"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=10,
        )
        runtime = json.loads(child.stdout)
        self.assertEqual(runtime["minor"], list(sys.version_info[:2]),
                         "quickstart's python3 child must match the test driver")
        result = subprocess.run(
            [sys.executable, "examples/synthetic_quickstart.py", "--verify-sample",
             "examples/synthetic_quickstart_report.json"],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.splitlines(), [
            "PASS  docs+unit run: exit 0, all 2 results ok, JSON report written",
            "PASS  failing docs run: exit 1, docs FAIL recorded, JSON report written",
            "PASS  failing unit run: exit 1, unit FAIL recorded, JSON report written",
            "PASS  sample report verified: examples/synthetic_quickstart_report.json",
            "synthetic quickstart OK (3/3 scenarios, all output in disposable dirs)",
        ])
        # Only successful synthetic output/runtime versions are emitted for CI proof.
        print(f"Quickstart CLI runtime: driver {sys.version.split()[0]}, "
              f"child {runtime['version']}, platform {sys.platform}")
        print(result.stdout, end="")


if __name__ == "__main__":
    unittest.main()
