"""Shared evidence parsing; no external queries or state changes on import."""
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_VERSION = 'v1.0'


def git_value(path, *args):
    try:
        p = subprocess.run(['git', '-C', str(Path(path).expanduser()), *args],
                           capture_output=True, text=True, timeout=10)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''


def repo_remote(path):
    rc, _ = git_value(path, 'rev-parse', '--git-dir')
    if rc:
        return 'unknown', ''
    rc, names = git_value(path, 'remote')
    if rc:
        return 'unknown', ''
    if 'origin' not in names.splitlines():
        return 'local-only', ''
    rc, url = git_value(path, 'remote', 'get-url', 'origin')
    return ('remote', url) if not rc and url else ('unknown', '')


def common_identity(path):
    rc, value = git_value(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    return str(Path(value).resolve()) if rc == 0 and value else None


def identity(path):
    rc, head = git_value(path, 'rev-parse', 'HEAD')
    status_rc, status = git_value(path, 'status', '--porcelain=v1', '--untracked-files=all')
    return {'head': head if rc == 0 else None,
            'dirty': bool(status) if status_rc == 0 else None}


def timestamp(value):
    try:
        if len(value) == 16 and value.endswith('Z'):
            return datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def receipt_order(path):
    match = re.fullmatch(r'run-(\d{8}T\d{6}Z)(?:-(\d+))?\.json', path.name)
    return (match[1], int(match[2] or 0)) if match else (path.name, 0)


def valid_evidence(value):
    if not isinstance(value, dict):
        return False
    for key in ('source', 'manifest', 'selection', 'runtime', 'repos'):
        if key in value and not isinstance(value[key], dict):
            return False
    for pair in value.get('repos', {}).values():
        if not isinstance(pair, dict) or any(key in pair and not isinstance(pair[key], dict) for key in ('before','after')):
            return False
    selection = value.get('selection',{})
    for key in ('repos','tiers'):
        if key in selection and (not isinstance(selection[key],list) or any(not isinstance(v,str) for v in selection[key])):
            return False
    if 'collection_errors' in value and not isinstance(value['collection_errors'],list):
        return False
    return True


def normalize_state(raw, names):
    """Legacy timestamps are attempts, never proof of verified coverage."""
    if not isinstance(raw, dict):
        raw = {}
    rows = raw.get('repos', {})
    if not isinstance(rows, dict):
        rows = {}
    nested = rows.get('repos', {})
    if isinstance(nested, dict):
        rows = {**nested, **rows}
    normalized = {}
    for name in names:
        old = rows.get(name, {})
        old = old if isinstance(old, dict) else {}
        value = old.get('last_run_id', 0)
        normalized[name] = {'last_run_id': value if isinstance(value, int) and not isinstance(value, bool) else 0,
                            'state': old.get('state', 'unknown'),
                            'verified': old.get('verified')}
    return {'schema_version': 2, 'contract_version': CONTRACT_VERSION,
            'attempted': raw.get('attempted', raw.get('checked')),
            'verified': raw.get('verified') if raw.get('schema_version') == 2 else None,
            'repos': normalized}


def valid_runs(runs, *, monitor=False):
    if not isinstance(runs, list):
        return False
    for r in runs:
        if not isinstance(r, dict):
            return False
        if not isinstance(r.get('conclusion'), str) and not (
            r.get('conclusion') is None and r.get('status') in ('queued','in_progress','waiting','requested','pending')):
            return False
        if monitor and (not isinstance(r.get('databaseId'), int) or isinstance(r['databaseId'], bool)):
            return False
    return True


def ci_verdict(runs):
    if not valid_runs(runs):
        return 'unknown', '', None
    if not runs:
        return 'no runs', '', None
    r = runs[0]
    status = r.get('status')
    conclusion = r.get('conclusion')
    if status and status != 'completed':
        return status, r.get('url', ''), None
    if not conclusion:
        return 'unknown', r.get('url', ''), None
    return conclusion, r.get('url', ''), conclusion == 'success'
