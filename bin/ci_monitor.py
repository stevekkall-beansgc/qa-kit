#!/usr/bin/env python3
"""ci_monitor.py — watch GitHub Actions across every registered repo.

For each manifest repo WITH a remote: list recent runs on main; flag any
newly observed failed run attempt, following unfinished runs until completion.
State lives in qa-kit/logs/ci-state.json so repeated polls deduplicate failures
by run identity and attempt, independent of creation/completion order.
Separates query coverage from test verdicts. Local-only/no-runs states are
known observations, never successful CI. Auth/API/schema failures are unknown.

Exit 0 = queries verified and nothing new failed. Exit 1 = query uncertainty or
at least one new failure (designed to land as a FAIL row on the bean-sched board).

Auth: uses local `gh`. Stdlib only.
"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from reporting import normalize_state, repo_remote, valid_runs, ci_verdict

import shutil
GH_BIN = shutil.which("gh") or "/opt/homebrew/bin/gh"  # launchd PATH lacks homebrew

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"
STATE = HERE / "logs" / "ci-state.json"
OWNER = "stevekkall-beansgc"
RUN_FIELDS = "databaseId,attempt,workflowName,conclusion,displayTitle,createdAt,url,status"


def expand(p):
    return Path(p).expanduser()


def gh(args):
    try:
        p = subprocess.run([GH_BIN, *args], capture_output=True, text=True,
                           timeout=30)
        return p.returncode, p.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def main():
    man = json.loads(MANIFEST.read_text())
    auth_rc, auth_out = gh(["auth", "status"])
    auth_verified = auth_rc == 0
    raw = {}
    if STATE.exists():
        try:
            raw = json.loads(STATE.read_text())
        except (OSError, ValueError):
            pass
    eligible = [r for r in man['repos'] if r.get('status') != 'planned']
    wrapper = normalize_state(raw, [r['name'] for r in eligible])
    state = wrapper['repos']
    stamp = datetime.now(timezone.utc).isoformat()
    wrapper['attempted'] = stamp

    new_failures = []
    infos = []
    query_failures = []
    if not auth_verified:
        query_failures.append('GitHub auth check failed; coverage unknown')
    for repo in eligible:
        name = repo["name"]
        seen = state[name]
        seen['attempted'] = stamp
        seen['state'] = 'unknown'
        if not auth_verified:
            continue
        remote_state, _ = repo_remote(repo['path'])
        if remote_state == 'unknown':
            query_failures.append(f'{name}: repository/remote unavailable')
            continue
        if remote_state == 'local-only':
            infos.append(f"{name}: no remote configured (local-only)")
            seen['state'] = 'local-only'
            seen['verified'] = stamp
            continue

        gh_name = repo.get("github", name)
        rc, out = gh(["run", "list", "--repo", f"{OWNER}/{gh_name}",
                      "--branch", "main", "--limit", "8",
                      "--json", RUN_FIELDS])
        if rc != 0:
            infos.append(f"{name}: gh query failed; coverage unknown")
            query_failures.append(name)
            continue
        try:
            runs = json.loads(out)
        except (TypeError, ValueError):
            runs = None
        if not valid_runs(runs, monitor=True):
            query_failures.append(f'{name}: malformed/unavailable run response')
            continue
        recent_state, _, _ = ci_verdict(runs)
        observed = seen['runs']
        listed_ids = {str(r['databaseId']) for r in runs}
        pending_query_failed = False
        # A busy repository may push an unfinished run out of the recent eight.
        # Keep following that identity rather than silently dropping its result.
        for run_id, previous in observed.items():
            if previous['conclusion'] or run_id in listed_ids:
                continue
            rc, out = gh(['run', 'view', run_id, '--repo', f'{OWNER}/{gh_name}',
                          '--json', RUN_FIELDS])
            try:
                pending = json.loads(out) if rc == 0 else None
            except (TypeError, ValueError):
                pending = None
            if not valid_runs([pending], monitor=True) or str(pending['databaseId']) != run_id:
                query_failures.append(f'{name}: pending run {run_id} unavailable/malformed')
                pending_query_failed = True
                continue
            runs.append(pending)
        if not pending_query_failed:
            seen['state'] = recent_state
            seen['verified'] = stamp
        for r in sorted(runs, key=lambda x: x["databaseId"]):
            run_id = str(r['databaseId'])
            previous = observed.get(run_id)
            # A retry reuses the run ID, while stale responses must not rewind it.
            if previous and (r['attempt'] < previous['attempt'] or (
                    r['attempt'] == previous['attempt'] and previous['conclusion'])):
                continue
            terminal = (not r.get('status') or r['status'] == 'completed') and bool(r['conclusion'])
            observed[run_id] = {'attempt': r['attempt'],
                                'conclusion': r['conclusion'] if terminal else ''}
            if not terminal:
                continue
            if r["conclusion"] == "failure":
                new_failures.append({
                    "repo": name, "run_id": r["databaseId"],
                    "attempt": r['attempt'],
                    "workflow": r.get("workflowName"), "title": str(r.get("displayTitle",''))[:90],
                    "url": r.get("url"),
                })
            # Retain the old field for readers, but never use it for deduplication.
            seen['last_run_id'] = max(r['databaseId'], seen['last_run_id'])

    if auth_verified and not query_failures:
        wrapper['verified'] = stamp
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=STATE.parent,prefix='.ci-state-',delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(wrapper, indent=2))
    try:
        temporary.replace(STATE)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"== CI monitor {stamp} ==")
    if infos:
        print("INFO:")
        for i in infos:
            print(f"  - {i}")
    if query_failures:
        print(f"\nMONITOR FAILURE (auth_verified={str(auth_verified).lower()}):")
        for failure in query_failures:
            print(f"  ✗ {failure}")
    if new_failures:
        print(f"\nNEW FAILURES ({len(new_failures)}):")
        for f in new_failures:
            print(f"  ✗ [{f['repo']}] {f['workflow']}: {f['title']} (attempt {f['attempt']})")
            print(f"      {f['url']}")
        print("auth_verified=true")
    if query_failures or new_failures:
        sys.exit(1)
    print("query coverage verified — auth_verified=true; no new failures since last sweep; this is not a fleet CI pass")


if __name__ == "__main__":
    main()
