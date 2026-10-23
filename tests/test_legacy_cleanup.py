"""Legacy runner timeouts must stop descendants from writing after verdicts."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import run_all


@unittest.skipUnless(os.name == 'posix', 'process groups are a POSIX contract')
class LegacyProcessCleanup(unittest.TestCase):
    def assert_timeout_stops_descendant(self, *, parent_exits):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Every fixture process is local and bounded, including on old code.
            # Ignoring TERM proves cleanup does not leave stubborn descendants.
            (root / 'child.py').write_text(
                "import json,os,pathlib,signal,time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "pathlib.Path('ready.json').write_text(json.dumps({"
                "'started':time.monotonic(),'group':os.getpgrp()}))\n"
                "time.sleep(3)\n"
                "pathlib.Path('late-write').write_text('survived timeout')\n")
            (root / 'parent.py').write_text(
                "import subprocess,sys,time\n"
                "subprocess.Popen([sys.executable,'child.py'])\n"
                + ("" if parent_exits else "time.sleep(10)\n"))
            row = {'name': 'fixture', 'path': str(root),
                   'unit': {'cmd': [sys.executable, 'parent.py']}}
            with mock.patch.object(run_all, 'TIMEOUT_SECS', 2):
                result = run_all.run_repo(row, 'unit')
            self.assertEqual(set(result), {'repo', 'kind', 'ok', 'secs', 'tail'})
            self.assertEqual((result['repo'], result['kind'], result['ok']),
                             ('fixture', 'unit', False))
            self.assertEqual(result['tail'], 'TIMEOUT after 2s')
            self.assertTrue((root / 'ready.json').exists(), 'child must start before the timeout')
            ready = json.loads((root / 'ready.json').read_text())
            time.sleep(max(0, ready['started'] + 3.3 - time.monotonic()))
            self.assertFalse((root / 'late-write').exists(),
                             'a descendant wrote after its check timed out')
            self.assertNotEqual(ready['group'], os.getpgrp(),
                                'cleanup must target a separate process group')

    def test_timeout_stops_child_while_parent_is_running(self):
        self.assert_timeout_stops_descendant(parent_exits=False)

    def test_timeout_stops_child_even_after_parent_exited(self):
        self.assert_timeout_stops_descendant(parent_exits=True)


if __name__ == '__main__':
    unittest.main()
