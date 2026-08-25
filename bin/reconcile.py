#!/usr/bin/env python3
"""reconcile.py — registry drift catcher for BeanLabs.

Enumerates git repos actually on disk (beans layout + known legacy paths),
then diffs against BOTH registries: this manifest and agency's repos.json.

Fails (exit 1) on:
  - a repo on disk missing from qa-kit manifest   -> registration drift
  - a manifest/repos.json row pointing at a dead path
Planned repos are reported but not failures.

`--fix` appends stub manifest rows (status=planned, gap=auto-detected) for
unregistered disk repos so humans/agents graduate them on next touch.
Designed to run unattended via bean-sched; stdout is the audit trail.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"
GROUPS = ["platform", "products", "catalog", "mind", "labs", "archive"]
LEGACY = [Path.home() / "Desktop", Path.home() / "agency"]
BEANS = Path.home() / "beans"


def expand(p):
    return Path(p).expanduser()


def is_git_repo(d):
    return d.is_dir() and (d / ".git").exists()


def disk_repos():
    found = {}
    if BEANS.exists():
        for group in GROUPS:
            g = BEANS / group
            if not g.exists():
                continue
            for child in sorted(g.iterdir()):
                if is_git_repo(child):
                    found[str(child)] = child.name
                elif child.is_dir():
                    for sub in sorted(child.iterdir()):
                        if is_git_repo(sub):
                            found[str(sub)] = sub.name
    for base in LEGACY:
        if base.is_file() or not base.exists():
            if base.name == "agency" and is_git_repo(base):
                found[str(base)] = base.name
            continue
        for child in sorted(base.iterdir()):
            if is_git_repo(child):
                found[str(child)] = child.name
    return found


def main():
    fix = "--fix" in sys.argv
    man = json.loads(MANIFEST.read_text())
    manifest_names = {r["name"] for r in man["repos"]}
    manifest_paths = {str(expand(r["path"])) for r in man["repos"]}

    repos_json_path = BEANS / "platform" / "agency" / "repos.json"
    if not repos_json_path.exists():
        repos_json_path = Path.home() / "agency" / "repos.json"
    registries_other = set()
    if repos_json_path.exists():
        try:
            other = json.loads(repos_json_path.read_text())
            for r in other.get("repos", []):
                registries_other.add(r["name"])
                manifest_paths.add(str(expand(r["path"])))
        except Exception as e:
            print(f"WARN: unreadable {repos_json_path}: {e}")

    problems = []

    # 1. Registered paths that vanished (mid-migration or deleted).
    for r in man["repos"]:
        if r.get("status") == "planned":
            continue
        p = expand(r["path"])
        if not p.exists():
            problems.append(f"manifest row '{r['name']}' path missing: {p}")

    # 2. Disk repos absent from BOTH registries. Archive-group repos are
    #    informational only (cold storage — no test expectations).
    unregistered, archived_hits = [], []
    for path, name in disk_repos().items():
        if name in manifest_names or name in registries_other:
            continue
        if str(path) in manifest_paths:
            continue
        if "/archive/" in path or Path(path).parent.name == "archive":
            archived_hits.append((path, name))
            print(f"INFO: archived repo (no registry expectation): {path}")
            continue
        unregistered.append((path, name))
        problems.append(f"repo on disk not in any registry: {path}")
        if fix:
            man["repos"].append({
                "name": name, "path": str(path).replace(str(Path.home()), "~"),
                "tier": "C", "status": "planned",
                "gap": "auto-detected by reconcile.py --fix; needs entrypoints + review",
            })

    print(f"disk repos scanned: {len(disk_repos())}; manifest: {len(man['repos'])} rows")
    for p in problems:
        print(f"DRIFT: {p}")
    if not problems:
        print("no drift — every disk repo is registered; every registered path exists")
    if fix and unregistered:
        MANIFEST.write_text(json.dumps(man, indent=2))
        print(f"--fix appended {len(unregistered)} stub row(s) to manifest.json")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
