"""Unit tests for qa-kit helpers — pure logic; network only via localhost."""
import json
import sys
import os
import tempfile
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
        setup = " ".join(agency["setup"]["cmd"])
        self.assertIn("sys.version_info >= (3, 10)", setup)
        self.assertIn("python3.12", setup)
        self.assertIn("venv --clear", setup)
        self.assertIn("-r server/requirements.txt", setup)


if __name__ == "__main__":
    unittest.main()
