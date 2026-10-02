"""Keep third-party workflow actions immutable without changing the caller."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkflowPins(unittest.TestCase):
    def test_third_party_actions_use_full_commit_ids(self):
        found = []
        for path in sorted((ROOT / '.github/workflows').glob('*.yml')):
            for action, ref in re.findall(r'uses:\s+([^@\s]+)@([^\s#]+)', path.read_text()):
                if action.startswith('stevekkall-beansgc/'):
                    continue
                found.append(action)
                with self.subTest(workflow=path.name, action=action):
                    self.assertRegex(ref, r'^[0-9a-f]{40}$')
        self.assertTrue(found, 'No third-party actions inspected')
