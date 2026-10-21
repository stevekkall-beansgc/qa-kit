#!/usr/bin/env python3
"""Offline companion audit accounting; never executes evidence or grants acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'qa-kit.audit-review/v1'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.@/-]{0,159}\Z')
REF = re.compile(r'sha256:[0-9a-f]{64}\Z')


def digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                                 allow_nan=False).encode()).hexdigest()


def require(test):
    if not test:
        raise ValueError('invalid audit input')


def fields(value, names):
    require(isinstance(value, dict) and set(value) == set(names.split()))


def ids(values):
    require(isinstance(values, list) and all(isinstance(x, str) and ID.fullmatch(x)
                                          and '..' not in x for x in values))
    require(len(values) == len(set(values)))
    return set(values)


def reference(value):
    return isinstance(value, str) and REF.fullmatch(value) is not None


def target_identity(value):
    fields(value, 'repository commit tracked_sha256 source_blobs dependencies controls selection')
    require(isinstance(value['repository'], str) and
            re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value['repository']))
    require(isinstance(value['commit'], str) and re.fullmatch(r'[0-9a-f]{40}', value['commit']))
    require(isinstance(value['tracked_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', value['tracked_sha256']))
    ids([value['selection']])
    blobs = value['source_blobs']
    require(isinstance(blobs, dict) and blobs)
    for path, blob in blobs.items():
        require(isinstance(path, str) and ID.fullmatch(path) and '..' not in path.split('/'))
        require(isinstance(blob, str) and re.fullmatch(r'[0-9a-f]{40}', blob))
    require(isinstance(value['dependencies'], dict) and isinstance(value['controls'], dict)
            and 'qa' in value['controls'])
    for snapshots in (value['dependencies'], value['controls']):
        ids(list(snapshots))
        for snapshot in snapshots.values():
            fields(snapshot, 'head dirty tracked_sha256 matches_head')
            require(isinstance(snapshot['head'], str) and re.fullmatch(r'[0-9a-f]{40}', snapshot['head']))
            require(isinstance(snapshot['tracked_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', snapshot['tracked_sha256']))
            require(snapshot['dirty'] is False and snapshot['matches_head'] is True)


def review(record, expected, receipts, verification):
    """expected/verification are separately reviewed caller inputs, never record claims.

    receipts is a digest-keyed map of already supplied JSON receipts, not locations.
    Nothing is fetched, executed, persisted, cleared, scored or accepted here.
    """
    fields(record, 'schema target receipts scope findings known_findings exceptions review')
    require(record['schema'] == SCHEMA)
    fields(expected, 'target required_cells required_scope')
    target_identity(record['target'])
    target_identity(expected['target'])
    target = expected['target']
    required = ids(expected['required_cells']); required_scope = ids(expected['required_scope'])
    require(required and required_scope and all(re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+', x) for x in required))
    require(isinstance(receipts, dict) and isinstance(verification, dict))
    fields(verification, 'reproductions independence remediations')
    require(all(isinstance(verification[k], dict) for k in verification))
    problems = set(); covered = set(); tasks = []; findings = []; held = 0
    if record['target'] != expected['target']:
        problems.add('target_or_source_mismatch')
    refs = record['receipts']; require(isinstance(refs, list) and all(reference(x) for x in refs))
    require(len(refs) == len(set(refs)))
    for ref in refs:
        receipt = receipts.get(ref)
        if not isinstance(receipt, dict) or digest(receipt) != ref:
            problems.add('receipt_unavailable_or_changed'); continue
        target = expected['target']
        candidate = receipt.get('candidate', {})
        require(isinstance(candidate, dict))
        before, after = candidate.get('before', {}), candidate.get('after', {})
        require(isinstance(before, dict) and isinstance(after, dict))
        deps = receipt.get('fixtures', {})
        require(isinstance(deps, dict) and all(isinstance(v, dict) for v in deps.values()))
        bound = (record['target'] == target and receipt.get('schema') == 'qa-kit.validation-result/v1'
                 and receipt.get('github_repository') == target['repository']
                 and receipt.get('selection') == target['selection']
                 and before.get('head') == target['commit']
                 and before.get('tracked_sha256') == target['tracked_sha256']
                 and before.get('dirty') is False and before.get('matches_head') is True
                 and before == after and receipt.get('controls') == target['controls']
                 and set(deps) == set(target['dependencies'])
                 and all(v.get('before') == target['dependencies'][k]
                         and v.get('after') == target['dependencies'][k] for k, v in deps.items()))
        if not bound:
            problems.add('receipt_attribution_mismatch'); continue
        declared = ids(receipt.get('required', []))
        selected = ids(receipt.get('selected', []))
        if declared != required or not selected <= required:
            problems.add('receipt_selection_mismatch'); continue
        variant = receipt.get('variant'); require(isinstance(variant, str) and ID.fullmatch(variant))
        rows = receipt.get('tasks'); require(isinstance(rows, list))
        statuses = {}; seen = set()
        for row in rows:
            require(isinstance(row, dict))
            cell = str(row.get('task')) + '@' + str(row.get('variant'))
            require(ID.fullmatch(cell) and row.get('variant') == variant and cell not in seen)
            seen.add(cell)
            state = row.get('status'); require(state in {'pass', 'fail', 'blocked'})
            if state == 'pass' and (type(row.get('exit_code')) is not int or row.get('exit_code') != 0 or row.get('timed_out')
                                    or row.get('cancelled')):
                state = 'fail'
            statuses[cell] = state
            tasks.append({'cell': cell, 'status': state, 'receipt': ref})
        if receipt.get('status') != 'pass' or receipt.get('errors'):
            problems.add('execution_failed_or_incomplete')
        elif all(statuses.get(cell) == 'pass' for cell in selected):
            covered |= selected
        else:
            problems.add('task_evidence_missing_or_failed')
    scope = record['scope']; require(isinstance(scope, list))
    scope_ids = []
    scope_report = []
    for row in scope:
        fields(row, 'id status evidence reason')
        scope_ids.append(row['id']); require(row['status'] in {'inspected', 'excluded', 'unavailable'})
        require(isinstance(row['reason'], str) and row['reason'])
        safe = reference(row['evidence'])
        held += not safe
        state = row['status'] if safe else 'unavailable'
        if row['id'] in required_scope and state != 'inspected':
            problems.add('required_scope_not_inspected')
        scope_report.append({'id': row['id'], 'status': state})
    scope_set = ids(scope_ids)
    if not required_scope <= scope_set:
        problems.add('required_scope_missing')
    require(isinstance(record['findings'], list))
    finding_ids = []
    for row in record['findings']:
        fields(row, 'id status evidence counterevidence reproduction')
        finding_ids.append(row['id']); state = row['status']
        require(state in {'confirmed', 'rejected', 'unverified'})
        require(isinstance(row['evidence'], list) and isinstance(row['counterevidence'], list))
        safe = all(reference(r) for r in [*row['evidence'], *row['counterevidence']])
        held += sum(not reference(r) for r in [*row['evidence'], *row['counterevidence']])
        reproduction = verification['reproductions'].get(row['reproduction'])
        # Reproduction binds the entire claim, exact target and exact evidence.
        reproduced = (reference(row['reproduction']) and reproduction == {
            'target': expected['target'], 'finding': digest({k: v for k, v in row.items()
                                                           if k != 'reproduction'}), 'outcome': state})
        held += not reference(row['reproduction'])
        if state == 'unverified' or not safe or not row['evidence'] or (state == 'confirmed' and not reproduced):
            state = 'unverified'; problems.add('finding_needs_validation')
        if state == 'rejected' and not row['counterevidence']:
            state = 'unverified'; problems.add('rejection_needs_counterevidence')
        findings.append({'id': row['id'], 'status': state,
                         'evidence': [r for r in row['evidence'] if reference(r)],
                         'counterevidence': [r for r in row['counterevidence'] if reference(r)]})
    current_ids = ids(finding_ids); known = ids(record['known_findings'])
    unresolved = set(known)
    # A missing known finding is never clearance. Only a separate scoped verified
    # remediation supplied by the caller can mark it remediated in this report.
    for key in known:
        remediation = verification['remediations'].get(key, {})
        if (isinstance(remediation, dict) and remediation.get('target') == expected['target']
                and remediation.get('finding') == key and remediation.get('outcome') == 'remediated'
                and reference(remediation.get('fix_evidence'))
                and reference(remediation.get('verification_evidence'))
                and remediation.get('qualified_reviewer') is True):
            unresolved.discard(key)
    if known - current_ids:
        problems.add('known_finding_absent_scope_review')
    exceptions = record['exceptions']; require(isinstance(exceptions, list))
    for row in exceptions:
        fields(row, 'finding decision evidence')
        require(row['finding'] in known | current_ids and row['decision'] in {'accepted', 'pending', 'rejected'})
        held += not reference(row['evidence'])
    r = record['review']; fields(r, 'author reviewer independence_evidence')
    ids([r['author']]); ids([r['reviewer']])
    held += not reference(r['independence_evidence'])
    basis = verification['independence'].get(r['independence_evidence'])
    independent = (r['author'] != r['reviewer'] and reference(r['independence_evidence']) and
                   basis == {'author': r['author'], 'reviewer': r['reviewer'],
                             'record': digest(record), 'independent': True})
    if not independent:
        problems.add('independence_unverified')
    missing = required - covered
    if missing: problems.add('required_cells_missing')
    if held: problems.add('unsafe_evidence_reference')
    return {'schema': 'qa-kit.audit-report/v1', 'mode': 'report-only', 'acceptance_granted': False,
            'record_sha256': digest(record), 'problems': sorted(problems),
            'covered_cells': sorted(covered), 'remaining_cells': sorted(missing),
            'scope': scope_report, 'tasks': tasks, 'findings': findings,
            'unresolved_known_findings': sorted(unresolved),
            'exceptions': [{'finding': x['finding'], 'decision': x['decision']} for x in exceptions],
            'independence': 'caller-corroborated' if independent else 'unverified',
            'public_rendering': 'hold' if held else 'safe-reference-only',
            'held_reference_count': held}


def load(path):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out); out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('record', 'expected', 'receipts', 'verification'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        result = review(*(load(getattr(args, n)) for n in ('record', 'expected', 'receipts', 'verification')))
    except (ValueError, TypeError, KeyError, OSError):
        print(json.dumps({'error': 'invalid_or_unavailable_audit_input', 'acceptance_granted': False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 1 if result['problems'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
