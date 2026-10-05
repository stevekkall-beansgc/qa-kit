"""Offline runtime checks; no collectors or service activation."""
import sys
import json
import unittest
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bin'))
import scorecard_evaluator as ev

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT/'scorecards/policy.candidate.json').read_text())
    def test_existing_nine_cases_execute_real_evaluator(self):
        cases=json.loads((ROOT/'scorecards/acceptance-cases.json').read_text())['health_cases']
        for c in cases:
            with self.subTest(c=c['id']):
                result=ev.health(self.policy, c['ratings'], c['complete'], c['blockers'])
                self.assertEqual({k:result[k] for k in ('points','coverage','status')}, c['expected'])
    def test_bad_ratings_refused(self):
        for value in (True, 1.5, -1, 5, '4'):
            with self.assertRaises(ValueError): ev.health(self.policy,[value,4,4,4],[True]*4,[])
    def test_missing_rating_cannot_be_complete(self):
        with self.assertRaises(ValueError): ev.health(self.policy,[None,4,4,4],[True]*4,[])
    def test_incomplete_rating_cannot_earn_credit(self):
        with self.assertRaises(ValueError): ev.health(self.policy,[4]*4,[False,True,True,True],[])
    def test_unknown_blocker_refused(self):
        with self.assertRaises(ValueError): ev.health(self.policy,[4]*4,[True]*4,['typo'])
    def test_policy_unchanged(self):
        before=json.dumps(self.policy,sort_keys=True)
        ev.health(self.policy,[4]*4,[True]*4,[])
        self.assertEqual(before,json.dumps(self.policy,sort_keys=True))
    def test_boolean_complete_required(self):
        with self.assertRaises(ValueError): ev.health(self.policy,[4]*4,[1]*4,[])
    def test_exact_quarter_points(self):
        self.assertEqual(ev.health(self.policy,[3,3,3,4],[True]*4,[])['points'],78.75)
    def scan(self, **changes):
        s=dict(producer='zizmor',version='1.28.0',commit='a'*40,scope='workflows',observed_at='2026-10-05T11:00:00Z',result='completed',evidence_ref='scan-1',findings=[])
        s.update(changes); return s
    def sec(self, scans, findings=None, blockers=None):
        return ev.security(self.policy, required=['zizmor'],scans=scans,findings=findings or [],blockers=blockers or [],commit='a'*40,scope='workflows',now=NOW,max_age_seconds=86400)
    def test_empty_security_unknown(self): self.assertEqual(self.sec([])['status'],'unknown')
    def test_complete_scan_green(self): self.assertEqual(self.sec([self.scan()])['status'],'green')
    def test_failed_scan_unknown(self): self.assertEqual(self.sec([self.scan(result='error')])['status'],'unknown')
    def test_report_only_success_does_not_hide_finding(self):
        self.assertEqual(self.sec([self.scan(findings=['finding-1'])])['status'],'amber')
    def test_missing_with_finding_amber_incomplete(self):
        r=self.sec([],findings=['finding-1']);self.assertEqual(r['status'],'amber');self.assertFalse(r['coverage_complete'])
    def test_critical_blocker_red_despite_missing(self):
        self.assertEqual(self.sec([],blockers=['confirmed_exposed_credential'])['status'],'red')
    def test_stale_future_wrong_commit_scope_missing_version_unknown(self):
        for change in ({'observed_at':'2026-10-03T11:00:00Z'},{'observed_at':'2026-10-06T11:00:00Z'},{'commit':'b'*40},{'scope':'other'},{'version':''},{'evidence_ref':''}):
            with self.subTest(change=change): self.assertEqual(self.sec([self.scan(**change)])['status'],'unknown')
    def test_duplicate_producer_rejected_not_cherry_picked(self):
        with self.assertRaises(ValueError):self.sec([self.scan(),self.scan(result='error')])
    def test_no_required_scope_not_green(self):
        with self.assertRaises(ValueError): ev.security(self.policy,required=[],scans=[],findings=[],blockers=[],commit='a'*40,scope='workflows',now=NOW,max_age_seconds=86400)
    def test_no_implicit_freshness_policy(self):
        with self.assertRaises(ValueError): ev.security(self.policy,required=['zizmor'],scans=[],findings=[],blockers=[],commit='a'*40,scope='workflows',now=NOW,max_age_seconds=None)
    def test_stale_findings_remain_visible(self):
        self.assertEqual(self.sec([self.scan(observed_at='2026-10-03T11:00:00Z',findings=['f'])])['status'],'amber')
    def test_security_does_not_fabricate_native_score(self):
        self.assertIsNone(self.sec([self.scan()])['openssf_score'])
if __name__=='__main__':unittest.main()
