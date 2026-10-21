"""The actual shell entrypoint rejects runtimes and propagates unit/stdlib failures."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SelfcheckContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for directory in ('bin', 'scripts', 'tests', 'runtime'): (self.root / directory).mkdir()
        shutil.copy2(ROOT / 'bin/qa_selfcheck.sh', self.root / 'bin/qa_selfcheck.sh')
        shutil.copy2(ROOT / 'bin/validation.py', self.root / 'bin/validation.py')
        for name in ('check_docs.py', 'check_standards.py'):
            (self.root / 'bin' / name).write_text("from pathlib import Path\nPath('started').touch()\n")
        shutil.copy2(ROOT / 'scripts/check_stdlib.py', self.root / 'scripts/check_stdlib.py')
        (self.root / 'tests/test_fixture.py').write_text('import unittest\nclass Tests(unittest.TestCase):\n def test_fixture(self): self.assertTrue(True)\n')
        (self.root / 'runtime/dirname').symlink_to('/usr/bin/dirname')
        (self.root / 'runtime/git').symlink_to(shutil.which('git'))
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        self.env = {**os.environ, 'PATH': str(self.root / 'runtime'), 'CI': 'true', 'QA_SELFCHECK_REPORT': str(self.root / 'provenance.json')}

    def run_it(self, executable=None):
        if executable:
            (self.root / 'runtime/python3').symlink_to(executable)
        return subprocess.run(['/bin/bash', str(self.root / 'bin/qa_selfcheck.sh')],
                              env=self.env, capture_output=True, text=True)

    def test_missing_interpreter_blocks_before_tests(self):
        r = self.run_it(); self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root / 'started').exists())

    def test_wrong_interpreter_blocks_before_tests(self):
        wrong = self.root / 'wrong-python'
        wrong.write_text('#!/bin/sh\nexec ' + sys.executable + ' -c \'import sys; sys.version_info=(3, 13); exec(sys.argv[1])\' \"$2\"\n')
        wrong.chmod(0o755)
        r = self.run_it(wrong); self.assertNotEqual(r.returncode, 0)
        self.assertIn('Python 3.12', r.stderr)
        self.assertFalse((self.root / 'started').exists())

    def test_unit_failure_remains_failure(self):
        (self.root / 'tests/test_fixture.py').write_text('import unittest\nclass Tests(unittest.TestCase):\n def test_fixture(self): self.fail("known unit failure")\n')
        r = self.run_it(sys.executable); self.assertNotEqual(r.returncode, 0)
        self.assertIn('known unit failure', r.stderr)
        self.assertNotIn('stdlib-only OK', r.stdout)
        report = json.loads((self.root / 'provenance.json').read_text())
        self.assertEqual(report['checks']['unit'], 'fail')
        self.assertEqual(report['checks']['stdlib'], 'blocked')

    def test_stdlib_failure_remains_failure(self):
        (self.root / 'bin/forbidden.py').write_text('import definitely_third_party\n')
        r = self.run_it(sys.executable); self.assertNotEqual(r.returncode, 0)
        self.assertIn('definitely_third_party', r.stdout)

    def test_success_includes_stdlib(self):
        r = self.run_it(sys.executable); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('stdlib-only OK', r.stdout)
        self.assertIn('Ran 1 test', r.stderr)
        report = json.loads((self.root / 'provenance.json').read_text())
        self.assertEqual(report['python_version'][:2], [3, 12])
        self.assertEqual(set(report['checks'].values()), {'pass'})
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn(sys.executable, json.dumps(report))
