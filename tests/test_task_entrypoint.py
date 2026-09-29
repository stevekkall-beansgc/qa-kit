"""Keep the Task wrapper and trusted-push workflow scope explicit."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TaskEntrypoint(unittest.TestCase):
    def test_validate_wraps_existing_deterministic_checks(self):
        taskfile = (ROOT / 'Taskfile.yml').read_text()
        self.assertIn("version: '3'", taskfile)
        self.assertIn('sys.version_info[:2] != (3, 12)', taskfile)
        self.assertIn('      - CI=true bash bin/qa_selfcheck.sh\n', taskfile)
        self.assertIn('      - python3 scripts/check_stdlib.py bin/\n', taskfile)
        self.assertNotIn('run_all.py', taskfile)
        self.assertNotIn('ignore_error', taskfile)

    def test_hosted_python312_pr_checks_remain(self):
        workflow = (ROOT / '.github/workflows/test.yml').read_text()
        hosted = workflow.split('  task-validate-local:')[0]
        self.assertIn('  pull_request:\n', hosted)
        self.assertIn('    runs-on: ubuntu-latest\n', hosted)
        self.assertIn('          python-version: "3.12"\n', hosted)
        self.assertIn('      - run: python3 -m unittest discover -s tests -v\n', hosted)
        self.assertIn('      - run: python3 scripts/check_stdlib.py bin/\n', hosted)
        self.assertNotIn('pull_request_target', workflow)

    def test_local_job_is_only_canonical_main_push(self):
        workflow = (ROOT / '.github/workflows/test.yml').read_text()
        local = workflow.split('  task-validate-local:', 1)[1]
        self.assertIn("if: github.repository == 'stevekkall-beansgc/qa-kit' && github.event_name == 'push' && github.ref == 'refs/heads/main'", local)
        self.assertIn('runs-on: [self-hosted, macOS, ARM64, beans-mac]', local)
        self.assertLess(local.index('test "$RUNNER_NAME" = "beans-macbook-qa-kit"'),
                        local.index('uses: actions/checkout@v5'))
        self.assertIn('ref: ${{ github.sha }}', local)
        self.assertIn('persist-credentials: false', local)
        self.assertIn('task validate', local)
        self.assertNotIn('pull_request.head', local)


if __name__ == '__main__':
    unittest.main()
