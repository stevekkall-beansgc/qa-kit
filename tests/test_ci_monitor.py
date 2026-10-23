"""Offline, persisted multi-poll regressions for CI failure delivery."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import ci_monitor


def run(run_id, conclusion='', *, attempt=1, status=None):
    return {'databaseId': run_id, 'attempt': attempt,
            'status': status or ('completed' if conclusion else 'in_progress'),
            'conclusion': conclusion, 'workflowName': 'tests',
            'displayTitle': f'run {run_id}',
            'url': f'https://example.invalid/runs/{run_id}'}


class MonitorDelivery(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.state = self.root / 'state.json'
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps({'repos': [
            {'name': 'one', 'path': str(self.root)}]}))

    def poll(self, runs, *responses):
        output = io.StringIO()
        code = 0
        with mock.patch.object(ci_monitor, 'STATE', self.state), \
             mock.patch.object(ci_monitor, 'MANIFEST', self.manifest), \
             mock.patch.object(ci_monitor, 'repo_remote', return_value=('remote', 'url')), \
             mock.patch.object(ci_monitor, 'gh', side_effect=[
                 (0, ''), (0, json.dumps(runs)), *responses]) as gh, \
             contextlib.redirect_stdout(output):
            try:
                ci_monitor.main()
            except SystemExit as stopped:
                code = stopped.code
        return code, output.getvalue(), gh.call_args_list

    def test_older_run_finishing_after_newer_success_alerts_once(self):
        self.assertEqual(self.poll([run(11, 'success'), run(10)])[0], 0)
        finished = [run(11, 'success'), run(10, 'failure')]
        code, output, _ = self.poll(finished)
        self.assertEqual(code, 1)
        self.assertIn('NEW FAILURES (1)', output)
        self.assertIn('/runs/10', output)
        self.assertEqual(self.poll(finished)[0], 0)

    def test_each_failed_retry_alerts_once_even_without_observing_it_inflight(self):
        self.assertEqual(self.poll([run(10, 'failure')])[0], 1)
        self.assertEqual(self.poll([run(10, 'failure')])[0], 0)
        self.assertEqual(self.poll([run(10, 'failure', attempt=2)])[0], 1)
        self.assertEqual(self.poll([run(10, 'failure', attempt=2)])[0], 0)
        # A stale response must not rewind attempt state and re-alert later.
        self.assertEqual(self.poll([run(10, 'failure')])[0], 0)
        self.assertEqual(self.poll([run(10, 'failure', attempt=2)])[0], 0)

    def test_retry_inflight_then_failure_is_not_suppressed_by_previous_attempt(self):
        self.assertEqual(self.poll([run(10, 'success')])[0], 0)
        self.assertEqual(self.poll([run(10, attempt=2)])[0], 0)
        self.assertEqual(self.poll([run(10, 'failure', attempt=2)])[0], 1)
        self.assertEqual(self.poll([run(10, 'failure', attempt=2)])[0], 0)

    def test_pending_run_is_followed_after_leaving_recent_window(self):
        self.assertEqual(self.poll([run(11, 'success'), run(10)])[0], 0)
        code, output, calls = self.poll(
            [run(12, 'success')], (0, json.dumps(run(10, 'failure'))))
        self.assertEqual(code, 1)
        self.assertIn('/runs/10', output)
        self.assertEqual(calls[2].args[0][:3], ['run', 'view', '10'])
        self.assertEqual(self.poll([run(12, 'success')])[0], 0)

    def test_pending_lookup_failure_stays_unknown_and_is_retried(self):
        self.assertEqual(self.poll([run(10)])[0], 0)
        before = json.loads(self.state.read_text())
        code, output, _ = self.poll([run(12, 'success')], (1, 'unavailable'))
        self.assertEqual(code, 1)
        self.assertIn('MONITOR FAILURE', output)
        after = json.loads(self.state.read_text())
        self.assertEqual(after['repos']['one']['state'], 'unknown')
        self.assertEqual(after['repos']['one']['verified'], before['repos']['one']['verified'])
        self.assertEqual(after['verified'], before['verified'])
        code, output, _ = self.poll(
            [run(12, 'success')], (0, json.dumps(run(10, 'failure'))))
        self.assertEqual(code, 1)
        self.assertIn('/runs/10', output)

    def test_legacy_watermark_is_not_proof_that_an_older_failure_was_reported(self):
        self.state.write_text(json.dumps({'repos': {'one': {'last_run_id': 11}}}))
        runs = [run(11, 'success'), run(10, 'failure')]
        self.assertEqual(self.poll(runs)[0], 1)
        self.assertEqual(self.poll(runs)[0], 0)

    def test_other_repo_query_error_does_not_consume_an_unprinted_failure(self):
        self.manifest.write_text(json.dumps({'repos': [
            {'name': name, 'path': str(self.root)} for name in ('one', 'two')]}))
        code, output, _ = self.poll([run(10, 'failure')], (1, 'unavailable'))
        self.assertEqual(code, 1)
        self.assertIn('MONITOR FAILURE', output)
        self.assertIn('NEW FAILURES (1)', output)
        self.assertIn('/runs/10', output)

    def test_unavailable_attempt_cannot_claim_verified_coverage(self):
        for attempt in (None, 0, True, '2'):
            with self.subTest(attempt=attempt):
                code, output, _ = self.poll([run(10, 'failure', attempt=attempt)])
                self.assertEqual(code, 1)
                self.assertIn('MONITOR FAILURE', output)
                self.assertNotIn('NEW FAILURES', output)

    def test_wrong_pending_run_identity_does_not_clear_pending_failure(self):
        self.assertEqual(self.poll([run(10)])[0], 0)
        code, output, _ = self.poll(
            [run(12, 'success')], (0, json.dumps(run(99, 'success'))))
        self.assertEqual(code, 1)
        self.assertIn('MONITOR FAILURE', output)
        self.assertEqual(self.poll(
            [run(12, 'success')], (0, json.dumps(run(10, 'failure'))))[0], 1)


if __name__ == '__main__':
    unittest.main()
