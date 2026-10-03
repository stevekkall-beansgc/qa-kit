"""Protect the owned token, event and checkout boundaries without a YAML dependency.

These workflows use a deliberately small mapping/list shape. Inspect fields at
their actual indentation, rejecting duplicates and unexpected fields rather
than finding a reassuring substring elsewhere in the document. This is a
repository contract test, not a general YAML parser or hosted-run qualification.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_IF = ("github.repository == 'stevekkall-beansgc/qa-kit' && "
            "github.event_name == 'push' && github.ref == 'refs/heads/main'")
GATE_RUNNER = ("${{ github.event_name == 'push' && (github.ref == 'refs/heads/main' "
               "|| startsWith(github.ref, 'refs/heads/release/')) && 'beans-mac' "
               "|| 'ubuntu-latest' }}")


def mapping(text, indent):
    """Return direct scalar fields and their bodies; fail on unsupported shape."""
    lines = [line for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    fields = {}
    starts = []
    for index, line in enumerate(lines):
        depth = len(line) - len(line.lstrip(' '))
        assert '\t' not in line[:depth + 1], 'tab indentation'
        assert depth >= indent, 'field escaped its parent'
        if depth == indent:
            match = re.fullmatch(r' *([A-Za-z][A-Za-z0-9_-]*):(?: (.*))?', line)
            assert match, f'unsupported mapping field: {line}'
            starts.append((index, match.group(1), match.group(2) or ''))
    for position, (index, key, value) in enumerate(starts):
        assert key not in fields, f'duplicate field: {key}'
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        fields[key] = (value, '\n'.join(lines[index + 1:end]))
    return fields


def nested(fields, key, indent):
    value, body = fields[key]
    assert value == '', f'{key} must be a mapping'
    return mapping(body, indent)


def scalar(fields, key):
    value, body = fields[key]
    assert not body, f'{key} must be a scalar'
    return value


def steps(job):
    value, body = job['steps']
    assert value == '', 'steps must be a list'
    chunks = re.split(r'(?m)^      - ', body)
    assert not chunks[0].strip(), 'unsupported step list'
    return [mapping('        ' + chunk, 8) for chunk in chunks[1:]]


def read_ceiling(workflow):
    assert 'permissions' in workflow, 'missing workflow permission ceiling'
    permissions = nested(workflow, 'permissions', 2)
    assert permissions == {'contents': ('read', '')}, 'workflow needs contents:read only'
    for job in nested(workflow, 'jobs', 2).values():
        assert not job[0], 'job must be a mapping'
        fields = mapping(job[1], 4)
        if 'permissions' in fields:
            assert nested(fields, 'permissions', 6) == {'contents': ('read', '')}, \
                'job escalated the read ceiling'


def checkout_boundary(job, expected):
    checkouts = [step for step in steps(job)
                 if step.get('uses', ('', ''))[0].startswith('actions/checkout@')]
    assert len(checkouts) == 1, 'one owned source checkout required'
    checkout = checkouts[0]
    assert set(checkout) == {'uses', 'with'}, 'unexpected checkout field'
    assert nested(checkout, 'with', 10) == expected, 'checkout source/credential drift'


def runner_precheck(local_steps):
    # Close the reviewed step shape and body. This is an exact source contract,
    # not a claim to evaluate arbitrary YAML conditions or shell programs.
    assert local_steps[0] == {
        'name': ('Verify the existing QA runner before checkout', ''),
        'shell': ('bash', ''),
        'run': ('|', '\n'.join([
            '          test "$RUNNER_NAME" = "beans-macbook-qa-kit"',
            '          /opt/homebrew/opt/python@3.12/libexec/bin/python3 --version',
            '          /opt/homebrew/bin/task --version',
        ])),
    }, 'runner precheck must execute the exact reviewed guard and propagate failure'


def execution_boundary(hosted, local):
    hosted_steps, local_steps = steps(hosted), steps(local)
    assert len(hosted_steps) == 4 and len(local_steps) == 3, 'reviewed step order/count changed'
    runner_precheck(local_steps)
    assert hosted_steps[2:] == [
        {'run': ('python3 -m unittest discover -s tests -v', '')},
        {'run': ('python3 scripts/check_stdlib.py bin/', '')},
    ], 'hosted checks must execute reviewed commands and propagate failure'
    assert local_steps[2] == {
        'name': ('Run task validate on macOS ARM64 with Python 3.12', ''),
        'shell': ('bash', ''),
        'run': ('|', '\n'.join([
            '          export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:/usr/bin:/bin"',
            '          test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
            '          task validate',
        ])),
    }, 'local validation must execute the exact source guard/Task and propagate failure'


def test_contract(text, boundary='all'):
    workflow = mapping(text, 0)
    assert {'name', 'on', 'jobs'} <= set(workflow) <= {'name', 'on', 'permissions', 'jobs'}, \
        'unexpected workflow field'
    assert scalar(workflow, 'name') == 'test', 'workflow name is an API'
    jobs = nested(workflow, 'jobs', 2)
    assert set(jobs) == {'unittest', 'task-validate-local'}, 'check identities changed'
    hosted = nested(jobs, 'unittest', 4)
    local = nested(jobs, 'task-validate-local', 4)
    if boundary in ('all', 'permissions'):
        read_ceiling(workflow)
    if boundary in ('all', 'events'):
        events = nested(workflow, 'on', 2)
        assert set(events) == {'push', 'pull_request'}, 'unauthorized event'
        assert nested(events, 'push', 4) == {'branches': ('[main]', '')}, 'push scope drift'
        assert events['pull_request'] == ('', ''), 'PR scope drift'
        assert set(hosted) == {'runs-on', 'steps'}, 'hosted job scope drift'
        assert scalar(hosted, 'runs-on') == 'ubuntu-latest', 'PR runner drift'
        assert set(local) == {'if', 'runs-on', 'permissions', 'timeout-minutes', 'steps'}, \
            'local job scope drift'
        assert scalar(local, 'if') == LOCAL_IF, 'local event trust drift'
        assert scalar(local, 'runs-on') == '[self-hosted, macOS, ARM64, beans-mac]', \
            'local runner drift'
    if boundary in ('all', 'checkout'):
        checkout_boundary(hosted, {'persist-credentials': ('false', '')})
        checkout_boundary(local, {'ref': ('${{ github.sha }}', ''),
                                  'persist-credentials': ('false', '')})
        runner_precheck(steps(local))
    if boundary in ('all', 'execution'):
        execution_boundary(hosted, local)


def gate_contract(text):
    workflow = mapping(text, 0)
    assert {'name', 'on', 'jobs'} <= set(workflow) <= {'name', 'on', 'permissions', 'jobs'}, \
        'unexpected workflow field'
    assert scalar(workflow, 'name') == 'gate', 'workflow name is an API'
    assert scalar(workflow, 'on') == '[pull_request, push]', 'unauthorized gate event'
    read_ceiling(workflow)
    jobs = nested(workflow, 'jobs', 2)
    assert set(jobs) == {'compliance'}, 'gate check identity changed'
    job = nested(jobs, 'compliance', 4)
    assert set(job) == {'uses', 'with'}, 'unexpected reusable caller field'
    assert scalar(job, 'uses') == \
        'stevekkall-beansgc/gate-kit/.github/workflows/compliance.yml@v0.4.11', \
        'caller rollout requires separate review'
    assert nested(job, 'with', 6) == {'repo': ('qa-kit', ''), 'full': ('false', ''),
                                    'runner': (GATE_RUNNER, '')}, 'gate selection drift'


class GateCallerTests(unittest.TestCase):
    def test_pull_requests_use_hosted_runner(self):
        gate_contract((ROOT / '.github/workflows/gate.yml').read_text())

    def test_owned_workflow_read_ceiling(self):
        test_contract((ROOT / '.github/workflows/test.yml').read_text(), 'permissions')

    def test_owned_checkouts_keep_event_source_without_credentials(self):
        test_contract((ROOT / '.github/workflows/test.yml').read_text(), 'checkout')

    def test_owned_workflow_event_boundary(self):
        test_contract((ROOT / '.github/workflows/test.yml').read_text(), 'events')

    def test_owned_required_steps_fail_closed(self):
        test_contract((ROOT / '.github/workflows/test.yml').read_text(), 'execution')

    def test_skipped_or_suppressed_required_steps_are_rejected(self):
        source = (ROOT / '.github/workflows/test.yml').read_text()
        guard_name = '      - name: Verify the existing QA runner before checkout\n'
        local_name = '      - name: Run task validate on macOS ARM64 with Python 3.12\n'
        runner_guard = '          test "$RUNNER_NAME" = "beans-macbook-qa-kit"'
        head_guard = '          test "$(git rev-parse HEAD)" = "$GITHUB_SHA"'
        unit = '      - run: python3 -m unittest discover -s tests -v'
        stdlib = '      - run: python3 scripts/check_stdlib.py bin/'
        mutations = {
            'skipped runner guard': (guard_name, guard_name + '        if: false\n'),
            'ignored runner failure': (guard_name, guard_name + '        continue-on-error: true\n'),
            'neutralized runner guard': (runner_guard, runner_guard + ' || true'),
            'commented runner guard': (runner_guard, runner_guard.replace('test ', '# test ', 1)),
            'early successful guard exit': (runner_guard, '          exit 0\n' + runner_guard),
            'skipped local validation': (local_name, local_name + '        if: false\n'),
            'ignored local validation failure': (local_name, local_name + '        continue-on-error: true\n'),
            'neutralized HEAD assertion': (head_guard, head_guard + ' || true'),
            'commented HEAD assertion': (head_guard, head_guard.replace('test ', '# test ', 1)),
            'neutralized Task failure': ('          task validate', '          task validate || true'),
            'skipped hosted unit': (unit, unit + '\n        if: false'),
            'ignored hosted unit failure': (unit, unit + '\n        continue-on-error: true'),
            'neutralized hosted unit failure': (unit, unit + ' || true'),
            'skipped hosted stdlib': (stdlib, stdlib + '\n        if: false'),
            'ignored hosted stdlib failure': (stdlib, stdlib + '\n        continue-on-error: true'),
            'neutralized hosted stdlib failure': (stdlib, stdlib + ' || true'),
        }
        for label, (old, new) in mutations.items():
            with self.subTest(mutation=label):
                self.assertIn(old, source, 'mutation did not reach the actual step')
                with self.assertRaises((AssertionError, KeyError)):
                    test_contract(source.replace(old, new, 1))

    def test_negative_mutations_are_rejected(self):
        source = (ROOT / '.github/workflows/test.yml').read_text()
        mutations = {
            'missing ceiling': ('permissions:\n  contents: read\n', ''),
            'workflow write grant': ('permissions:\n  contents: read', 'permissions: write-all'),
            'job write grant': ('      contents: read', '      contents: write'),
            'extra permission': ('permissions:\n  contents: read',
                                 'permissions:\n  contents: read\n  issues: write'),
            'duplicate permission': ('permissions:\n  contents: read',
                                     'permissions:\n  contents: read\npermissions: write-all'),
            'credential retention': ('          persist-credentials: false',
                                     '          persist-credentials: true'),
            'missing credential control': ('          persist-credentials: false\n', ''),
            'local credential retention': ('ref: ${{ github.sha }}\n          persist-credentials: false',
                                           'ref: ${{ github.sha }}\n          persist-credentials: true'),
            'hosted PR head': ('          persist-credentials: false',
                               '          ref: ${{ github.event.pull_request.head.sha }}\n'
                               '          persist-credentials: false'),
            'local moving source': ('ref: ${{ github.sha }}', 'ref: main'),
            'untrusted event': ('  pull_request:', '  pull_request_target:'),
            'missing push guard': (LOCAL_IF, LOCAL_IF.replace("github.event_name == 'push' && ", '')),
            'missing repo guard': (LOCAL_IF, LOCAL_IF.split(' && ', 1)[1]),
            'missing branch guard': (LOCAL_IF, LOCAL_IF.rsplit(' && ', 1)[0]),
            'PR on local runner': ('runs-on: ubuntu-latest', 'runs-on: beans-mac'),
        }
        for label, (old, new) in mutations.items():
            with self.subTest(mutation=label):
                self.assertIn(old, source, 'mutation did not reach the actual workflow')
                with self.assertRaises((AssertionError, KeyError)):
                    test_contract(source.replace(old, new, 1))

    def test_negative_caller_mutations_are_rejected(self):
        source = (ROOT / '.github/workflows/gate.yml').read_text()
        mutations = {
            'missing ceiling': ('permissions:\n  contents: read\n', ''),
            'write grant': ('contents: read', 'contents: write'),
            'new event': ('[pull_request, push]', '[pull_request_target, push]'),
            'caller upgrade': ('@v0.4.11', '@v0.7.2'),
            'untrusted local selection': (GATE_RUNNER, "${{ 'beans-mac' }}"),
            'broader selection': ('full: false', 'full: true'),
        }
        for label, (old, new) in mutations.items():
            with self.subTest(mutation=label):
                self.assertIn(old, source, 'mutation did not reach the actual caller')
                with self.assertRaises((AssertionError, KeyError)):
                    gate_contract(source.replace(old, new, 1))


if __name__ == "__main__":
    unittest.main()
