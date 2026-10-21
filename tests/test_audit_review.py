"""Twelve bookmark acceptance cases, using synthetic receipts and supplied evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import audit_review as audit


class AuditReviewTests(unittest.TestCase):
    def setUp(self):
        self.ref = 'sha256:' + 'a' * 64
        identity = {'head': 'a' * 40, 'tracked_sha256': 'b' * 64,
                    'dirty': False, 'matches_head': True}
        self.target = {'repository': 'synthetic/product', 'commit': 'a' * 40,
                       'tracked_sha256': 'b' * 64, 'source_blobs': {'app.py': 'c' * 40},
                       'dependencies': {'fixture': identity}, 'controls': {'qa': identity},
                       'selection': 'ci-required'}
        self.expected = {'target': copy.deepcopy(self.target), 'required_cells': ['unit@host'],
                         'required_scope': ['native-capture']}
        self.receipt = {'schema': 'qa-kit.validation-result/v1', 'github_repository': 'synthetic/product',
                        'candidate': {'before': identity, 'after': identity},
                        'fixtures': {'fixture': {'before': identity, 'after': identity}},
                        'controls': {'qa': identity}, 'variant': 'host', 'selection': 'ci-required',
                        'required': ['unit@host'], 'selected': ['unit@host'], 'status': 'pass',
                        'errors': [], 'tasks': [{'task': 'unit', 'variant': 'host', 'status': 'pass',
                                                'exit_code': 0, 'timed_out': False}]}
        self.record = {'schema': audit.SCHEMA, 'target': copy.deepcopy(self.target), 'receipts': [],
                       'scope': [{'id': 'native-capture', 'status': 'inspected',
                                  'evidence': self.ref, 'reason': 'synthetic inspection'}],
                       'findings': [], 'known_findings': [], 'exceptions': [],
                       'review': {'author': 'author', 'reviewer': 'reviewer', 'independence_evidence': self.ref}}
        self.verification = {'reproductions': {}, 'independence': {}, 'remediations': {}}

    def run_review(self, corroborate=True):
        ref = audit.digest(self.receipt)
        self.record['receipts'] = [ref]
        if corroborate:
            self.verification['independence'][self.ref] = {
                'author': 'author', 'reviewer': 'reviewer', 'record': audit.digest(self.record), 'independent': True}
        return audit.review(self.record, self.expected, {ref: self.receipt}, self.verification)

    def finding(self, status='confirmed'):
        f = {'id': 'F1', 'status': status, 'evidence': [self.ref],
             'counterevidence': [], 'reproduction': self.ref}
        self.record['findings'] = [f]
        return f

    def test_c01_missing_required_variant(self):
        self.expected['required_cells'].append('unit@phone')
        self.receipt['required'].append('unit@phone')
        r = self.run_review()
        self.assertEqual(r['remaining_cells'], ['unit@phone'])
        self.assertIn('required_cells_missing', r['problems'])

    def test_c02_passing_tests_do_not_inspect_native_journey(self):
        self.record['scope'][0]['status'] = 'unavailable'
        r = self.run_review()
        self.assertEqual(r['covered_cells'], ['unit@host'])
        self.assertIn('required_scope_not_inspected', r['problems'])

    def test_c03_schema_valid_claim_is_not_verification(self):
        self.finding()
        self.assertEqual(self.run_review()['findings'][0]['status'], 'unverified')

    def test_c04_different_reviewer_id_does_not_prove_independence(self):
        self.assertEqual(self.run_review(False)['independence'], 'unverified')
        self.verification['independence'][self.ref] = {'independent': True}
        self.assertEqual(self.run_review(False)['independence'], 'unverified')

    def test_c05_rejected_hypothesis_and_counterevidence_retained(self):
        f = self.finding('rejected'); f['counterevidence'] = [self.ref]
        r = self.run_review()['findings'][0]
        self.assertEqual(r['status'], 'rejected')
        self.assertEqual(r['counterevidence'], [self.ref])
        self.assertEqual(self.record['findings'], [f])

    def test_c06_absence_in_narrower_scan_is_not_clearance(self):
        self.record['known_findings'] = ['F1']
        r = self.run_review()
        self.assertEqual(r['unresolved_known_findings'], ['F1'])
        self.assertIn('known_finding_absent_scope_review', r['problems'])

    def test_c07_exception_is_not_remediation(self):
        self.record['known_findings'] = ['F1']
        self.record['exceptions'] = [{'finding': 'F1', 'decision': 'accepted', 'evidence': self.ref}]
        self.assertEqual(self.run_review()['unresolved_known_findings'], ['F1'])
        self.verification['remediations']['F1'] = {'target': self.target, 'verified': True}
        self.assertEqual(self.run_review()['unresolved_known_findings'], ['F1'])
        self.verification['remediations']['F1'] = {'target': self.target, 'finding': 'F1',
            'outcome': 'remediated', 'fix_evidence': self.ref, 'verification_evidence': self.ref,
            'qualified_reviewer': True}
        self.assertEqual(self.run_review()['unresolved_known_findings'], [])

    def test_c08_same_commit_in_wrong_repository(self):
        self.receipt['github_repository'] = 'synthetic/foreign'
        r = self.run_review()
        self.assertEqual(r['covered_cells'], [])
        self.assertIn('receipt_attribution_mismatch', r['problems'])

    def test_c09_changed_source_blob_and_dependency_do_not_carry_forward(self):
        for key, value in [('source_blobs', {'app.py': 'd' * 40}), ('dependencies', {'other': self.target['dependencies']['fixture']})]:
            with self.subTest(key=key):
                self.record['target'] = {**self.target, key: value}
                self.assertEqual(self.run_review()['covered_cells'], [])
        self.record['target'] = copy.deepcopy(self.target)
        self.receipt['fixtures']['fixture']['after'] = {**self.target['dependencies']['fixture'], 'head': 'e' * 40}
        self.assertEqual(self.run_review()['covered_cells'], [])

    def test_c10_setup_failure_preserves_blocked_dependents(self):
        self.receipt['status'] = 'fail'
        self.receipt['tasks'] = [{'task': 'setup', 'variant': 'host', 'status': 'fail', 'exit_code': 7},
                                 {'task': 'unit', 'variant': 'host', 'status': 'blocked', 'exit_code': None}]
        r = self.run_review()
        self.assertEqual([x['status'] for x in r['tasks']], ['fail', 'blocked'])
        self.assertEqual(r['covered_cells'], [])

    def test_c11_report_only_zero_exit_does_not_clear_findings_or_errors(self):
        self.finding(); self.receipt['errors'] = ['collection incomplete']
        r = self.run_review()
        self.assertIn('execution_failed_or_incomplete', r['problems'])
        self.assertEqual(len(r['findings']), 1)
        self.assertFalse(r['acceptance_granted'])

    def test_c12_private_and_executable_references_are_held_and_never_rendered(self):
        for ref in ['/Users/private/raw-transcript.txt', 'javascript:alert(1)', 'https://evil.invalid/run.sh']:
            self.record['scope'][0]['evidence'] = ref
            self.finding()['evidence'] = [ref]
            r = self.run_review()
            self.assertEqual(r['public_rendering'], 'hold')
            self.assertNotIn(ref, json.dumps(r))
            self.assertEqual(r['findings'][0]['status'], 'unverified')

    def test_corroboration_binds_exact_claim_and_record(self):
        f = self.finding()
        self.verification['reproductions'][self.ref] = {'target': self.target,
             'finding': audit.digest({k: v for k, v in f.items() if k != 'reproduction'}), 'outcome': 'confirmed'}
        self.assertEqual(self.run_review()['findings'][0]['status'], 'confirmed')
        f['counterevidence'] = ['sha256:' + 'f' * 64]
        self.assertEqual(self.run_review()['findings'][0]['status'], 'unverified')
        self.record['findings'] = []
        self.assertEqual(self.run_review()['problems'], [])

    def test_digest_changed_missing_receipt_and_duplicate_cells(self):
        self.record['receipts'] = [self.ref]
        r = audit.review(self.record, self.expected, {}, self.verification)
        self.assertIn('receipt_unavailable_or_changed', r['problems'])
        self.receipt['tasks'] *= 2
        with self.assertRaises(ValueError): self.run_review()

    def test_malformed_target_identity_refuses(self):
        self.expected['target']['commit'] = 'mutable-main'
        with self.assertRaises(ValueError): self.run_review()

    def test_cli_rejects_duplicate_keys_without_disclosing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'; path.write_text('{"secret":"private", "secret":1}')
            cmd = [sys.executable, audit.__file__]
            for key in ('record', 'expected', 'receipts', 'verification'): cmd += ['--' + key, str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('private', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
