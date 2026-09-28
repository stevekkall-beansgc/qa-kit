"""Explicit fleet evidence acceptance; unset policy never approves a baseline."""
from reporting import timestamp
from datetime import datetime, timezone


def fresh(when, hours, now):
    stamp = timestamp(when)
    return stamp is not None and 0 <= (now-stamp).total_seconds() <= hours*3600


def evaluate(qa, ci, policy, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(policy, dict):
        return {'verdict':'UNVERIFIED','reasons':['fleet policy pending owner decision']}
    hours = policy.get('max_age_hours')
    if policy.get('mode') not in ('sweep-and-current','sweep-only') or \
        not isinstance(hours,(int,float)) or isinstance(hours,bool) or not 0 < hours <= 8760:
        return {'verdict':'UNVERIFIED','reasons':['invalid fleet policy']}
    reasons = []
    sweep = qa.get('fleet_candidate')
    if not sweep or not fresh(sweep.get('when'),hours,now):
        reasons.append('no complete current fleet sweep within approved age')
    if qa.get('receipt_errors'):
        reasons.append('unreadable/malformed QA receipts require adjudication')
    per_repo = qa.get('per_repo',{})
    if not per_repo:
        reasons.append('empty eligible fleet')
    for name, row in per_repo.items():
        if policy['mode']=='sweep-and-current' and (
            row.get('verdict')!='PASS' or not row.get('current_complete') or not fresh(row.get('when'),hours,now)):
            reasons.append(f'{name}: current complete QA evidence unavailable')
        remote = ci.get(name,{})
        if remote.get('state')=='local-only':
            continue
        if remote.get('ok') is not True or not remote.get('head_verified') or not remote.get('coverage_verified') or \
            not fresh(remote.get('when'),hours,now) or not fresh(remote.get('queried_at'),hours,now):
            reasons.append(f'{name}: current successful CI evidence unavailable')
    return {'verdict':'UNVERIFIED' if reasons else 'PASS','reasons':reasons,
            'max_age_hours':hours,'mode':policy['mode']}
