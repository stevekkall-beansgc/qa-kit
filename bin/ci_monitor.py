#!/usr/bin/env python3
"""ci_monitor.py — watch GitHub Actions across every registered repo.

For each manifest repo WITH a remote: list recent runs on main; flag any
conclusion=failure newer than the last-seen watermark. State lives in
qa-kit/logs/ci-state.json so repeated runs only surface NEW failures.
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
                      "--json", "databaseId,workflowName,conclusion,"
                      "displayTitle,createdAt,url,status"])
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
        seen['state'], _, _ = ci_verdict(runs)
        seen['verified'] = stamp
        last_id = seen.get("last_run_id", 0)
        for r in sorted(runs, key=lambda x: x["databaseId"]):
            if r.get('status') and r['status'] != 'completed':
                continue
            if not r['conclusion']:
                continue
            if r["databaseId"] <= last_id:
                continue
            if r["conclusion"] == "failure":
                new_failures.append({
                    "repo": name, "run_id": r["databaseId"],
                    "workflow": r.get("workflowName"), "title": str(r.get("displayTitle",''))[:90],
                    "url": r.get("url"),
                })
            state.setdefault(name, {})["last_run_id"] = max(
                r["databaseId"], state.get(name, {}).get("last_run_id", 0))

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
        sys.exit(1)
    if new_failures:
        print(f"\nNEW FAILURES ({len(new_failures)}):")
        for f in new_failures:
            print(f"  ✗ [{f['repo']}] {f['workflow']}: {f['title']}")
            print(f"      {f['url']}")
        print("auth_verified=true")
        sys.exit(1)
    print("query coverage verified — no new failures since last sweep; this is not a fleet CI pass")


if __name__ == "__main__":
    main()
