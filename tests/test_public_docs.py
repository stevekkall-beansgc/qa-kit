import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REPORT_URL = "https://github.com/stevekkall-beansgc/qa-kit/security/advisories/new"


class PublicDocumentationTests(unittest.TestCase):
    def test_standalone_quickstart_precedes_fleet_operations(self):
        readme = (ROOT / "README.md").read_text()
        command = "python3 examples/synthetic_quickstart.py"
        self.assertTrue((ROOT / "examples" / "synthetic_quickstart.py").is_file())
        self.assertIn(command, readme)
        self.assertLess(
            readme.index(command), readme.index("## BeanLabs fleet operations"))
        self.assertIn("## Exact limitations", readme)

    def test_security_policy_names_private_reporting_and_support_scope(self):
        security = (ROOT / "SECURITY.md").read_text()
        self.assertIn(PRIVATE_REPORT_URL, security)
        self.assertIn("Private vulnerability reporting is enabled", security)
        self.assertIn("current `main` branch and the latest tagged release", security)
        self.assertIn("external BeanLabs repositories", security)


if __name__ == "__main__":
    unittest.main()
