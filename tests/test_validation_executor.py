"""Synthetic, offline qualification of the shared execution boundary."""
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import validation


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


def commit(root):
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
    return git(root, 'rev-parse', 'HEAD')


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / 'product'; self.root.mkdir()
        self.qa = self.base / 'qa'; self.qa.mkdir()
        for root in (self.root, self.qa):
            git(root, 'init', '-q')
        (self.qa / 'source').write_text('synthetic control')
        (self.qa/'.gitignore').write_text('__pycache__/\n')
        (self.qa/'bin').mkdir()
        shutil.copy2(Path(validation.__file__),self.qa/'bin/validation.py')
        self.qa_head = commit(self.qa)
        (self.root / '.gitignore').write_text('scratch/\n')
        (self.root / 'check.py').write_text("import os, pathlib\np=pathlib.Path('scratch'); p.mkdir(exist_ok=True)\n(p/'ran').write_text(os.environ.get('MODE','')+'|'+os.environ.get('INPUT',''))\n")
        (self.root / 'prep.py').write_text('pass\n')
        self.contract = {'schema':'qa-kit.validation-contract/v1',
            'variants':{'host':{'os':platform.system().lower(), 'arch':platform.machine(),
                        'runtimes':{'python':f'{sys.version_info.major}.{sys.version_info.minor}'}}},
            'tasks':{'setup':{'argv':[sys.executable,'prep.py'],'cwd':'.','after':[],
                              'variants':['host'],'effects':[], 'fixtures':[], 'env':{}, 'timeout_seconds':5},
                     'unit':{'argv':[sys.executable,'check.py'],'cwd':'.','after':['setup'],
                             'variants':['host'],'effects':['repo-write'],'fixtures':[],
                             'env':{'MODE':{'literal':'offline'},'INPUT':{'repo_path':'check.py'}},
                             'timeout_seconds':5}},
            'selections':{'routine':['unit@host']}}
        self.registry = {'schema':'qa-kit.validation-registry/v1','repos':{'sample':{
            'contract':'validation.json','contract_sha256':'','selections':{'routine':['unit@host']},
            'github_repository':'synthetic/sample','required_selections':{'ci':'routine','release':'routine'}}}}
        self.authorization = {'schema':'qa-kit.validation-authorization/v1',
            'contexts':['local'],'variants':['host'],'effects':['repo-write']}
        self.bundle = {'schema':'qa-kit.validation-bundle/v1','protocol':'1.0',
            'qa_commit':self.qa_head,'registry_sha256':'','authorization_sha256':'',
            'adapters':{},'fixtures':{}}
        self.sync()

    def sync(self):
        self.registry['repos']['sample']['contract_sha256']=write_json(self.root/'validation.json',self.contract)
        self.bundle['registry_sha256']=write_json(self.base/'registry.json',self.registry)
        self.bundle['authorization_sha256']=write_json(self.base/'authorization.json',self.authorization)
        write_json(self.base/'bundle.json',self.bundle)
        if git(self.root,'status','--porcelain'):
            self.head=commit(self.root)

    def run_it(self, **overrides):
        args=dict(root=self.root,repo='sample',registry_path=self.base/'registry.json',
                  bundle_path=self.base/'bundle.json',selection='routine',variant='host',
                  expected_head=self.head,context='local',authorization_path=self.base/'authorization.json',
                  qa_root=self.qa)
        args.update(overrides)
        return validation.run_validation(**args)

    def test_success_and_typed_environment(self):
        r=self.run_it()
        self.assertEqual(r['status'],'pass',r)
        self.assertEqual((self.root/'scratch/ran').read_text(),'offline|'+str(self.root/'check.py'))
        self.assertEqual([t['task'] for t in r['tasks']],['setup','unit'])
        self.assertEqual(r['candidate']['before']['head'],self.head)
        for key in ('contract_sha256','registry_sha256','bundle_sha256','plan_sha256','authorization_sha256'):
            self.assertEqual(len(r[key]),64)

    def test_setup_failure_blocks_dependent(self):
        (self.root/'prep.py').write_text('raise SystemExit(7)\n'); self.sync()
        r=self.run_it()
        self.assertEqual(r['status'],'fail')
        self.assertEqual(r['tasks'][0]['exit_code'],7)
        self.assertEqual(r['tasks'][1]['status'],'blocked')
        self.assertFalse((self.root/'scratch/ran').exists())

    def test_runtime_mismatch_blocks_before_setup(self):
        self.contract['variants']['host']['runtimes']['python']='0.0'; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')
        self.assertFalse((self.root/'scratch/ran').exists())

    def test_platform_mismatch(self):
        self.contract['variants']['host']['os']='not-this-os'; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_wrong_candidate(self):
        self.assertEqual(self.run_it(expected_head='0'*40)['status'],'blocked')

    def test_dirty_source(self):
        (self.root/'prep.py').write_text('raise SystemExit(0)\n')
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_source_drift_after_task(self):
        (self.root/'check.py').write_text("from pathlib import Path\nPath('prep.py').write_text('changed')\n")
        self.sync()
        r=self.run_it(); self.assertEqual(r['status'],'fail')
        self.assertTrue(r['candidate']['after']['dirty'])

    def test_missing_fixture(self):
        self.contract['tasks']['unit']['fixtures']=['database']; self.bundle['fixtures']['database']='a'*40; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')
        self.assertFalse((self.root/'scratch/ran').exists())

    def test_timeout(self):
        (self.root/'prep.py').write_text('import time\ntime.sleep(5)\n')
        self.contract['tasks']['setup']['timeout_seconds']=0.1; self.sync()
        r=self.run_it(); self.assertEqual(r['status'],'fail')
        self.assertTrue(r['tasks'][0]['timed_out'])
        self.assertEqual(r['tasks'][1]['status'],'blocked')

    def test_incompatible_bundle(self):
        self.bundle['protocol']='99'; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_unknown_effect_cannot_self_authorize(self):
        self.contract['tasks']['unit']['effects']=['private-knowledge']; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_bad_env_type(self):
        self.contract['tasks']['unit']['env']['MODE']='offline'; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_env_path_traversal(self):
        self.contract['tasks']['unit']['env']['INPUT']={'repo_path':'../'}; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_contract_drift(self):
        self.registry['repos']['sample']['contract_sha256']='0'*64; write_json(self.base/'registry.json',self.registry)
        self.bundle['registry_sha256']=hashlib.sha256((self.base/'registry.json').read_bytes()).hexdigest()
        write_json(self.base/'bundle.json',self.bundle)
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_selection_cannot_reduce_central_requirement(self):
        self.contract['selections']['routine']=['setup@host']; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_cycle_blocks(self):
        self.contract['tasks']['setup']['after']=['unit']; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_unknown_variant(self):
        self.assertEqual(self.run_it(variant='missing')['status'],'blocked')

    def test_empty_selection(self):
        self.contract['selections']['routine']=[]; self.registry['repos']['sample']['selections']['routine']=[]; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_multivariant_pass_is_partial(self):
        self.contract['variants']['second']=self.contract['variants']['host'].copy()
        for task in self.contract['tasks'].values(): task['variants'].append('second')
        for obj in (self.contract,self.registry['repos']['sample']): obj['selections']['routine'].append('unit@second')
        self.sync(); r=self.run_it()
        self.assertEqual(r['status'],'pass',r)
        self.assertFalse(r['selection_complete'])
        self.assertEqual(r['remaining_required'],['unit@second'])

    def test_unknown_schema_field(self):
        self.contract['tasks']['unit']['ignore_failure']=True; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_ambient_credentials_not_inherited(self):
        from unittest.mock import patch
        (self.root/'check.py').write_text("import os\nassert 'SYNTHETIC_SECRET' not in os.environ\nassert 'PYTHONPATH' not in os.environ\n")
        self.sync()
        with patch.dict(os.environ,{'SYNTHETIC_SECRET':'not-a-real-secret','PYTHONPATH':'/nonexistent'}):
            self.assertEqual(self.run_it()['status'],'pass')

    def test_path_override_rejected(self):
        self.contract['tasks']['unit']['env']['PATH']={'literal':'/other'}; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_unobserved_absolute_interpreter_rejected(self):
        self.contract['tasks']['unit']['argv'][0]='/unqualified/python3'; self.sync()
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_fixture_success_then_drift_blocks(self):
        fixture=self.base/'fixture'; fixture.mkdir(); git(fixture,'init','-q')
        (fixture/'input').write_text('synthetic'); fixture_head=commit(fixture)
        self.contract['tasks']['unit']['fixtures']=['data']
        self.contract['tasks']['unit']['env']['INPUT']={'fixture_path':{'name':'data','path':'input'}}
        self.bundle['fixtures']['data']=fixture_head
        self.sync(); r=self.run_it(fixtures={'data':fixture}); self.assertEqual(r['status'],'pass',r)
        (self.root/'check.py').write_text("import os,pathlib\npathlib.Path(os.environ['INPUT']).write_text('changed')\n")
        self.sync(); r=self.run_it(fixtures={'data':fixture}); self.assertEqual(r['status'],'fail',r)

    def test_timeout_kills_descendant(self):
        (self.root/'prep.py').write_text("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',\"import time,pathlib;time.sleep(1);pathlib.Path('scratch/orphan').write_text('bad')\"])\ntime.sleep(5)\n")
        (self.root/'scratch').mkdir()
        self.contract['tasks']['setup']['timeout_seconds']=0.1; self.sync()
        r=self.run_it(); self.assertTrue(r['tasks'][0]['timed_out'])
        import time; time.sleep(1.2)
        self.assertFalse((self.root/'scratch/orphan').exists())

    def test_ci_needs_pinned_adapter_and_bundle(self):
        self.authorization['contexts'].append('ci'); self.sync()
        self.assertEqual(self.run_it(context='ci')['status'],'blocked')
        self.bundle['adapters']['ci']=self.qa_head; self.sync()
        r=self.run_it(context='ci',adapter_root=self.qa,
                      expected_bundle=hashlib.sha256((self.base/'bundle.json').read_bytes()).hexdigest())
        self.assertEqual(r['status'],'pass',r)

    def test_duplicate_json_key(self):
        path=self.base/'authorization.json'
        path.write_text('{"schema":"qa-kit.validation-authorization/v1","contexts":[],"contexts":["local"]}')
        self.bundle['authorization_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        write_json(self.base/'bundle.json',self.bundle)
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_hidden_candidate_edit_is_rejected(self):
        git(self.root,'update-index','--assume-unchanged','prep.py')
        (self.root/'prep.py').write_text('raise SystemExit(9)\n')
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_hidden_control_edit_is_rejected(self):
        git(self.qa,'update-index','--skip-worktree','source')
        (self.qa/'source').write_text('changed')
        self.assertEqual(self.run_it()['status'],'blocked')

    def test_shell_python_uses_declared_runtime_binding(self):
        (self.root/'runner.sh').write_text('python3 check.py\n')
        bash=subprocess.check_output(['/bin/bash','--version']).decode()
        import re
        self.contract['variants']['host']['runtimes']['bash']=re.search(r'version (\d+)',bash).group(1)
        self.contract['tasks']['unit']['argv']=['bash','runner.sh']
        poison=self.base/'poison'; poison.mkdir()
        fake=poison/'python3'; fake.write_text('#!/bin/sh\nexit 99\n'); fake.chmod(0o755)
        # Observe /bin/bash, while an ambient python3 is deliberately wrong.
        self.sync()
        from unittest.mock import patch
        with patch.dict(os.environ,{'PATH':str(poison)+':/usr/bin:/bin'}):
            r=self.run_it()
        self.assertEqual(r['status'],'pass',r)

    def cli(self):
        return [sys.executable,'-I',str(self.qa/'bin/validation.py'),
            '--root',str(self.root),'--repo','sample','--registry',str(self.base/'registry.json'),
            '--bundle',str(self.base/'bundle.json'),'--authorization',str(self.base/'authorization.json'),
            '--expected-head',self.head,'--selection','routine','--variant','host','--context','local',
            '--expected-bundle',hashlib.sha256((self.base/'bundle.json').read_bytes()).hexdigest(),
            '--output',str(self.base/'result.json')]

    def test_real_cli_checks_its_own_source(self):
        p=subprocess.run(self.cli(),capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        receipt=json.loads((self.base/'result.json').read_text())
        self.assertEqual(receipt['controls']['qa']['head'],self.qa_head)
        self.assertTrue(receipt['selection_complete'])

    def test_context_does_not_change_task_environment(self):
        self.authorization['contexts'].append('ci'); self.bundle['adapters']['ci']=self.qa_head
        (self.root/'check.py').write_text("import os,pathlib\np=pathlib.Path('scratch');p.mkdir(exist_ok=True);(p/'ran').write_text(os.environ.get('CI','absent'))\n")
        self.sync(); local=self.run_it(); self.assertEqual(local['status'],'pass')
        local_value=(self.root/'scratch/ran').read_text()
        ci=self.run_it(context='ci',adapter_root=self.qa,
            expected_bundle=hashlib.sha256((self.base/'bundle.json').read_bytes()).hexdigest())
        self.assertEqual(ci['status'],'pass')
        self.assertEqual((self.root/'scratch/ran').read_text(),local_value)

    def test_tracked_qa_helper_argument(self):
        (self.qa/'bin/helper.py').write_text('print("central helper")\n')
        self.bundle['qa_commit']=commit(self.qa)
        self.contract['tasks']['unit']['argv']=[sys.executable,{'qa_path':'bin/helper.py'}]
        self.sync(); r=self.run_it(); self.assertEqual(r['status'],'pass',r)

    def test_untracked_qa_helper_cannot_run(self):
        (self.qa/'.gitignore').write_text('__pycache__/\nbin/untracked.py\n')
        self.bundle['qa_commit']=commit(self.qa)
        (self.qa/'bin/untracked.py').write_text('raise SystemExit(0)\n')
        self.contract['tasks']['unit']['argv']=[sys.executable,{'qa_path':'bin/untracked.py'}]
        self.sync(); r=self.run_it(); self.assertEqual(r['status'],'blocked',r)

    def test_central_docs_cli_uses_named_repo_and_candidate_root(self):
        helper=Path(validation.__file__).parent/'check_docs.py'
        manifest={'repos':[{'name':'sample','path':'/nonexistent','status':'active',
                           'unit':{'cmd':['python3','check.py']}}]}
        write_json(self.base/'docs-manifest.json',manifest)
        (self.root/'README.md').write_text('AGENTS.md')
        (self.root/'AGENTS.md').write_text('## Test commands\npython3 check.py\n')
        args=[sys.executable,str(helper),'--repo','sample','--root',str(self.root),
              '--manifest',str(self.base/'docs-manifest.json')]
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        (self.root/'AGENTS.md').write_text('## Test commands\npython3 wrong.py\n')
        self.assertEqual(subprocess.run(args,capture_output=True).returncode,1)
        args[args.index('sample')]='missing'
        self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)

    def test_real_cli_cancellation_stops_group(self):
        import time
        (self.root/'scratch').mkdir()
        (self.root/'prep.py').write_text("import subprocess,sys,time,pathlib\nsubprocess.Popen([sys.executable,'-c',\"import time,pathlib;time.sleep(1);pathlib.Path('scratch/orphan').write_text('bad')\"])\npathlib.Path('scratch/ready').write_text('ready')\ntime.sleep(20)\n")
        self.contract['tasks']['setup']['timeout_seconds']=30; self.sync()
        process=subprocess.Popen(self.cli(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+10
            while not (self.root/'scratch/ready').exists() and time.monotonic()<deadline:
                time.sleep(.02)
            self.assertTrue((self.root/'scratch/ready').exists())
            process.terminate(); process.communicate(timeout=10)
            self.assertEqual(process.returncode,1)
            receipt=json.loads((self.base/'result.json').read_text())
            self.assertTrue(receipt['tasks'][0]['cancelled'])
            self.assertEqual(receipt['tasks'][1]['status'],'blocked')
            time.sleep(1.2)
            self.assertFalse((self.root/'scratch/orphan').exists())
        finally:
            if process.poll() is None: process.kill(); process.communicate()

    def test_run_all_enrolled_uses_shared_executor_only(self):
        for name in ('run_all.py','reporting.py','check_validation.py'):
            shutil.copy2(Path(validation.__file__).parent/name,self.qa/'bin'/name)
        self.bundle['qa_commit']=commit(self.qa)
        (self.root/'README.md').write_text('See AGENTS.md')
        (self.root/'AGENTS.md').write_text('## Test commands\npython3 legacy.py\n')
        (self.root/'legacy.py').write_text('raise SystemExit(99)\n')
        self.sync()
        manifest={'repos':[{'name':'sample','path':str(self.root),'status':'active',
            'unit':{'cmd':['python3','legacy.py']},'validation':{'schema':'qa-kit.validation-enrollment/v1'}}]}
        write_json(self.base/'manifest.json',manifest)
        command=[sys.executable,str(self.qa/'bin/run_all.py'),'--manifest',str(self.base/'manifest.json'),
            '--logs-dir',str(self.base/'logs'),'--only','sample','--all',
            '--validation-registry',str(self.base/'registry.json'),'--validation-bundle',str(self.base/'bundle.json'),
            '--validation-authorization',str(self.base/'authorization.json'),'--validation-selection','routine',
            '--validation-variant','host','--validation-expected-bundle',hashlib.sha256((self.base/'bundle.json').read_bytes()).hexdigest()]
        p=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        report=json.loads(next((self.base/'logs').glob('*.json')).read_text())
        self.assertEqual([r['kind'] for r in report['results']],['docs','validation'])
        self.assertTrue(report['results'][1]['validation']['selection_complete'])

    def test_run_all_empty_enrollment_never_uses_legacy(self):
        self.registry['repos']['sample']={}
        write_json(self.base/'registry.json',self.registry)
        manifest={'repos':[{'name':'sample','path':str(self.root),'status':'active',
            'unit':{'cmd':[sys.executable,'check.py']}}]}
        write_json(self.base/'manifest.json',manifest)
        p=subprocess.run([sys.executable,str(Path(validation.__file__).parent/'run_all.py'),
            '--manifest',str(self.base/'manifest.json'),'--logs-dir',str(self.base/'logs'),
            '--validation-registry',str(self.base/'registry.json')],capture_output=True,text=True)
        self.assertEqual(p.returncode,1,p.stdout+p.stderr)
        self.assertFalse((self.root/'scratch/ran').exists())


if __name__=='__main__': unittest.main()
