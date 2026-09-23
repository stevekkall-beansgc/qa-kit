#!/usr/bin/env python3
"""Clean-room synthetic quickstart for qa-kit.

Runs the REAL bin/run_all.py against a disposable, synthetic repository
created under a temp directory, and writes timestamped JSON reports to a
disposable logs directory. No BeanLabs workspace, no network, no real data,
no credentials.

Demonstrates, in order:
  1. a passing docs + unit run  (exit 0, JSON report written)
  2. a failing docs run         (nonzero exit, JSON report preserved)
  3. a failing unit run         (nonzero exit, JSON report preserved)

Usage: python3 examples/synthetic_quickstart.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RUN_ALL = HERE / "bin" / "run_all.py"

UNIT_CMD = ["python3", "-m", "unittest", "discover", "-s", "tests"]
UNIT_TEXT = " ".join(UNIT_CMD)


def write_repo(root, label, *, good_docs, bad_test):
    repo = root / ("repo-" + label)
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text(f"# synthetic-{label}\n\nSee AGENTS.md.\n")
    if good_docs:
        (repo / "AGENTS.md").write_text(
            f"# synthetic-{label}\n\n## Test commands\n- {UNIT_TEXT}\n")
    if bad_test:
        (repo / "tests" / "test_bad.py").write_text(
            "import unittest\n"
            "\n"
            "class TestBad(unittest.TestCase):\n"
            "    def test_bad(self):\n"
            "        self.fail('synthetic failure')\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n")
    else:
        (repo / "tests" / "test_ok.py").write_text(
            "import unittest\n"
            "\n"
            "class TestOk(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertTrue(True)\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n")
    return repo


def write_manifest(path, repo):
    path.write_text(json.dumps({
        "version": 1,
        "description": "clean-room synthetic manifest",
        "tiers": {"B": "docs/meta"},
        "repos": [{
            "name": "synthetic-" + repo.name,
            "path": str(repo),
            "tier": "B",
            "status": "active",
            "unit": {"cmd": UNIT_CMD},
            "e2e": {"cmd": None},
        }],
    }, indent=2))


def run_scenario(root, label, *, docs_ok, unit_ok, expect_fail):
    repo = write_repo(root, label, good_docs=docs_ok, bad_test=not unit_ok)
    manifest = root / f"manifest-{label}.json"
    logs = root / "logs" / label
    write_manifest(manifest, repo)
    proc = subprocess.run(
        [sys.executable, str(RUN_ALL), "--all",
         "--manifest", str(manifest), "--logs-dir", str(logs)],
        capture_output=True, text=True, timeout=120)
    reports = sorted(logs.glob("run-*.json"))
    detail = proc.stdout + proc.stderr
    if not reports:
        raise SystemExit(f"{label}: no JSON report written to {logs}\n{detail}")
    report = json.loads(reports[-1].read_text())
    if expect_fail and proc.returncode == 0:
        raise SystemExit(f"{label}: expected nonzero exit, got 0\n{detail}")
    if not expect_fail and proc.returncode != 0:
        raise SystemExit(f"{label}: expected exit 0, got {proc.returncode}\n{detail}")
    return proc.returncode, report


def main():
    with tempfile.TemporaryDirectory(prefix="qa-kit-synthetic-") as tmp:
        root = Path(tmp)

        code, report = run_scenario(root, "pass",
                                    docs_ok=True, unit_ok=True, expect_fail=False)
        if not all(r["ok"] for r in report["results"]):
            raise SystemExit("pass: a result failed unexpectedly")
        print(f"PASS  docs+unit run: exit {code}, all {len(report['results'])} "
              "results ok, JSON report written")

        code, report = run_scenario(root, "bad-docs",
                                    docs_ok=False, unit_ok=True, expect_fail=True)
        if not any(not r["ok"] and r["kind"] == "docs" for r in report["results"]):
            raise SystemExit("bad-docs: no failing docs verdict in report")
        print(f"PASS  failing docs run: exit {code}, docs FAIL recorded, JSON report written")

        code, report = run_scenario(root, "bad-unit",
                                    docs_ok=True, unit_ok=False, expect_fail=True)
        if not any(not r["ok"] and r["kind"] == "unit" for r in report["results"]):
            raise SystemExit("bad-unit: no failing unit verdict in report")
        print(f"PASS  failing unit run: exit {code}, unit FAIL recorded, JSON report written")

    print("synthetic quickstart OK (3/3 scenarios, all output in disposable dirs)")


if __name__ == "__main__":
    main()