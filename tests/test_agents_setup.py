"""Execute the registered Beanstalk setup with isolated interpreter fixtures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


MANIFEST = Path(__file__).resolve().parents[1] / 'manifest.json'


class AgentsSetup(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.trace = self.root / 'trace.jsonl'
        # Preserve the manifest's shell flags, but never source host login files.
        shell = self.bin / 'bash'
        shell.write_text('#!/bin/sh\nexec /bin/bash --noprofile --norc "$@"\n')
        shell.chmod(0o700)
        self.env = {'PATH': str(self.bin), 'QA_SETUP_TRACE': str(self.trace),
                    'QA_SETUP_PIP_EXIT': '0'}
        self.row = next(r for r in json.loads(MANIFEST.read_text())['repos']
                        if r['name'] == 'agents')

    def interpreter(self, path, version, *, environment_prefix=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'''#!{sys.executable}
import json, os, pathlib, shutil, sys
version = {version!r}
args = sys.argv[1:]
def record(event):
    with open(os.environ['QA_SETUP_TRACE'], 'a') as stream:
        stream.write(json.dumps({{'event':event,'version':version,'args':args}}) + '\\n')
if args[0] == '-c':
    sys.version_info = (*version, 0, 'final', 0)
    if pathlib.Path(sys.argv[0]).parent.parent.name == '.venv':
        sys.prefix = {environment_prefix!r} or str(pathlib.Path(sys.argv[0]).parent.parent.resolve())
    exec(args[1])
elif args[:2] == ['-m', 'venv']:
    record('venv')
    source = pathlib.Path(sys.argv[0]).read_text()
    target = pathlib.Path(args[-1])
    if target.exists() and '--clear' in args:
        shutil.rmtree(target)
    executable = target / 'bin/python'
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(source)
    executable.chmod(0o700)
    (target / 'pyvenv.cfg').write_text('version = ' + '.'.join(map(str, version)))
elif args[:3] == ['-m', 'pip', 'install']:
    record('install')
    raise SystemExit(int(os.environ['QA_SETUP_PIP_EXIT']) if version == (3, 14) else 91)
else:
    raise SystemExit('unexpected fixture invocation: ' + repr(args))
''')
        path.chmod(0o700)
        if path.parent.parent.name == '.venv':
            (path.parent.parent / 'pyvenv.cfg').write_text('version = ' + '.'.join(map(str, version)))

    def setup(self):
        result = subprocess.run(self.row['setup']['cmd'], cwd=self.root, env=self.env,
                                capture_output=True, text=True, timeout=10)
        events = [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []
        return result, events

    def test_wrong_default_uses_available_python314(self):
        for version in ((3, 12), (3, 13), (3, 15)):
            with self.subTest(version=version):
                # Each subtest starts with no venv or installation record.
                shutil.rmtree(self.root / '.venv', ignore_errors=True)
                self.trace.unlink(missing_ok=True)
                self.interpreter(self.bin / 'python3', version)
                self.interpreter(self.bin / 'python3.14', (3, 14))
                result, events = self.setup()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([(e['event'], e['version']) for e in events],
                                 [('venv', [3, 14]), ('install', [3, 14])])

    def test_fresh_setup_uses_explicit_python314_even_with_compatible_default(self):
        self.interpreter(self.bin / 'python3', (3, 14))
        self.interpreter(self.bin / 'python3.14', (3, 14))
        result, events = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e['version'] for e in events], [[3, 14], [3, 14]])

    def test_incompatible_existing_venv_is_rejected_without_replacement(self):
        self.interpreter(self.bin / 'python3', (3, 12))
        self.interpreter(self.bin / 'python3.14', (3, 14))
        self.interpreter(self.root / '.venv/bin/python', (3, 13))
        marker = self.root / '.venv/old-runtime-marker'
        marker.touch()
        result, events = self.setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Existing .venv must be a Python 3.14 virtual environment', result.stderr)
        self.assertEqual(events, [])
        self.assertTrue(marker.exists())

    def test_valid_existing_venv_is_reused_without_another_base_binary(self):
        self.interpreter(self.bin / 'python3', (3, 13))
        self.interpreter(self.root / '.venv/bin/python', (3, 14))
        marker = self.root / '.venv/keep'
        marker.touch()
        result, events = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e['event'] for e in events], ['install'])
        self.assertTrue(marker.exists())

    def test_missing_python314_fails_before_install_or_venv_creation(self):
        self.interpreter(self.bin / 'python3', (3, 13))
        result, events = self.setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.14 required', result.stderr)
        self.assertEqual(events, [])
        self.assertFalse((self.root / '.venv').exists())

    def test_symlinked_venv_is_rejected_without_touching_its_target(self):
        target = self.root / 'unrelated'
        target.mkdir()
        marker = target / 'keep'
        marker.touch()
        (self.root / '.venv').symlink_to(target, target_is_directory=True)
        self.interpreter(self.bin / 'python3', (3, 14))
        self.interpreter(self.bin / 'python3.14', (3, 14))
        result, events = self.setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Refusing symlinked .venv', result.stderr)
        self.assertEqual(events, [])
        self.assertEqual(list(target.iterdir()), [marker])

    def test_existing_directory_without_venv_metadata_is_not_modified(self):
        directory = self.root / '.venv'
        directory.mkdir()
        marker = directory / 'keep'
        marker.touch()
        self.interpreter(self.bin / 'python3', (3, 14))
        self.interpreter(self.bin / 'python3.14', (3, 14))
        result, events = self.setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Existing .venv must be a Python 3.14 virtual environment', result.stderr)
        self.assertEqual(events, [])
        self.assertEqual(list(directory.iterdir()), [marker])

    def test_interpreter_belonging_to_another_environment_is_rejected(self):
        self.interpreter(self.root / '.venv/bin/python', (3, 14),
                         environment_prefix=str(self.root / 'unrelated'))
        result, events = self.setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Existing .venv must be a Python 3.14 virtual environment', result.stderr)
        self.assertEqual(events, [])

    def test_misnamed_python314_binary_is_rejected(self):
        self.interpreter(self.bin / 'python3', (3, 12))
        self.interpreter(self.bin / 'python3.14', (3, 15))
        result, events = self.setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.14 required', result.stderr)
        self.assertEqual(events, [])

    def test_install_failure_propagates(self):
        self.interpreter(self.bin / 'python3', (3, 14))
        self.interpreter(self.bin / 'python3.14', (3, 14))
        self.env['QA_SETUP_PIP_EXIT'] = '37'
        result, events = self.setup()
        self.assertEqual(result.returncode, 37)
        self.assertEqual([e['event'] for e in events], ['venv', 'install'])
        self.assertEqual(events[-1]['args'], ['-m', 'pip', 'install', '--quiet', '-e', '.'])


if __name__ == '__main__':
    unittest.main()
