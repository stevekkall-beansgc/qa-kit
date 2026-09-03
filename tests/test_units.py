"""Unit tests for qa-kit helpers — pure logic; network only via localhost."""
import json
import sys
import os
import tempfile
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import health  # noqa: E402
import reconcile  # noqa: E402
import check_standards  # noqa: E402


class TestProbeUrl(unittest.TestCase):
    def test_refused_is_down(self):
        ok, err = health.probe_url("http://127.0.0.1:1/", timeout=1)
        self.assertFalse(ok)
        self.assertTrue(err)

    def _serve(self, code):
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(code)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv

    def test_2xx_is_up(self):
        srv = self._serve(200)
        try:
            ok, _ = health.probe_url(f"http://127.0.0.1:{srv.server_port}/", timeout=3)
            self.assertTrue(ok)
        finally:
            srv.shutdown()

    def test_5xx_is_down_by_definition(self):
        srv = self._serve(503)
        try:
            ok, _ = health.probe_url(f"http://127.0.0.1:{srv.server_port}/", timeout=3)
            self.assertFalse(ok)  # probe_url: alive iff status < 500
        finally:
            srv.shutdown()


class TestReconcile(unittest.TestCase):
    def test_is_git_repo(self):
        d = Path(tempfile.mkdtemp())
        self.assertFalse(reconcile.is_git_repo(d))
        (d / ".git").mkdir()
        self.assertTrue(reconcile.is_git_repo(d))


class TestStandardsResolution(unittest.TestCase):
    def test_cross_repo_target_falls_back_to_canonical_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            isolated = root / "qa-worktree"
            canonical = root / "beans"
            target = canonical / "platform" / "gate-kit" / "bin" / "compliance.py"
            target.parent.mkdir(parents=True)
            target.write_text("advisory\n")
            old_here = check_standards.HERE
            old_workspace = os.environ.get("BEAN_WORKSPACE_ROOT")
            try:
                check_standards.HERE = isolated
                os.environ["BEAN_WORKSPACE_ROOT"] = str(canonical)
                self.assertEqual(
                    check_standards.resolve_target("../gate-kit/bin/compliance.py"),
                    target.resolve(),
                )
            finally:
                check_standards.HERE = old_here
                if old_workspace is None:
                    os.environ.pop("BEAN_WORKSPACE_ROOT", None)
                else:
                    os.environ["BEAN_WORKSPACE_ROOT"] = old_workspace


class TestManifestContract(unittest.TestCase):
    def test_agency_setup_validates_runtime_and_installs_dependencies(self):
        manifest = json.loads(
            (Path(__file__).resolve().parents[1] / "manifest.json").read_text()
        )
        agency = next(repo for repo in manifest["repos"] if repo["name"] == "agency")
        self.assertEqual(agency["setup"]["cmd"][:2], ["bash", "-c"])
        setup = " ".join(agency["setup"]["cmd"])
        self.assertIn("sys.version_info >= (3, 10)", setup)
        self.assertIn("python3.12", setup)
        self.assertIn("venv --clear", setup)
        self.assertIn("-r server/requirements.txt", setup)

    def _run_agency_setup(self, *, clawstr=True, bootstrap=True, pip_exit=0, bootstrap_exit=0):
        manifest = json.loads((Path(__file__).resolve().parents[1] / "manifest.json").read_text())
        command = next(repo for repo in manifest["repos"] if repo["name"] == "agency")["setup"]["cmd"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text('#!/bin/sh\nif [ "$1 $2" = "-m pip" ]; then\n  echo python >> "$QA_SETUP_TRACE"\n  exit "$QA_SETUP_PIP_EXIT"\nfi\nexit 0\n')
            python.chmod(0o700)
            if clawstr:
                setup = root / "setup/clawstr"
                setup.mkdir(parents=True)
                if bootstrap:
                    (setup / "bootstrap.sh").write_text('echo clawstr >> "$QA_SETUP_TRACE"\nexit "$QA_SETUP_BOOTSTRAP_EXIT"\n')
            trace = root / "trace"
            env = dict(os.environ, QA_SETUP_TRACE=str(trace), QA_SETUP_PIP_EXIT=str(pip_exit),
                       QA_SETUP_BOOTSTRAP_EXIT=str(bootstrap_exit))
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=20)
            return result.returncode, trace.read_text().splitlines() if trace.exists() else []

    def test_agency_setup_runs_clawstr_bootstrap_after_python(self):
        self.assertEqual(self._run_agency_setup(), (0, ["python", "clawstr"]))

    def test_agency_setup_preserves_older_checkouts_without_clawstr(self):
        self.assertEqual(self._run_agency_setup(clawstr=False), (0, ["python"]))

    def test_agency_setup_fails_closed_on_missing_or_failed_bootstrap(self):
        code, trace = self._run_agency_setup(bootstrap=False)
        self.assertNotEqual(code, 0)
        self.assertEqual(trace, ["python"])
        self.assertEqual(self._run_agency_setup(bootstrap_exit=23), (23, ["python", "clawstr"]))

    def test_agency_setup_stops_after_python_install_failure(self):
        self.assertEqual(self._run_agency_setup(pip_exit=19), (19, ["python"]))


if __name__ == "__main__":
    unittest.main()
