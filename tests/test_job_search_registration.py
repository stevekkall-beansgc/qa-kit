import json
from pathlib import Path
import unittest


class JobSearchRegistrationTests(unittest.TestCase):
    def test_active_job_search_runs_owned_combined_e2e(self):
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'manifest.json').read_text())
        entries = [row for row in manifest['repos'] if row['name'] == 'job-search']
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['status'], 'active')
        self.assertEqual(entries[0]['unit']['cmd'], ['npm', 'test'])
        self.assertEqual(entries[0]['e2e']['cmd'], ['python3', 'scripts/run_e2e.py'])


if __name__ == '__main__':
    unittest.main()
