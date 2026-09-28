"""Synthetic evidence: unavailable or scoped results must never become green."""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import health
import ci_monitor
import reconcile


class ReportingIntegrity(unittest.TestCase):
    def test_success_for_previous_main_commit_cannot_be_current_ci(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=Path(directory)/'manifest.json'
            manifest.write_text(json.dumps({'repos':[{'name':'one','path':directory}]}))
            runs=[{'conclusion':'success','status':'completed','headSha':'old','createdAt':'2026-09-28T12:00:00Z','url':'url'}]
            with mock.patch.object(health,'MANIFEST',manifest),mock.patch.object(health,'repo_remote',return_value=('remote','url')),mock.patch.object(health,'gh',side_effect=[runs,{'sha':'current'}]):
                self.assertIsNone(health.ci_rows()[0][3])

    def test_later_collision_failure_supersedes_base_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'logs').mkdir();manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'repos':[{'name':'one','path':directory,'unit':{'cmd':['true']}}]}))
            for suffix,ok in [('',True),('-1',False)]:
                (root/f'logs/run-20260928T000000Z{suffix}.json').write_text(json.dumps({'when':'20260928T000000Z','results':[{'repo':'one','kind':'unit','ok':ok}]}))
            with mock.patch.object(health,'HERE',root),mock.patch.object(health,'MANIFEST',manifest):
                result=health.qa_baseline()
            self.assertEqual(result['per_repo']['one']['verdict'],'FAIL')

    def test_malformed_provenance_is_unknown_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'logs').mkdir();manifest=root/'manifest.json';manifest.write_text('{"repos":[]}')
            (root/'logs/run-20260928T000000Z.json').write_text(json.dumps({'when':'20260928T000000Z','evidence':['malformed'],'results':[]}))
            with mock.patch.object(health,'HERE',root),mock.patch.object(health,'MANIFEST',manifest):
                result=health.qa_baseline()
            self.assertIsNone(result['fleet_candidate'])
            self.assertTrue(result['receipt_errors'])

    def test_monitor_inflight_failure_does_not_advance_completed_watermark(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state.json';manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'repos':[{'name':'one','path':directory}]}))
            inflight=[{'databaseId':9,'status':'in_progress','conclusion':'','url':'url'}]
            with mock.patch.object(ci_monitor,'STATE',state),mock.patch.object(ci_monitor,'MANIFEST',manifest),mock.patch.object(ci_monitor,'repo_remote',return_value=('remote','url')),mock.patch.object(ci_monitor,'gh',side_effect=[(0,''),(0,json.dumps(inflight))]),contextlib.redirect_stdout(io.StringIO()):
                ci_monitor.main()
            self.assertEqual(json.loads(state.read_text())['repos']['one']['last_run_id'],0)

    def test_receipt_records_exact_manifest_bytes_and_mutating_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);repo=root/'repo';repo.mkdir();logs=root/'logs'
            command=[sys.executable,'-c',"from pathlib import Path; Path('changed').write_text('fixture')"]
            (repo/'README.md').write_text('AGENTS.md\n')
            (repo/'AGENTS.md').write_text('## Test commands\n'+' '.join(command))
            subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture'],check=True,capture_output=True)
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'repos':[{'name':'one','path':str(repo),'status':'active','unit':{'cmd':command}}]},indent=4)+'\n')
            script=Path(__file__).resolve().parents[1]/'bin/run_all.py'
            result=subprocess.run([sys.executable,str(script),'--manifest',str(manifest),'--logs-dir',str(logs),'--only','one','--all'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(next(logs.glob('run-*.json')).read_text());evidence=data['evidence']
            self.assertEqual(evidence['manifest']['sha256'],hashlib.sha256(manifest.read_bytes()).hexdigest())
            self.assertFalse(evidence['repos']['one']['before']['dirty'])
            self.assertTrue(evidence['repos']['one']['after']['dirty'])
            self.assertEqual(evidence['selection']['repos'],['one'])
            self.assertNotIn('changed',json.dumps(evidence))

    def test_ci_failure_is_unknown_not_no_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory)/'manifest.json'
            manifest.write_text(json.dumps({'repos':[{'name':'fixture','path':directory}]}))
            with mock.patch.object(health,'MANIFEST',manifest), \
                 mock.patch.object(health,'repo_remote',return_value=('remote','https://github.com/o/r.git')), \
                 mock.patch.object(health,'gh',return_value=None):
                self.assertEqual(health.ci_rows()[0][1:],('unknown','',None))

    def test_empty_or_running_ci_is_not_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=Path(directory)/'manifest.json'
            manifest.write_text(json.dumps({'repos':[{'name':'fixture','path':directory}]}))
            with mock.patch.object(health,'MANIFEST',manifest), mock.patch.object(health,'repo_remote',return_value=('remote','url')):
                for response,state in [([], 'no runs'),([{'status':'in_progress','conclusion':'','url':'url'}],'in_progress')]:
                    with mock.patch.object(health,'gh',return_value=response):
                        row=health.ci_rows()[0]
                        self.assertEqual(row[1],state)
                        self.assertIsNone(row[3])

    def test_linked_worktree_remote_uses_git(self):
        from reporting import repo_remote
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);primary=root/'primary';linked=root/'linked'
            subprocess.run(['git','init',str(primary)],check=True,capture_output=True)
            subprocess.run(['git','-C',str(primary),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','fixture'],check=True,capture_output=True)
            subprocess.run(['git','-C',str(primary),'remote','add','origin','https://github.com/o/r.git'],check=True)
            subprocess.run(['git','-C',str(primary),'worktree','add',str(linked)],check=True,capture_output=True)
            self.assertEqual(repo_remote(linked),('remote','https://github.com/o/r.git'))
            rows=[{'name':'source','path':str(primary)}]
            problems,_=reconcile.registry_drift(rows,rows,{str(linked):'working-copy'})
            self.assertEqual(problems,[], 'a linked task checkout is not a new repository')

    def test_single_repo_pass_is_scoped_and_unrelated_failure_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'logs').mkdir()
            manifest=root/'manifest.json'; manifest.write_text(json.dumps({'repos':[{'name':n,'status':'active','path':directory,'unit':{'cmd':['true']}} for n in ['one','two']]}))
            (root/'logs/run-20260927T000000Z.json').write_text(json.dumps({'when':'20260927T000000Z','results':[{'repo':'two','kind':'unit','ok':False}]}))
            (root/'logs/run-20260928T000000Z.json').write_text(json.dumps({'when':'20260928T000000Z','results':[{'repo':'one','kind':'docs','ok':True},{'repo':'one','kind':'unit','ok':True}]}))
            with mock.patch.object(health,'HERE',root),mock.patch.object(health,'MANIFEST',manifest):
                result=health.qa_baseline()
            self.assertNotEqual(result['verdict'],'PASS')
            self.assertEqual(result['latest_run']['repos'],['one'])
            self.assertEqual(result['per_repo']['two']['verdict'],'FAIL')

    def test_never_run_html_renders_without_green(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); manifest=root/'manifest.json';manifest.write_text('{"repos":[]}')
            with mock.patch.object(health,'HERE',root),mock.patch.object(health,'MANIFEST',manifest):
                qa=health.qa_baseline()
            page=health.html({'generated':'fixture','services':[],'repos':[],'qa':qa,'monitors':{'attempted':'never','verified':'never','repos_watched':0,'repos_verified':0,'unknown':0}})
            self.assertIn('never-run',page)

    def test_monitor_auth_failure_preserves_verified_time_and_cleans_wrappers(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); state=root/'ci-state.json';manifest=root/'manifest.json'
            state.write_text(json.dumps({'checked':'old','repos':{'checked':'legacy','repos':{},'one':{'last_run_id':7}}}))
            manifest.write_text(json.dumps({'repos':[{'name':'one','path':directory}]}))
            with mock.patch.object(ci_monitor,'STATE',state),mock.patch.object(ci_monitor,'MANIFEST',manifest),mock.patch.object(ci_monitor,'gh',return_value=(1,'auth failed')),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as stopped:
                ci_monitor.main()
            self.assertEqual(stopped.exception.code,1)
            result=json.loads(state.read_text())
            self.assertEqual(set(result['repos']),{'one'})
            self.assertIsNone(result['verified'])
            self.assertEqual(result['repos']['one']['state'],'unknown')
            self.assertEqual(result['repos']['one']['last_run_id'],7)

    def test_monitor_malformed_query_remains_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state.json';manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'repos':[{'name':'one','path':directory}]}))
            with mock.patch.object(ci_monitor,'STATE',state),mock.patch.object(ci_monitor,'MANIFEST',manifest),mock.patch.object(ci_monitor,'repo_remote',return_value=('remote','url')),mock.patch.object(ci_monitor,'gh',side_effect=[(0,''),(0,'{"oops":1}')]),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as stopped:
                ci_monitor.main()
            self.assertEqual(stopped.exception.code,1)
            self.assertEqual(json.loads(state.read_text())['repos']['one']['state'],'unknown')

    def test_stuck_sync_cannot_inherit_last_exit_green(self):
        self.assertEqual(health.sync_status('state = running\npid = 42\nlast exit code = 0')[2],None)
        self.assertIn('last exit 0',health.sync_status('state = running\npid = 42\nlast exit code = 0')[1])

    def test_offsite_restore_failure_attributed_separately(self):
        rows=health.restore_status({'when':'2026-09-28T00:00:00Z','local':{'ok':True},'offsite':{'ok':False},'overall':False})
        self.assertTrue(rows[0][2])
        self.assertFalse(rows[1][2])

    def test_registry_requires_each_source_and_checks_agency_dead_paths(self):
        rows=[{'name':'one','path':'/one'}]
        problems,_=reconcile.registry_drift(rows,[{'name':'two','path':'/dead'}],{'/one':'one'},path_exists=lambda p:p=='/one')
        self.assertTrue(any('Agency' in p and 'one' in p for p in problems))
        self.assertTrue(any('/dead' in p for p in problems))

    def test_archived_disk_asset_does_not_acquire_test_obligations(self):
        problems,_=reconcile.registry_drift([],[],{'/beans/archive/old':'old'},path_exists=lambda p:True)
        self.assertFalse(problems)

    def test_unreadable_agency_registry_fails_closed_without_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'manifest.json';manifest.write_text('{"repos":[]}')
            with mock.patch.object(reconcile,'MANIFEST',manifest),mock.patch.object(reconcile,'BEANS',root),mock.patch.object(reconcile,'LEGACY',[]),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as stopped:
                reconcile.main()
            self.assertEqual(stopped.exception.code,1)
            self.assertEqual(manifest.read_text(),'{"repos":[]}')
