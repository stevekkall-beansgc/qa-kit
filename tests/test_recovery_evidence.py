"""Synthetic recovery faults must remain distinct from verified recovery."""
from datetime import datetime, timezone
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from recovery_evidence import evaluate_restore

CLOCK = datetime(2026, 9, 29, 11, tzinfo=timezone.utc)
POLICY = {'owner': 'agency', 'consistency': 'snapshot-consistent',
          'max_recovery_point_age_hours': 24}


def failed_attempt():
    return {'schema': 'agency.restore-proof/v1', 'attempt_id': 'synthetic-attempt',
            'started_at': '2026-09-29T10:40:00Z', 'completed_at': '2026-09-29T10:50:00Z',
            'local': {'attempted': False, 'verified': False, 'ok': None, 'status': 'not_attempted'},
            'offsite': {'attempted': True, 'verified': False, 'ok': False,
                        'status': 'failed', 'error_stage': 'download'}, 'overall': False}


class RecoveryEvidence(unittest.TestCase):
    def test_download_failure_and_skipped_local_phase_remain_distinct(self):
        result = evaluate_restore(failed_attempt(), CLOCK, POLICY)
        self.assertFalse(result['overall'])
        self.assertIsNone(result['phases']['local']['ok'])
        self.assertEqual(result['phases']['local']['status'], 'not_attempted')
        self.assertFalse(result['phases']['offsite']['ok'])
        self.assertEqual(result['phases']['offsite']['error_stage'], 'download')
        self.assertIsNone(result['verified_at'])

    def test_failure_is_not_replaced_by_historical_verification(self):
        data = failed_attempt()
        data['verified_at'] = '2026-09-28T12:00:00Z'
        data['last_success'] = {'overall': True}
        result = evaluate_restore(data, CLOCK, POLICY)
        self.assertFalse(result['overall'])
        self.assertIsNone(result['verified_at'])

    def test_future_or_malformed_attempt_cannot_approve_status(self):
        for patch in [{'completed_at': '2026-09-30T12:00:00Z'},
                      {'started_at': '2026-09-29T10:59:00Z'},
                      {'started_at': 'invalid'}, {'completed_at': None}]:
            data = failed_attempt(); data.update(patch)
            result = evaluate_restore(data, CLOCK, POLICY)
            self.assertIsNone(result['overall'])
            self.assertIsNone(result['attempted_at'])

    def test_inconsistent_flags_and_unknown_phase_are_not_verdicts(self):
        for patch in [{'ok': 'false'}, {'verified': True}, {'attempted': 'true'},
                      {'status': 'unknown'}, {'error_stage': 'invented'}]:
            data = failed_attempt(); data['offsite'].update(patch)
            result = evaluate_restore(data, CLOCK, POLICY)
            self.assertIsNone(result['overall'])
            self.assertIsNone(result['phases']['offsite']['ok'])

    def test_missing_or_unsupported_schema_and_malformed_input_are_unknown(self):
        for data in [None, [], {}, dict(failed_attempt(), schema='agency.restore-proof/v99')]:
            result = evaluate_restore(data, CLOCK, POLICY)
            self.assertIsNone(result['overall'])
            self.assertIsNone(result['verified_at'])

class ArtifactFixture:
    def setUp(self):
        import tempfile, sqlite3, shutil, hashlib, base64
        from recovery_evidence import canonical, database
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'beans'
        source = self.root / 'platform/agency/agency.db'; source.parent.mkdir(parents=True)
        with sqlite3.connect(source) as db:
            db.execute('create table sample(id integer primary key, value text)')
            db.execute("insert into sample values(1, 'synthetic')")
        reference = self.root / 'reference.db'; shutil.copyfile(source, reference)
        fingerprint = database(str(reference), self.root)
        identity = source.stat()
        ref = dict(fingerprint, snapshot_path=str(reference),
            database_identity={'resolved_path': str(source), 'device': identity.st_dev, 'inode': identity.st_ino},
            capture_started_at='2026-09-29T10:30:00Z', captured_at='2026-09-29T10:30:01Z',
            capture_completed_at='2026-09-29T10:30:02Z', recovery_point_at='2026-09-29T10:30:01Z',
            replica_max_txid='0000000000000001', last_data_transaction_at='2026-09-29T10:29:00Z')
        cache = self.root / 'object.ltx'; cache.write_bytes(b'synthetic LTX binding fixture')
        md5 = base64.b64encode(hashlib.md5(cache.read_bytes()).digest()).decode()
        objects = [{'level':9, 'name':'0000000000000001-0000000000000001.ltx',
            'min_txid':'0000000000000001','max_txid':'0000000000000001', 'size':cache.stat().st_size,
            'timestamp':'2026-09-29T10:29:00Z', 'cache_path':str(cache),
            'sha256':hashlib.sha256(cache.read_bytes()).hexdigest(), 'md5_base64':md5,'remote_md5':md5,
            'uri':'gs://synthetic/agency/ltx/9/0000000000000001-0000000000000001.ltx',
            'generation':'100', 'metageneration':'1'}]
        manifest = {'schema':'agency.recovery-manifest/v1','reference':ref, 'objects':objects,
            'captured_at':ref['captured_at'],'replica_max_txid':ref['replica_max_txid']}
        manifest_path = self.root / 'point.json'; manifest_path.write_bytes(canonical(manifest)+b'\n')
        binding = {'path':str(manifest_path), 'sha256':hashlib.sha256(canonical(manifest)).hexdigest(),
            'file_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'uri':'gs://synthetic/agency/recovery-manifests/'+hashlib.sha256(canonical(manifest)).hexdigest()+'.json','generation':'101',
            'md5_base64':base64.b64encode(hashlib.md5(manifest_path.read_bytes()).digest()).decode()}
        self.data={'schema':'agency.restore-proof/v1','attempt_id':'00000000-0000-4000-8000-000000000001',
            'producer_attempt_id':'00000000-0000-4000-8000-000000000002',
            'started_at':'2026-09-29T10:40:00Z','completed_at':'2026-09-29T10:50:00Z',
            'producer_completed_at':'2026-09-29T10:35:00Z','overall':True,'rpo_verified':True,
            'reference':ref,'objects':objects,'object_manifest':binding}
        for mode in ('local','offsite'):
            restored = self.root / (mode+'.db'); shutil.copyfile(reference,restored)
            self.data[mode]={'attempted':True,'verified':True,'ok':True,'status':'verified','error_stage':None,
                'restored_at':'2026-09-29T10:45:00Z','reference_sha256':ref['snapshot_sha256'],
                'reference_logical_sha256':ref['logical_sha256'],'restored_logical_sha256':ref['logical_sha256'],
                'restored_schema_sha256':ref['schema_sha256'],'tables':ref['tables'],
                'restored_snapshot_path':str(restored),'restored_snapshot_sha256':ref['snapshot_sha256'],
                'recovery_point_at':ref['recovery_point_at'],'object_manifest_sha256':binding['sha256']}

    def evaluate(self, **kw):
        return evaluate_restore(self.data, kw.get('now',CLOCK), kw.get('policy',POLICY), artifact_root=self.root)

    def rebind_manifest(self):
        import json,hashlib,base64
        from recovery_evidence import canonical
        binding=self.data['object_manifest'];path=Path(binding['path'])
        manifest=json.loads(path.read_text());manifest.update(reference=self.data['reference'],objects=self.data['objects'])
        path.write_bytes(canonical(manifest)+b'\n')
        binding.update(sha256=hashlib.sha256(canonical(manifest)).hexdigest(),file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            md5_base64=base64.b64encode(hashlib.md5(path.read_bytes()).digest()).decode())
        binding['uri']='gs://synthetic/agency/recovery-manifests/'+binding['sha256']+'.json'
        for mode in ('local','offsite'):self.data[mode]['object_manifest_sha256']=binding['sha256']

class BoundArtifacts(ArtifactFixture, unittest.TestCase):
    def test_complete_bound_artifacts_verify_each_phase_and_overall(self):
        result=self.evaluate()
        self.assertTrue(result['overall'])
        self.assertTrue(all(p['verified'] for p in result['phases'].values()))
        self.assertEqual(result['verified_at'],self.data['completed_at'])
        self.assertNotIn(str(self.root),str(result))

    def test_health_consumes_private_artifacts_without_provider_query_or_payload(self):
        import json
        from unittest import mock
        from types import SimpleNamespace
        import health, recovery_evidence
        logs=self.root/'platform/agency/logs';logs.mkdir()
        (logs/'restore-drill.json').write_text(json.dumps(self.data))
        with mock.patch.object(Path,'home',return_value=self.root.parent), \
             mock.patch.object(health,'load_policy',return_value={'recovery':POLICY}), \
             mock.patch.object(recovery_evidence,'datetime') as dates, \
             mock.patch.object(health.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')) as commands:
            dates.now.return_value=CLOCK
            evidence=health.backup_evidence()
            rows=health.backups(evidence)
        self.assertTrue(evidence['restore']['overall'])
        self.assertTrue(next(row[2] for row in rows if row[0]=='DB offsite (GCS)'))
        self.assertTrue(next(row[2] for row in rows if row[0]=='Restore drill overall'))
        self.assertIsNone(evidence['sync']['ok'])
        self.assertNotIn(str(self.root),json.dumps(evidence))
        self.assertNotIn('synthetic',json.dumps(evidence))
        self.assertTrue(all('gsutil' not in str(call) for call in commands.call_args_list))

    def test_same_count_content_mutation_only_invalidates_affected_phase(self):
        import sqlite3
        with sqlite3.connect(self.data['offsite']['restored_snapshot_path']) as db:
            db.execute("update sample set value='changed'")
        result=self.evaluate()
        self.assertTrue(result['phases']['local']['verified'])
        self.assertIsNone(result['phases']['offsite']['ok'])
        self.assertIsNone(result['overall'])

    def test_missing_manifest_or_tampered_object_cannot_pass(self):
        for target in ['manifest','object']:
            path=Path(self.data['object_manifest']['path'] if target=='manifest' else self.data['objects'][0]['cache_path'])
            original=path.read_bytes();path.write_bytes(b'changed')
            self.assertIsNone(self.evaluate()['overall']);path.write_bytes(original)

    def test_rpo_exact_boundary_and_one_second_beyond_are_distinct(self):
        from datetime import timedelta
        from reporting import timestamp
        point=timestamp(self.data['reference']['recovery_point_at'])
        self.assertTrue(self.evaluate(now=point+timedelta(hours=24))['overall'])
        self.assertIsNone(self.evaluate(now=point+timedelta(hours=24,seconds=1))['overall'])

    def test_malformed_policy_does_not_raise_or_verify(self):
        for value in [None,True,'24',float('nan'),float('inf'),25,0]:
            policy=dict(POLICY,max_recovery_point_age_hours=value)
            self.assertIsNone(self.evaluate(policy=policy)['overall'])

    def test_other_database_identity_cannot_be_substituted(self):
        self.data['reference']['database_identity']['resolved_path']=str(self.root/'unrelated.db')
        self.rebind_manifest()
        self.assertIsNone(self.evaluate()['overall'])

    def test_remote_generation_missing_or_object_range_wrong_cannot_pass(self):
        for patch in [{'generation':None},{'metageneration':'0'},{'min_txid':'ffffffffffffffff'},
                      {'size':0},{'max_txid':'0000000000000002'},
                      {'uri':'gs://wrong/agency/ltx/9/0000000000000001-0000000000000001.ltx'}]:
            original=dict(self.data['objects'][0]);self.data['objects'][0].update(patch);self.rebind_manifest()
            self.assertIsNone(self.evaluate()['overall'])
            self.data['objects'][0]=original;self.rebind_manifest()

class SyncArtifacts(ArtifactFixture, unittest.TestCase):
    def sync(self):
        return {'schema':'agency.backup-sync/v1','attempt_id':self.data['producer_attempt_id'],
                'started_at':'2026-09-29T10:29:00Z','completed_at':self.data['producer_completed_at'],
                'status':'completed','verified':True,'error_stage':None,
                'reference':self.data['reference'],'object_manifest':self.data['object_manifest'],
                'object_count':len(self.data['objects'])}

    def test_bound_sync_completion_is_not_a_restore_verdict(self):
        from recovery_evidence import evaluate_sync
        result=evaluate_sync(self.sync(),CLOCK,POLICY,artifact_root=self.root)
        self.assertTrue(result['ok'])
        self.assertEqual(result['verified_at'],self.data['producer_completed_at'])
        self.assertNotIn('overall',result)
        self.assertNotIn(str(self.root),str(result))

    def test_current_running_or_failed_sync_never_inherits_old_success(self):
        from recovery_evidence import evaluate_sync
        data=self.sync();data['last_success']=copy.deepcopy(data)
        data.update(status='running',verified=False,completed_at=None)
        result=evaluate_sync(data,CLOCK,POLICY,artifact_root=self.root)
        self.assertIsNone(result['ok']);self.assertIsNone(result['verified_at'])
        data.update(status='failed',error_stage='upload',completed_at='2026-09-29T10:55:00Z')
        result=evaluate_sync(data,CLOCK,POLICY,artifact_root=self.root)
        self.assertFalse(result['ok']);self.assertIsNone(result['verified_at'])

    def test_current_manifest_tamper_or_missing_object_keeps_sync_unknown(self):
        from recovery_evidence import evaluate_sync
        data=self.sync();Path(data['object_manifest']['path']).unlink()
        self.assertIsNone(evaluate_sync(data,CLOCK,POLICY,artifact_root=self.root)['ok'])
