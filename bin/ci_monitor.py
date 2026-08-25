#!/usr/bin/env python3
"""ci_monitor.py — watch GitHub Actions across every registered repo.

For each manifest repo WITH a remote: list recent runs on main; flag any
conclusion=failure newer than the last-seen watermark. State lives in
qa-kit/logs/ci-state.json so repeated runs only surface NEW failures.
Also reports repos with no remote / no runs as INFO, not failures.

Exit 0 = nothing new failed. Exit 1 = at least one new failure since last
sweep (designed to land as a FAIL row on the bean-sched board).

Auth: uses local `gh`. Stdlib only.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"
STATE = HERE / "logs" / "ci-state.json"
OWNER = "stevekkall-beansgc"


def expand(p):
    return Path(p).expanduser()


def gh(args):
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True,
                           timeout=30)
        return p.returncode, p.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def main():
    man = json.loads(MANIFEST.read_text())
    state = {}
    if STATE.exists():
        try:
            wrapper = json.loads(STATE.read_text())
            state = wrapper.get("repos", {})
        except ValueError:
            state = {}

    new_failures = []
    infos = []
    for repo in man["repos"]:
        if repo.get("status") == "planned":
            continue
        name = repo["name"]
        remote = expand(repo["path"]) / ".git" / "config"
        if not remote.exists():
            infos.append(f"{name}: no git repo on disk")
            continue
        cfg = remote.read_text()
        if "origin" not in cfg:
            infos.append(f"{name}: no remote configured (local-only)")
            continue

        gh_name = repo.get("github", name)
        rc, out = gh(["run", "list", "--repo", f"{OWNER}/{gh_name}",
                      "--branch", "main", "--limit", "8",
                      "--json", "databaseId,workflowName,conclusion,"
                                "displayTitle,createdAt,url"])
        if rc != 0:
            infos.append(f"{name}: gh query failed ({out[:120]})")
            continue
        runs = json.loads(out or "[]")
        seen = state.get(name, {})
        last_id = seen.get("last_run_id", 0)
        for r in sorted(runs, key=lambda x: x["databaseId"]):
            if r["databaseId"] <= last_id:
                continue
            if r["conclusion"] == "failure":
                new_failures.append({
                    "repo": name, "run_id": r["databaseId"],
                    "workflow": r.get("workflowName"), "title": r["displayTitle"][:90],
                    "url": r.get("url"),
                })
            state.setdefault(name, {})["last_run_id"] = max(
                r["databaseId"], state.get(name, {}).get("last_run_id", 0))

    STATE.parent.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    STATE.write_text(json.dumps({"checked": stamp, "repos": state}, indent=2))

    print(f"== CI monitor {stamp} ==")
    if infos:
        print("INFO:")
        for i in infos:
            print(f"  - {i}")
    if new_failures:
        print(f"\nNEW FAILURES ({len(new_failures)}):")
        for f in new_failures:
            print(f"  ✗ [{f['repo']}] {f['workflow']}: {f['title']}")
            print(f"      {f['url']}")
        sys.exit(1)
    print("all green — no new failures since last sweep")


if __name__ == "__main__":
    main()
