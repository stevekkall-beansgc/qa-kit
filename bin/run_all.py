#!/usr/bin/env python3
"""qa-kit run_all.py — BeanLabs central QA orchestrator.

Runs the unit/e2e entrypoints declared in manifest.json, one repo at a
time, and reports a single aggregate verdict. Test BODIES live in their
owning repos; this script only sequences them and records results.

Usage:
  run_all.py                # unit tier, all active repos
  run_all.py --e2e          # e2e tier
  run_all.py --all          # unit then e2e
  run_all.py --only beanfit-app [--e2e]

Stdlib only. Results appended to logs/run-<utcstamp>.json.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"
LOGS = HERE / "logs"
TIMEOUT_SECS = 900


def load_manifest():
    return json.loads(MANIFEST.read_text())


def expand(path):
    return Path(path).expanduser()


def run_repo(repo, kind):
    spec = repo.get(kind)
    if not spec or not spec.get("cmd"):
        return None
    cwd = expand(repo["path"])
    env = None
    if spec.get("env"):
        import os
        env = dict(os.environ)
        for k, v in spec["env"].items():
            # Relative paths (e.g. PYTHONPATH=src) resolve against the repo.
            env[k] = str(cwd / v) if not v.startswith("/") else v
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            spec["cmd"], cwd=str(cwd), env=env,
            capture_output=True, text=True, timeout=TIMEOUT_SECS,
        )
        ok, out = proc.returncode == 0, (proc.stdout + "\n" + proc.stderr)[-1200:]
    except subprocess.TimeoutExpired:
        ok, out = False, f"TIMEOUT after {TIMEOUT_SECS}s"
    except FileNotFoundError as e:
        ok, out = False, f"entrypoint missing: {e}"
    return {"repo": repo["name"], "kind": kind, "ok": ok,
            "secs": round(time.monotonic() - t0, 1), "tail": out.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--include-planned", action="store_true",
                    help="list planned/gap repos instead of skipping silently")
    args = ap.parse_args()

    kinds = ["unit", "e2e"] if args.all else (["e2e"] if args.e2e else ["unit"])
    man = load_manifest()
    results, skipped = [], []
    for repo in man["repos"]:
        if args.only and repo["name"] != args.only:
            continue
        if repo.get("status") == "planned":
            skipped.append({"repo": repo["name"],
                            "gap": repo.get("gap", "no entrypoint registered")})
            continue
        for kind in kinds:
            r = run_repo(repo, kind)
            if r:
                results.append(r)

    failed = [r for r in results if not r["ok"]]
    print("\n== qa-kit report ==")
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"  [{mark}] {r['repo']:<14} {r['kind']:<4} {r['secs']:>6}s")
        if not r["ok"]:
            print("         " + r["tail"][-500:].replace("\n", "\n         "))
    if args.include_planned and skipped:
        print("  PLANNED (no baseline yet):")
        for s in skipped:
            print(f"    - {s['repo']}: {s['gap']}")
    print(f"\n{len(results) - len(failed)}/{len(results)} passed"
          + (f" · {len(skipped)} planned" if skipped else ""))

    LOGS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (LOGS / f"run-{stamp}.json").write_text(json.dumps(
        {"when": stamp, "results": results, "planned_skipped": skipped}, indent=2))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
