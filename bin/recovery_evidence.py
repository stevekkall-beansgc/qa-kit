"""Validate private Agency recovery artifacts; never invoke providers or restore."""
import base64
import hashlib
import json
import math
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from reporting import timestamp

RESTORE_SCHEMA = 'agency.restore-proof/v1'
SYNC_SCHEMA = 'agency.backup-sync/v1'
MANIFEST_SCHEMA = 'agency.recovery-manifest/v1'
PHASES = ('local', 'offsite')
ERROR_STAGES = {'capture', 'plan', 'restore', 'integrity', 'schema', 'content',
                'download', 'object_binding', 'rpo', 'sync', 'upload', 'overlap'}


class Unverified(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require(test, message):
    if not test:
        raise Unverified(message)


def hash_value(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def recovery_limit(policy):
    if not isinstance(policy, dict) or policy.get('owner') != 'agency' or policy.get('consistency') != 'snapshot-consistent':
        return None
    limit = policy.get('max_recovery_point_age_hours')
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 0 < limit <= 24:
        return None
    return limit


def artifact(path, root):
    require(isinstance(path, str), 'artifact path unavailable')
    candidate = Path(path).resolve(strict=True)
    require(candidate.is_relative_to(root.resolve()), 'artifact outside trusted workspace')
    return candidate, candidate.read_bytes()


def database(path, root):
    candidate, before = artifact(path, root)
    require(not any(Path(str(candidate) + suffix).exists() for suffix in ('-wal', '-journal')),
            'staged database sidecar state unresolved')
    db = sqlite3.connect(candidate.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        require(db.execute('pragma integrity_check').fetchall() == [('ok',)], 'staged database integrity unverified')
        schema = db.execute('select type,name,tbl_name,sql from sqlite_master order by type,name').fetchall()
        tables = []
        for (name,) in db.execute("select name from sqlite_master where type='table' order by name"):
            quoted = '"' + name.replace('"', '""') + '"'
            def typed(value):
                if isinstance(value, bytes):
                    return ['blob', base64.b64encode(value).decode()]
                return ['null', None] if value is None else [type(value).__name__, value]
            rows = sorted(sha(canonical([typed(v) for v in row])) for row in db.execute('select * from ' + quoted))
            tables.append({'table': name, 'count': len(rows), 'sha256': sha(canonical(rows))})
    finally:
        db.close()
    require(candidate.read_bytes() == before, 'staged database changed during verification')
    return {'snapshot_sha256': sha(before), 'schema_sha256': sha(canonical(schema)),
            'logical_sha256': sha(canonical(tables)), 'tables': tables}


def context(data, root, now, limit):
    ref, binding = data.get('reference'), data.get('object_manifest')
    require(isinstance(ref, dict) and isinstance(binding, dict), 'reference or object manifest unavailable')
    point, captured = timestamp(ref.get('recovery_point_at')), timestamp(ref.get('captured_at'))
    complete = timestamp(data.get('completed_at'))
    require(point is not None and point == captured and captured <= complete <= now,
            'source snapshot recovery-point boundary unverified')
    age = (now - point).total_seconds() / 3600
    require(0 <= age <= limit, 'recovery point outside approved age bound')
    producer = timestamp(data.get('producer_completed_at', data.get('completed_at')))
    capture_start, capture_end = timestamp(ref.get('capture_started_at')), timestamp(ref.get('capture_completed_at'))
    require(capture_start is not None and capture_end is not None and producer is not None
            and capture_start <= captured <= capture_end <= producer <= complete,
            'reference capture and producer chronology unverified')
    identity = ref.get('database_identity')
    require(isinstance(identity, dict) and isinstance(identity.get('resolved_path'), str)
            and Path(identity['resolved_path']).is_absolute()
            and all(isinstance(identity.get(k), int) and not isinstance(identity[k], bool) and identity[k] >= 0
                    for k in ('device', 'inode')), 'source database identity unavailable')
    source = (root / 'platform/agency/agency.db').resolve(strict=True)
    source_stat = source.stat()
    require(Path(identity['resolved_path']).resolve(strict=True) == source
            and (identity['device'], identity['inode']) == (source_stat.st_dev, source_stat.st_ino),
            'authoritative source database identity differs')
    checked = database(ref.get('snapshot_path'), root)
    require(all(ref.get(k) == checked[k] for k in checked), 'reference snapshot hash or content binding unverified')
    path, raw = artifact(binding.get('path'), root)
    require(hash_value(binding.get('file_sha256')) and sha(raw) == binding['file_sha256'],
            'manifest file hash binding unverified')
    manifest = json.loads(raw)
    require(isinstance(manifest, dict) and manifest.get('schema') == MANIFEST_SCHEMA
            and hash_value(binding.get('sha256')) and sha(canonical(manifest)) == binding['sha256']
            and manifest.get('reference') == ref, 'canonical manifest or reference binding unverified')
    require(isinstance(binding.get('uri'), str) and binding['uri'].startswith('gs://')
            and binding['uri'].endswith('/recovery-manifests/' + binding['sha256'] + '.json')
            and re.fullmatch('[1-9][0-9]*', str(binding.get('generation'))) is not None
            and binding.get('md5_base64') == base64.b64encode(hashlib.md5(raw).digest()).decode(),
            'remote manifest generation or checksum binding unverified')
    objects = manifest.get('objects')
    if data.get('schema') == RESTORE_SCHEMA:
        uuid.UUID(data.get('producer_attempt_id', ''))
        require(data.get('objects') == objects, 'restore selected chain unavailable')
    require(isinstance(objects, list) and objects and data.get('objects', objects) == objects,
            'complete selected object chain unavailable')
    txid = ref.get('replica_max_txid')
    require(isinstance(txid, str) and re.fullmatch('[0-9a-fA-F]{16}', txid) is not None
            and manifest.get('replica_max_txid') == txid and manifest.get('captured_at') == ref['captured_at'],
            'replica transaction watermark unavailable')
    names = set()
    for obj in objects:
        require(isinstance(obj, dict), 'malformed object chain')
        level, name = obj.get('level'), obj.get('name')
        require(isinstance(level, int) and not isinstance(level, bool) and 0 <= level <= 9
                and isinstance(name, str) and re.fullmatch(r'[0-9a-fA-F]{16}-[0-9a-fA-F]{16}\.ltx', name) is not None
                and (level, name) not in names, 'invalid or duplicate object identity')
        names.add((level, name))
        _, payload = artifact(obj.get('cache_path'), root)
        minimum, maximum = name[:-4].split('-')
        require(obj.get('min_txid') == minimum and obj.get('max_txid') == maximum
                and int(minimum, 16) <= int(maximum, 16) <= int(txid, 16)
                and isinstance(obj.get('size'), int) and not isinstance(obj['size'], bool)
                and obj['size'] == len(payload), 'object range or size binding unverified')
        written = timestamp(obj.get('timestamp'))
        require(written is not None and written <= captured, 'replica transaction timestamp unverified')
        md5 = base64.b64encode(hashlib.md5(payload).digest()).decode()
        require(hash_value(obj.get('sha256')) and sha(payload) == obj['sha256']
                and obj.get('md5_base64') == md5 and obj.get('remote_md5') == md5
                and re.fullmatch('[1-9][0-9]*', str(obj.get('generation'))) is not None
                and re.fullmatch('[1-9][0-9]*', str(obj.get('metageneration'))) is not None
                and obj.get('uri') == binding['uri'].split('/recovery-manifests/')[0] + '/ltx/' + str(level) + '/' + name,
                'selected object bytes or remote generation binding unverified')
    require(max(int(obj['max_txid'], 16) for obj in objects) == int(txid, 16)
            and timestamp(ref.get('last_data_transaction_at')) == max(timestamp(obj['timestamp']) for obj in objects),
            'complete chain watermark or last data transaction unverified')
    return ref, binding, checked, age


def phase_proof(raw, ref, binding, checked, started, completed, root):
    restored = timestamp(raw.get('restored_at'))
    require(restored is not None and started <= restored <= completed, 'restore chronology unverified')
    require(raw.get('reference_sha256') == ref['snapshot_sha256']
            and raw.get('reference_logical_sha256') == ref['logical_sha256']
            and raw.get('restored_logical_sha256') == ref['logical_sha256']
            and raw.get('restored_schema_sha256') == ref['schema_sha256']
            and raw.get('tables') == ref['tables']
            and raw.get('object_manifest_sha256') == binding['sha256']
            and raw.get('recovery_point_at') == ref['recovery_point_at'], 'phase reference/content/manifest binding unverified')
    actual = database(raw.get('restored_snapshot_path'), root)
    require(raw.get('restored_snapshot_sha256') == actual['snapshot_sha256']
            and all(actual[k] == checked[k] for k in ('schema_sha256', 'logical_sha256', 'tables')),
            'restored immutable database content unverified')


def evaluate_restore(data, now=None, policy=None, artifact_root=None):
    now = now or datetime.now(timezone.utc)
    root = artifact_root or Path.home() / 'beans'
    result = {'schema': RESTORE_SCHEMA, 'attempted_at': None, 'verified_at': None,
              'recovery_point_at': None, 'recovery_point_age_hours': None,
              'object_manifest_sha256': None, 'overall': None, 'reason': 'authoritative recovery proof unavailable',
              'phases': {mode: {'attempted': None, 'verified': False, 'ok': None,
                               'status': 'unknown', 'error_stage': None} for mode in PHASES}}
    if not isinstance(data, dict) or data.get('schema') != RESTORE_SCHEMA:
        result['reason'] = 'missing or unsupported recovery receipt schema'
        return result
    started, completed = timestamp(data.get('started_at')), timestamp(data.get('completed_at'))
    timing_valid = bool(started and completed and started <= completed <= now)
    result['attempted_at'] = data.get('completed_at') if timing_valid else None
    for mode in PHASES:
        raw = data.get(mode)
        if not isinstance(raw, dict):
            continue
        phase = result['phases'][mode]
        phase['attempted'] = raw.get('attempted') if isinstance(raw.get('attempted'), bool) else None
        status = raw.get('status')
        if (timing_valid and phase['attempted'] is True and status == 'failed'
                and raw.get('ok') is False and raw.get('verified') is False and raw.get('error_stage') in ERROR_STAGES):
            phase.update(ok=False, status='failed', error_stage=raw['error_stage'])
        elif phase['attempted'] is False and status == 'not_attempted' and raw.get('ok') is None:
            phase['status'] = 'not_attempted'
        elif status == 'unverified':
            phase['status'] = 'unverified'
    failed = any(p['ok'] is False for p in result['phases'].values())
    if timing_valid and data.get('overall') is False and data.get('error_stage') in ERROR_STAGES:
        failed = True
    if failed:
        result.update(overall=False, reason='recovery attempt failed; successful verification not inferred')
    if not timing_valid:
        result['reason'] = 'invalid or future recovery attempt timestamps'
        return result
    limit = recovery_limit(policy)
    if limit is None:
        result['reason'] = 'valid snapshot-consistent recovery policy unavailable'
        return result
    try:
        uuid.UUID(data.get('attempt_id', ''))
        ref, binding, checked, age = context(data, root, now, limit)
        for mode in PHASES:
            raw = data.get(mode, {})
            if not isinstance(raw, dict) or not (raw.get('attempted') is True and raw.get('verified') is True
                    and raw.get('ok') is True and raw.get('status') == 'verified' and raw.get('error_stage') is None):
                continue
            try:
                phase_proof(raw, ref, binding, checked, started, completed, root)
                result['phases'][mode].update(ok=True, status='verified', verified=True)
            except (ValueError, OSError, TypeError, KeyError, sqlite3.Error):
                result['phases'][mode]['status'] = 'unverified'
        result.update(recovery_point_at=ref['recovery_point_at'], recovery_point_age_hours=age,
                      object_manifest_sha256=binding['sha256'])
        if not failed and data.get('overall') is True and data.get('rpo_verified') is True and all(p['verified'] for p in result['phases'].values()):
            result.update(overall=True, verified_at=data['completed_at'], reason='both immutable snapshot restores verified within recovery objective')
    except (ValueError, OSError, TypeError, KeyError, AttributeError, sqlite3.Error):
        if not failed:
            result['reason'] = 'immutable snapshot, object binding or recovery age unverified'
    return result


def restore_rows(summary):
    rows = []
    for mode in PHASES:
        phase = summary['phases'][mode]
        detail = phase['status']
        if phase['error_stage']:
            detail += ' at ' + phase['error_stage']
        if phase['verified']:
            detail += f" · recovery point {summary['recovery_point_age_hours']:.2f}h old"
        rows.append((f'Restore drill ({mode})', detail, phase['ok']))
    rows.append(('Restore drill overall', summary['reason'], summary['overall']))
    return rows


def evaluate_sync(data, now=None, policy=None, artifact_root=None):
    now = now or datetime.now(timezone.utc)
    root = artifact_root or Path.home() / 'beans'
    result = {'schema': SYNC_SCHEMA, 'attempted_at': None, 'completed_at': None,
              'verified_at': None, 'status': 'unknown', 'ok': None,
              'recovery_point_at': None, 'recovery_point_age_hours': None,
              'object_manifest_sha256': None, 'reason': 'timestamped sync proof unavailable'}
    if not isinstance(data, dict) or data.get('schema') != SYNC_SCHEMA:
        return result
    started, completed = timestamp(data.get('started_at')), timestamp(data.get('completed_at'))
    if not started or started > now:
        result['reason'] = 'invalid or future sync attempt timestamp'
        return result
    result['attempted_at'] = data['started_at']
    if data.get('status') == 'running' and completed is None and data.get('verified') is False:
        result.update(status='running', reason='sync attempt running; completion unverified')
        return result
    if not completed or not started <= completed <= now:
        result['reason'] = 'invalid or future sync completion timestamp'
        return result
    result['completed_at'] = data['completed_at']
    if data.get('status') == 'failed' and data.get('verified') is False and data.get('error_stage') in ERROR_STAGES:
        result.update(status='failed', ok=False, reason='latest sync attempt failed at ' + data['error_stage'])
        return result
    limit = recovery_limit(policy)
    if not (data.get('status') == 'completed' and data.get('verified') is True and limit is not None):
        return result
    try:
        uuid.UUID(data.get('attempt_id', ''))
        ref, binding, checked, age = context(data, root, now, limit)
        manifest = json.loads(Path(binding['path']).read_text())
        require(data.get('object_count') == len(manifest['objects']), 'sync object count binding unverified')
        result.update(status='verified', ok=True, verified_at=data['completed_at'],
                      recovery_point_at=ref['recovery_point_at'], recovery_point_age_hours=age,
                      object_manifest_sha256=binding['sha256'], reason='generation-bound immutable sync completion verified')
    except (ValueError, OSError, TypeError, KeyError, AttributeError, sqlite3.Error):
        result['reason'] = 'sync reference, object binding or recovery age unverified'
    return result
