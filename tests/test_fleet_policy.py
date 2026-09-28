"""A whole-fleet PASS requires the agreed scope and fresh current evidence."""
import copy
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from fleet_policy import evaluate


class FleetPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,28,16,tzinfo=timezone.utc)
        self.policy={'mode':'sweep-and-current','max_age_hours':24}
        self.qa={'fleet_candidate':{'when':'20260928T120000Z'},'receipt_errors':[],
                 'per_repo':{'one':{'verdict':'PASS','current_complete':True,'when':'20260928T120000Z'}}}
        self.ci={'one':{'state':'success','ok':True,'head_verified':True,'coverage_verified':True,
                        'when':'2026-09-28T12:00:00Z','queried_at':'2026-09-28T16:00:00Z'}}

    def test_unanswered_or_invalid_policy_cannot_go_green(self):
        for policy in [None,{}, {'mode':'sweep-and-current','max_age_hours':True}]:
            self.assertEqual(evaluate(self.qa,self.ci,policy,self.now)['verdict'],'UNVERIFIED')

    def test_complete_fresh_current_evidence_can_pass_under_explicit_policy(self):
        self.assertEqual(evaluate(self.qa,self.ci,self.policy,self.now)['verdict'],'PASS')

    def test_scoped_pass_cannot_replace_missing_fleet_sweep(self):
        self.qa['fleet_candidate']=None
        self.assertEqual(evaluate(self.qa,self.ci,self.policy,self.now)['verdict'],'UNVERIFIED')

    def test_evidence_just_over_24_hours_cannot_pass(self):
        self.qa['fleet_candidate']['when']='20260927T155959Z'
        self.assertEqual(evaluate(self.qa,self.ci,self.policy,self.now)['verdict'],'UNVERIFIED')

    def test_stale_sweep_and_newer_unrelated_failure_cannot_go_green(self):
        for mutate in [lambda:self.qa['fleet_candidate'].update(when='20260926T120000Z'),
                       lambda:self.qa['per_repo'].update(two={'verdict':'FAIL','when':'20260928T150000Z'})]:
            mutate()
            self.assertEqual(evaluate(self.qa,self.ci,self.policy,self.now)['verdict'],'UNVERIFIED')

    def test_missing_auth_failed_or_wrong_commit_ci_is_unknown(self):
        for value in [{}, {'state':'unknown'}, dict(self.ci['one'],head_verified=False),
                      dict(self.ci['one'],coverage_verified=False),
                      dict(self.ci['one'],when='2026-09-26T12:00:00Z')]:
            self.assertEqual(evaluate(self.qa,{'one':value},self.policy,self.now)['verdict'],'UNVERIFIED')

    def test_dirty_partial_future_or_malformed_qa_cannot_go_green(self):
        for key,value in [('current_complete',False),('when','20260929T120000Z')]:
            qa=copy.deepcopy(self.qa);qa['per_repo']['one'][key]=value
            self.assertEqual(evaluate(qa,self.ci,self.policy,self.now)['verdict'],'UNVERIFIED')
        self.qa['receipt_errors']=['broken.json']
        self.assertEqual(evaluate(self.qa,self.ci,self.policy,self.now)['verdict'],'UNVERIFIED')
