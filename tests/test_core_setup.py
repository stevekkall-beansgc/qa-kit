"""Core's registered setup and checks must share the owned Python environment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CoreSetupRegistration(unittest.TestCase):
    def test_registered_checks_use_dependencies_from_owned_setup(self):
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'manifest.json').read_text())
        row = next(r for r in manifest['repos'] if r['name'] == 'beanlabs')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            binaries = root / 'bin'
            binaries.mkdir()
            # The QA launcher may be Python 3.12. Setup must select the
            # registered 3.14 binary rather than inherit that default.
            default_python = binaries / 'python3'
            default_python.write_text('#!/bin/sh\necho "default Python 3.12 cannot run Core setup" >&2\nexit 62\n')
            default_python.chmod(0o700)
            (binaries / 'python3.14').symlink_to(sys.executable)
            npm = binaries / 'npm'
            npm.write_text('#!/bin/sh\necho "QA must call the owned setup" >&2\nexit 63\n')
            npm.chmod(0o700)
            # No downloads: a disposable real venv contains the fixture dependency.
            (scripts / 'setup_tests.py').write_text(
                "import pathlib,subprocess,venv\n"
                "venv.create('.venv-qa', with_pip=False)\n"
                "site=pathlib.Path(subprocess.check_output(['.venv-qa/bin/python','-c',"
                "'import sysconfig; print(sysconfig.get_path(\"purelib\"))'],text=True).strip())\n"
                "(site/'owned_setup_dependency.py').write_text('VALUE = 314\\n')\n"
                "pathlib.Path('setup-ran').touch()\n")
            for name, marker in (('check_prediction.py', 'unit-ran'),
                                 ('check_offline_flows.py', 'e2e-ran')):
                (scripts / name).write_text(
                    "import pathlib,sys\n"
                    "from owned_setup_dependency import VALUE\n"
                    "assert VALUE == 314\n"
                    "assert pathlib.Path(sys.prefix).resolve() == pathlib.Path('.venv-qa').resolve()\n"
                    f"pathlib.Path({marker!r}).touch()\n")
            env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.defpath,
                       PYTHONPATH='', PYTHONNOUSERSITE='1')
            for kind in ('setup', 'unit', 'e2e'):
                result = subprocess.run(row[kind]['cmd'], cwd=root, env=env,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0,
                                 f"{kind}: {result.stdout}{result.stderr}")
            self.assertTrue(all((root / marker).is_file()
                                for marker in ('setup-ran', 'unit-ran', 'e2e-ran')))


if __name__ == '__main__':
    unittest.main()
