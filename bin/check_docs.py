#!/usr/bin/env python3
"""check_docs.py — enforce the BeanLabs docs standard (v1).

Every active repo must carry a human wiki (README.md mentioning its agent
wiki) and an agent wiki (AGENTS.md following the agents.md convention with
a `## Test commands` section that matches the qa-kit manifest entrypoint).

Exit 0 iff all active repos pass. Stdlib only.
"""
import json
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"


def expand(p):
    return Path(p).expanduser()


def check(repo, root_override=None):
    root = root_override or expand(repo["path"])
    problems = []
    readme = root / "README.md"
    agents = root / "AGENTS.md"
    if not agents.exists():
        return [f"missing AGENTS.md (agents.md convention)"]
    ag = agents.read_text()
    if "## Test commands" not in ag:
        problems.append("AGENTS.md lacks '## Test commands' section")
    unit = repo.get("unit", {})
    cmd = unit.get("cmd")
    if cmd and " ".join(cmd) not in ag.replace("  ", " ").replace("`", ""):
        problems.append(f"AGENTS.md does not state the manifest unit cmd: {' '.join(cmd)}")
    if not readme.exists():
        problems.append("missing README.md")
    else:
        rd = readme.read_text()
        if "AGENTS.md" not in rd:
            problems.append("README.md does not point to AGENTS.md")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-only", action="store_true",
                    help="validate this checkout only; for isolated CI runners")
    args = ap.parse_args()
    man = json.loads(MANIFEST.read_text())
    failures = []
    checked = 0
    for repo in man["repos"]:
        if repo.get("status") == "planned":
            continue
        if args.self_only and repo.get("name") != "qa-kit":
            continue
        checked += 1
        problems = check(repo, HERE if args.self_only else None)
        mark = "PASS" if not problems else "FAIL"
        print(f"  [{mark}] {repo['name']}")
        for p in problems:
            print(f"         - {p}")
            failures.append((repo["name"], p))
    print(f"\ndocs standard: {checked - len(failures)}/{checked} repos conform")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
