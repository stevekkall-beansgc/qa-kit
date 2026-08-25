"""Unit tests for qa-kit helpers — pure logic; network only via localhost."""
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import health  # noqa: E402
import reconcile  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
