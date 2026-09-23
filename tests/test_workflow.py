"""The public gate caller must not expose the self-hosted runner to PRs."""
from pathlib import Path
import unittest


class GateCallerTests(unittest.TestCase):
    def test_pull_requests_use_hosted_runner(self):
        caller = (Path(__file__).resolve().parents[1] /
                  ".github/workflows/gate.yml").read_text()
        self.assertIn("on: [pull_request, push]", caller)
        self.assertIn(
            "runner: ${{ github.event_name == 'push' && (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/heads/release/')) && 'beans-mac' || 'ubuntu-latest' }}",
            caller,
        )


if __name__ == "__main__":
    unittest.main()
