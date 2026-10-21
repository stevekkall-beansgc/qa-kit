#!/usr/bin/env bash
# Canonical QA Kit checks, including legacy manifest callers that bypass Task.
set -e
cd "$(dirname "$0")/.."
runtime=blocked docs=blocked standards=blocked unit=blocked stdlib=blocked
finish() {
  status=$?
  trap - EXIT
  if [[ -n "${QA_SELFCHECK_REPORT:-}" ]]; then
    # Explicit caller-owned destination; no raw child output or local binary path.
    python3 - "$QA_SELFCHECK_REPORT" "$status" "$runtime" "$docs" "$standards" "$unit" "$stdlib" <<'PY'
import hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path('bin').resolve()))
from validation import identity
source = identity(pathlib.Path.cwd())
checks = dict(zip(('runtime', 'docs', 'standards', 'unit', 'stdlib'), sys.argv[3:]))
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
report = {'schema': 'qa-kit.selfcheck-provenance/v1', 'candidate': head, 'candidate_source': source,
          'entrypoint': 'bash bin/qa_selfcheck.sh',
          'entrypoint_sha256': hashlib.sha256(pathlib.Path('bin/qa_selfcheck.sh').read_bytes()).hexdigest(),
          'python_version': list(sys.version_info[:3]),
          'python_binary_sha256': hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),
          'exit_code': int(sys.argv[2]), 'checks': checks}
with open(sys.argv[1], 'x') as stream:
    json.dump(report, stream, sort_keys=True)
    stream.write('\n')
PY
    report_status=$?
    if [[ "$status" == 0 && "$report_status" != 0 ]]; then status=$report_status; fi
  fi
  exit "$status"
}
trap finish EXIT
# No fallback or install: the caller must supply the declared interpreter.
runtime=fail
python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else "Python 3.12 must be available as python3")'
runtime=pass
docs=fail
if [[ "${CI:-}" == "true" ]]; then python3 bin/check_docs.py --self-only; else python3 bin/check_docs.py; fi
docs=pass
standards=fail
if [[ "${CI:-}" == "true" ]]; then python3 bin/check_standards.py --self-only; else python3 bin/check_standards.py; fi
standards=pass
unit=fail
python3 -m unittest discover -s tests -v
unit=pass
stdlib=fail
python3 scripts/check_stdlib.py bin/
stdlib=pass
