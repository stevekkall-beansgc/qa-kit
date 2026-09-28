#!/usr/bin/env python3
"""health.py — ONE pane for Legume Labs fleet health.

Aggregates: service probes (hub, runner, Qdrant, LM Studio, harness
console), per-repo latest GitHub Actions conclusion, last qa-kit baseline
verdict, monitor/drift state. Emits public/index.html (served by the hub
at /qa) + public/health.json for machines.

Exit 0 always (reporting tool, not a gate); failures render AS red.
Stdlib only. Scheduled hourly alongside ci_monitor via bean-sched.
"""
import json
import subprocess
import urllib.request
import os
import re
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from reporting import CONTRACT_VERSION, repo_remote, ci_verdict, normalize_state, timestamp, identity, receipt_order, valid_evidence
import hashlib
from fleet_policy import evaluate as evaluate_fleet

import shutil
GH_BIN = shutil.which("gh") or "/opt/homebrew/bin/gh"  # launchd PATH lacks homebrew

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"
PUBLIC = HERE / "public"
OWNER = "stevekkall-beansgc"


def expand(p):
    return Path(p).expanduser()


def probe_url(url, timeout=3):
    """Liveness: ANY http response (<500) proves something is serving."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500, ""
    except Exception as e:
        return False, str(e)[:120]


def gh(args):
    try:
        p = subprocess.run([GH_BIN, *args], capture_output=True, text=True, timeout=30)
        return json.loads(p.stdout) if p.returncode == 0 else None
    except Exception:
        return None


def services():
    out = []
    ok, _ = probe_url("http://127.0.0.1:8800/api/health")
    out.append(("Hub API", ":8800", ok))
    runner = None
    try:
        with urllib.request.urlopen("http://127.0.0.1:8800/api/runner/status", timeout=3) as r:
            d = json.loads(r.read())
        age = d.get("heartbeat_age_seconds", 9999)
        out.append(("Runner heartbeat", f"{age}s old", age < 120))
    except Exception as e:
        out.append(("Runner heartbeat", str(e)[:60], False))
    ok, _ = probe_url("http://127.0.0.1:6333/readyz")
    out.append(("Qdrant", ":6333", ok))
    models = "-"
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=3) as r:
            models = f"{len(json.loads(r.read()).get('data', []))} loaded"
    except Exception:
        pass
    ok, _ = probe_url("http://127.0.0.1:1234/v1/models")
    out.append(("LM Studio", f":1234 · {models}", ok))
    ok, _ = probe_url("http://127.0.0.1:8766/api/status")
    out.append(("Harness console", ":8766 · benchmark lane", ok))

    tick, tick_ok = "never", False
    try:
        state_dir = Path.home() / "beans/platform/bean-sched/state"
        candidates = [state_dir / "state.json", state_dir / "history.json"]
        mtimes = [f.stat().st_mtime for f in candidates if f.exists()]
        if mtimes:
            age = max(0, int((datetime.now(timezone.utc).timestamp() - max(mtimes)) // 60))
            tick = "just now" if age < 2 else f"{age}m ago"
            tick_ok = age <= 10  # tick cadence is ~5 min
    except Exception:
        pass
    out.append(("bean-sched tick", f"5-min cadence · last write {tick}", tick_ok))
    return out


def backups():
    """Backup-chain probes: litestream local replica, gcssync launchd job,
    GCS offsite freshness. Exists because gcssync failed silently for days —
    nothing else watched the watchmen of the offsite copy."""
    out = []
    # 1. local replica freshness (litestream layer)
    # Healthy = segments keep pace with ACTUAL db writes — a quiet hour is not
    # a failure, so compare against agency.db-wal mtime (5-min slack).
    replica = Path.home() / "beans/platform/agency/replica"
    try:
        mtimes = [f.stat().st_mtime for f in replica.rglob("*.ltx")]
        if not mtimes:
            raise FileNotFoundError("no .ltx segments")
        seg_age_min = int((datetime.now(timezone.utc).timestamp() - max(mtimes)) // 60)
        wal = Path.home() / "beans/platform/agency/agency.db-wal"
        if not wal.exists():
            raise FileNotFoundError('database write reference unavailable')
        write_age_min = int((datetime.now(timezone.utc).timestamp() - wal.stat().st_mtime) // 60)
        lag_min = seg_age_min - write_age_min  # how far replication trails writes
        out.append(("DB replica (local)",
                    f"segment {seg_age_min}m old · last db write {write_age_min}m ago",
                    lag_min <= 5))
    except Exception as e:
        out.append(("DB replica (local)", str(e)[:60], False))
    # 2. gcssync last exit status
    try:
        p = subprocess.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/com.agency.gcssync"],
                           capture_output=True, text=True, timeout=10)
        duration = None
        pid = re.search(r'^\s*pid = (\d+)\s*$', p.stdout, re.M)
        if pid:
            elapsed = subprocess.run(['/bin/ps','-p',pid[1],'-o','etime='],capture_output=True,text=True,timeout=5)
            if elapsed.returncode == 0:
                duration = elapsed.stdout.strip()
        out.append(sync_status(p.stdout if p.returncode == 0 else '', duration))
    except (OSError, subprocess.TimeoutExpired):
        out.append(('gcssync (launchd)', 'process state unavailable', None))
    out.append(('gcssync last successful completion', 'no timestamped completion receipt available', None))
    # 3. offsite freshness via gsutil (absolute interpreter pin — standing rule)
    gsutil = shutil.which("gsutil") or "/opt/homebrew/bin/gsutil"
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin",
           "CLOUDSDK_PYTHON": "/opt/homebrew/bin/python3.12",
           "HOME": str(Path.home())}
    try:
        r = subprocess.run([gsutil, "-q", "ls", "-lR",
                            "gs://downtown-504818-agency-db/agency/ltx/"],
                           capture_output=True, text=True, timeout=45, env=env)
        if r.returncode:
            raise RuntimeError('offsite query failed; freshness unknown')
        stamps = [ln.split()[1] for ln in r.stdout.splitlines()
                  if len(ln.split()) >= 2 and "T" in ln.split()[1] and "Z" in ln.split()[1]]
        if stamps:
            newest = max(stamps)
            t = datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_h = int((datetime.now(timezone.utc) - t).total_seconds() // 3600)
            out.append(("DB offsite (GCS)", f"newest object {age_h}h old", 0 <= age_h <= 24))
        else:
            out.append(("DB offsite (GCS)", "no timestamped objects found", False))
    except Exception as e:
        out.append(("DB offsite (GCS)", str(e)[:60], None))
    # 4. restore drill (scheduled e2e proof backups are restorable)
    try:
        d = json.loads((Path.home() / "beans/platform/agency/logs/restore-drill.json").read_text())
        out.extend(restore_status(d))
    except Exception as e:
        out.append(("Restore drill", f"no result: {str(e)[:40]}", False))
    # 5. full-runbook rehearsal doctor (quarterly)
    try:
        d = json.loads((Path.home() / "beans/platform/agency/logs/runbook-doctor.json").read_text())
        when = datetime.strptime(d["when"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_d = int((datetime.now(timezone.utc) - when).total_seconds() // 86400)
        out.append(("Runbook rehearsal",
                    f"{d.get('passed', '?')} checks · {d.get('failed', '?')} failed · {age_d}d ago",
                    bool(d.get("overall")) and age_d <= 100))
    except Exception as e:
        out.append(("Runbook rehearsal", f"no result: {str(e)[:40]}", False))
    return out


def sync_status(output, duration=None):
    state = re.search(r'^\s*state = (.+)$', output, re.M)
    code = re.search(r'^\s*last exit code = (.+)$', output, re.M)
    detail = f"{state[1].strip() if state else 'unknown'} · runtime {duration or 'unknown'} · last exit {code[1].strip() if code else '?'}"
    # Process presence and a historical exit cannot prove completion/freshness.
    return ('gcssync (launchd)', detail, None)


def restore_status(data, now=None):
    now = now or datetime.now(timezone.utc)
    when = timestamp(data.get('when'))
    age = (now - when).total_seconds()/3600 if when else None
    fresh = age is not None and 0 <= age <= 48
    rows = []
    for mode in ('local', 'offsite'):
        phase = data.get(mode)
        verdict = phase.get('ok') if isinstance(phase, dict) else None
        ok = (verdict and fresh) if isinstance(verdict, bool) else None
        detail = 'not reached/unknown' if verdict is None else ('passed' if verdict else 'failed')
        if verdict is False and isinstance(phase.get('detail'),str) and 'row mismatch' in phase['detail'].lower():
            detail = 'failed snapshot/live comparison; consistency unverified'
        detail += f" · {int(age)}h ago" if age is not None else ' · age unknown'
        rows.append((f'Restore drill ({mode})', detail, ok))
    rows.append(('Restore drill overall', 'snapshot recovery objective pending; phase results shown separately',
                 False if data.get('overall') is False else None))
    return rows


def ci_evidence():
    man = json.loads(MANIFEST.read_text())
    rows = {}
    queried = datetime.now(timezone.utc).isoformat()
    for repo in man["repos"]:
        name = repo['name']
        row = {'state':'unknown','url':'','ok':None,'head_verified':False,'coverage_verified':False,
               'scope':'latest branch run; required workflow coverage unverified',
               'when':None,'head':None,'current_head':None,'queried_at':queried}
        rows[name] = row
        if repo.get("status") == "planned":
            row['state'] = 'planned'
            continue
        gh_name = repo.get("github", name)
        remote_state, _ = repo_remote(repo['path'])
        if remote_state != 'remote':
            row['state'] = remote_state
            continue
        branch = repo.get('default_branch','main')
        runs = gh(["run", "list", "--repo", f"{OWNER}/{gh_name}",
                   "--branch", branch, "--limit", "1",
                   "--json", "conclusion,url,displayTitle,status,headSha,createdAt"])
        state, url, ok = ci_verdict(runs)
        row.update(state=state,url=url,ok=ok)
        if isinstance(runs,list) and runs and isinstance(runs[0],dict):
            row['head'] = runs[0].get('headSha')
            row['when'] = runs[0].get('createdAt')
        if ok is True:
            commit = gh(['api',f'repos/{OWNER}/{gh_name}/commits/{branch}'])
            row['current_head'] = commit.get('sha') if isinstance(commit,dict) else None
            row['head_verified'] = bool(row['head']) and row['head']==row['current_head']
            if not row['head_verified'] or not timestamp(row['when']):
                row['ok'] = None
    return rows


def ci_rows():
    return [(name,row['state'],row['url'],row['ok']) for name,row in ci_evidence().items()]


def load_policy():
    try:
        data=json.loads((HERE/'reporting-policy.json').read_text())
        return data if isinstance(data,dict) and data.get('schema_version')==1 else None
    except (OSError,ValueError):
        return None


def qa_baseline(policy=None, ci=None, now=None):
    man = json.loads(MANIFEST.read_text())
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    eligible = {r['name']: r for r in man['repos'] if r.get('status') != 'planned'}
    per_repo = {name: {'verdict':'unknown','when':'','checks':[]} for name in eligible}
    latest = {'verdict':'never-run','when':'','total':0,'failed':0,'repos':[],'checks':[]}
    candidates = []
    errors = []
    current = {name:identity(repo['path']) for name,repo in eligible.items()}
    for log in sorted(HERE.glob('logs/run-*.json'), key=receipt_order):
        try:
            d = json.loads(log.read_text()); results = d['results']
            if not isinstance(results, list) or any(not isinstance(r,dict) or
                not isinstance(r.get('repo'),str) or not isinstance(r.get('kind'),str) or
                not isinstance(r.get('ok'),bool) for r in results):
                raise ValueError('invalid results')
            when = d.get('when',''); stamp = timestamp(when)
            if not stamp:
                raise ValueError('invalid timestamp')
            if 'evidence' in d and not valid_evidence(d['evidence']):
                raise ValueError('invalid provenance')
        except (OSError, ValueError, KeyError, TypeError):
            errors.append(log.name)
            # Cannot know which repos the invalid receipt would have superseded.
            for value in per_repo.values():
                value['verdict'] = 'unknown'
            latest = {'verdict':'unknown','when':'','total':0,'failed':0,'repos':[],'checks':[]}
            continue
        failed = sum(not r['ok'] for r in results)
        names = sorted({r['repo'] for r in results})
        checks = sorted({r['kind'] for r in results})
        latest = {'verdict':'PASS' if results and not failed else 'FAIL','when':when,
                  'total':len(results),'failed':failed,'repos':names,'checks':checks}
        for name in names:
            if name in per_repo:
                owned = [r for r in results if r['repo']==name]
                evidence = d.get('evidence') or {}
                pair = evidence.get('repos',{}).get(name,{})
                before,after = pair.get('before',{}),pair.get('after',{})
                wanted = {'docs','unit'}
                for kind in ('setup','e2e'):
                    if (eligible[name].get(kind) or {}).get('cmd'): wanted.add(kind)
                if eligible[name].get('validation'): wanted.add('validation')
                complete = bool(before.get('head')) and before.get('dirty') is False and before==after==current[name] and \
                    {r['kind'] for r in owned}==wanted and evidence.get('schema_version')==1 and \
                    evidence.get('source',{}).get('head') and evidence.get('source',{}).get('dirty') is False and \
                    evidence.get('manifest',{}).get('sha256')==digest and not evidence.get('collection_errors')
                per_repo[name] = {'verdict':'PASS' if all(r['ok'] for r in owned) else 'FAIL',
                                  'when':when,'checks':sorted({r['kind'] for r in owned}),
                                  'current_complete':complete,
                                  'source_head':(d.get('evidence') or {}).get('repos',{}).get(name,{}).get('before',{}).get('head')}
        evidence = d.get('evidence') or {}
        expected = {(name,'docs') for name in eligible}
        for name, repo in eligible.items():
            expected.add((name,'unit'))
            for kind in ('setup','e2e'):
                if (repo.get(kind) or {}).get('cmd'): expected.add((name,kind))
            if repo.get('validation'): expected.add((name,'validation'))
        actual = {(r['repo'],r['kind']) for r in results}
        source = evidence.get('source',{})
        stable = True
        for name, repo in eligible.items():
            pair = evidence.get('repos',{}).get(name,{})
            before,after = pair.get('before',{}),pair.get('after',{})
            if not before.get('head') or before.get('dirty') is not False or before != after or after != current[name]:
                stable = False
        if results and expected and evidence.get('schema_version') == 1 and evidence.get('manifest',{}).get('sha256') == digest and \
            source.get('head') and source.get('dirty') is False and stable and \
            not evidence.get('collection_errors') and set(names) == set(eligible) and actual == expected and not failed and \
            evidence.get('selection',{}).get('only') is None and \
            evidence.get('selection',{}).get('tiers') == ['unit','e2e'] and \
            set(evidence.get('selection',{}).get('repos',[])) == set(eligible):
            candidates.append({'when':when,'total':len(results),'source_head':source['head']})
    verdict = 'never-run' if latest['verdict']=='never-run' else 'UNVERIFIED'
    # No age/coverage policy is silently adopted. Candidates remain separate.
    output = {'verdict':verdict,'when':latest['when'],'total':latest['total'],'failed':latest['failed'],
            'latest_run':latest,'per_repo':per_repo,'fleet_candidate':candidates[-1] if candidates else None,
            'policy':'pending owner decision','receipt_errors':errors}
    if policy is not None:
        evaluation=evaluate_fleet(output,ci or {},policy,now)
        output.update(verdict=evaluation['verdict'],policy=evaluation)
    return output


def monitors():
    st = {}
    p = HERE / "logs" / "ci-state.json"
    if p.exists():
        try:
            st = json.loads(p.read_text())
        except (OSError, ValueError):
            pass
    names = [r['name'] for r in json.loads(MANIFEST.read_text())['repos'] if r.get('status') != 'planned']
    st = normalize_state(st,names)
    return {'attempted':st.get('attempted') or 'never','verified':st.get('verified') or 'never',
            'repos_watched':len(st['repos']),
            'repos_verified':sum(bool(r.get('verified')) and r.get('state')!='unknown' for r in st['repos'].values()),
            'unknown':sum(r.get('state')=='unknown' for r in st['repos'].values())}


def html(data):
    def dot(ok, neutral=False):
        cls = "y" if neutral or ok is None else ("g" if ok else "r")
        return f'<span class="d {cls}"></span>'
    svc = "".join(f"<tr><td>{dot(ok)}</td><td>{escape(n)}</td><td class=m>{escape(detail)}</td></tr>"
                  for n, detail, ok in data["services"])
    ci = data.get('ci_evidence',{})
    def ci_detail(name,state):
        row = ci.get(name,{})
        suffix = f" · {row['when']} · {str(row.get('head') or 'unknown')[:12]}" if row.get('when') else ''
        return escape(state+suffix)
    repos = "".join(
        f'<tr><td>{dot(ok, neutral=state in ("running", "queued"))}</td>'
        f'<td><a href="{escape(url,quote=True)}" target="_blank">{escape(n)}</a></td>'
        f"<td>{ci_detail(n,state)}</td></tr>" if url else
        f'<tr><td>{dot(ok, neutral=state in ("running", "queued"))}</td>'
        f'<td>{escape(n)}</td><td>{ci_detail(n,state)}</td></tr>'
        for n, state, url, ok in data["repos"])
    q = data["qa"]
    mon = data["monitors"]
    latest = q.get('latest_run',{})
    scope = ', '.join(latest.get('repos',[])) or 'none'
    tiers = ', '.join(latest.get('checks',[])) or 'none'
    policy_detail = q.get('policy','unknown')
    if isinstance(policy_detail,dict):
        policy_detail = ' · '.join(policy_detail.get('reasons',[])) or f"{policy_detail['mode']} · max {policy_detail['max_age_hours']}h"
    repo_qa = ''.join(f"<tr><td>{dot(False if row['verdict']=='FAIL' else None)}</td><td>{escape(name)}</td><td>{escape(row['verdict'])} · {escape(', '.join(row['checks']))} · {escape(row['when'])}</td></tr>" for name,row in q.get('per_repo',{}).items())
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Legume Labs fleet health</title><meta http-equiv="refresh" content="300">
<style>body{{font-family:-apple-system,sans-serif;background:#0f1216;color:#e6e8eb;
margin:0;padding:24px}}h1{{font-size:1.3rem}} h2{{font-size:1rem;margin:22px 0 8px;
color:#9aa4af;text-transform:uppercase;letter-spacing:.08em;font-size:.75rem}}
table{{border-collapse:collapse;width:100%;max-width:720px}} td{{padding:6px 10px;
border-bottom:1px solid #232a33}} .m{{color:#667085}} .d{{display:inline-block;
width:10px;height:10px;border-radius:50%}} .g{{background:#34d399}} .r{{background:#f87171}} .y{{background:#fbbf24}}
a{{color:#7dd3fc;text-decoration:none}} .sub{{color:#667085;font-size:.85rem}}</style></head><body>
<h1>Legume Labs fleet health</h1>
<p class="sub"><a href="https://github.com/stevekkall-beansgc/qa-kit/blob/main/STANDARDS.md">Standards & maintenance loops</a> · this pane regenerates every 15 min</p>
<p class="sub">generated {data['generated']} · refreshes every 5 min</p>
<h2>services</h2><table>{svc}</table>
<h2>repositories · latest main-branch run</h2><table>{repos}</table>
<h2>qa evidence</h2><table>
<tr><td>{dot(True if q['verdict']=='PASS' else None)}</td><td>fleet baseline</td><td class=m>{escape(q['verdict'])} · {escape(policy_detail)}</td></tr>
<tr><td>{dot(False if latest.get('verdict')=='FAIL' else None)}</td><td>latest scoped run</td><td class=m>
{escape(latest.get('verdict',q['verdict']))} · {q['total']} checks · {escape(q['when'])} · repos: {escape(scope)} · checks: {escape(tiers)}</td></tr>
<tr><td>{dot(None)}</td><td>ci monitor</td><td class=m>
{mon['repos_watched']} registered · {mon['repos_verified']} verified · {mon['unknown']} unknown · attempted {escape(mon['attempted'])} · coverage verified {escape(mon['verified'])}</td></tr>
</table><h2>latest QA by repository · scoped evidence</h2><table>{repo_qa}</table></body></html>"""


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ci = ci_evidence()
    policy = load_policy() or {}
    data = {
        "schema_version": 2,
        "contract_version": CONTRACT_VERSION,
        "generated": now,
        "services": services() + backups(),
        "repos": [(name,row['state'],row['url'],row['ok']) for name,row in ci.items()],
        "ci_evidence":ci,
        "qa": qa_baseline(policy=policy.get('fleet'),ci=ci),
        "monitors": monitors(),
    }
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / "index.html").write_text(html(data))
    (PUBLIC / "health.json").write_text(json.dumps(data, indent=2))
    print(f"health dashboard -> {PUBLIC}/index.html "
          f"({sum(1 for *_ , ok in data['repos'] if ok)}/{len(data['repos'])} repos ok, "
          f"{sum(1 for *_ , ok in data['services'] if ok)}/{len(data['services'])} services up)")


if __name__ == "__main__":
    main()
