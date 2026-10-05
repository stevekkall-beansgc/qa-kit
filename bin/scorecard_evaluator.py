"""Pure offline scorecard primitives. No collection, persistence, or activation.

Inputs must already be reviewed and normalized by a caller. A returned green
status describes supplied evidence only; it does not authenticate receipts or
certify a repository. This module is deliberately unwired from fleet reporting.
"""
from datetime import datetime, timezone
from fractions import Fraction


def _names(values, label):
    if not isinstance(values, list) or any(not isinstance(v,str) or not v.strip() for v in values) or len(values)!=len(set(values)):
        raise ValueError(label+' must contain unique nonempty strings')
    return values


def health(policy, ratings, complete, blockers):
    """Evaluate the supplied category judgments without rounding thresholds."""
    h=policy['health']
    categories=h['categories']
    weights=[c['weight'] for c in categories]
    if any(type(w) is not int or w<=0 for w in weights) or sum(weights)!=100:
        raise ValueError('invalid category weights')
    if not isinstance(ratings,list) or not isinstance(complete,list) or len(ratings)!=len(weights) or len(complete)!=len(weights):
        raise ValueError('one rating and completeness flag per category required')
    for rating,flag in zip(ratings,complete):
        if type(flag) is not bool or (rating is not None and (type(rating) is not int or not 0<=rating<=4)):
            raise ValueError('ratings must be integer 0..4 or null; completeness boolean')
        if flag != (rating is not None):
            raise ValueError('incomplete categories must be null')
    _names(blockers,'blockers')
    if set(blockers)-set(h['blockers']):raise ValueError('unknown blocker')
    points=sum((Fraction(w*(r or 0),4) for w,r in zip(weights,ratings)),Fraction(0))
    coverage=sum(w for w,flag in zip(weights,complete) if flag)
    bands=h['bands']
    if blockers:status='red'
    elif not all(complete):status='unknown'
    elif points>=Fraction(str(bands['green_min'])) and min(ratings)>=bands['green_category_floor']:status='green'
    elif points>=Fraction(str(bands['amber_min'])):status='amber'
    else:status='red'
    return dict(points=float(points),coverage=coverage,status=status,blockers=list(blockers),policy_version=policy['policy_version'])


def _time(value):
    if not isinstance(value,str):return None
    try:
        t=datetime.fromisoformat(value.replace('Z','+00:00'))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:return None


def security(policy, *, required, scans, findings, blockers, commit, scope, now, max_age_seconds):
    """Evaluate already normalized, scope-bound security evidence.

Freshness is a required caller decision, never activated from the candidate
policy. Findings/blockers are unresolved inputs and cannot expire away. Caller
must retain known findings across observations until independently cleared.
"""
    _names(required,'required');_names(findings,'findings');_names(blockers,'blockers')
    if not required:raise ValueError('nonempty reviewed required producer scope needed')
    if not isinstance(commit,str) or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('exact commit needed')
    if not isinstance(scope,str) or not scope.strip():raise ValueError('scope needed')
    if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError('aware evaluation time needed')
    if type(max_age_seconds) is not int or max_age_seconds<=0:raise ValueError('explicit positive freshness limit needed')
    if set(blockers)-set(policy['security']['blockers']):raise ValueError('unknown security blocker')
    if not isinstance(scans,list):raise ValueError('scans must be a list')
    by_producer={};unresolved=set(findings);diagnostics=[]
    for scan in scans:
        if not isinstance(scan,dict):raise ValueError('invalid scan')
        producer=scan.get('producer')
        if not isinstance(producer,str) or producer not in required:raise ValueError('unexpected producer')
        if producer in by_producer:raise ValueError('ambiguous duplicate producer')
        _names(scan.get('findings'),'scan findings')
        unresolved.update(scan['findings'])
        stamp=_time(scan.get('observed_at'))
        age=(now-stamp).total_seconds() if stamp else None
        reasons=[]
        for key,wanted in [('commit',commit),('scope',scope),('result','completed')]:
            if scan.get(key)!=wanted:reasons.append(key+' mismatch or incomplete')
        for key in ('version','evidence_ref'):
            if not isinstance(scan.get(key),str) or not scan[key].strip():reasons.append(key+' missing')
        if age is None or age<0 or age>max_age_seconds:reasons.append('source time invalid or stale')
        by_producer[producer]=not reasons
        diagnostics.extend(producer+': '+reason for reason in reasons)
    missing=[p for p in required if not by_producer.get(p,False)]
    diagnostics.extend(p+': never run or unavailable' for p in required if p not in by_producer)
    status='red' if blockers else 'amber' if unresolved else 'unknown' if missing else 'green'
    return dict(status=status,coverage_complete=not missing,missing=missing,findings=sorted(unresolved),blockers=list(blockers),diagnostics=diagnostics,openssf_score=None,policy_version=policy['policy_version'])
