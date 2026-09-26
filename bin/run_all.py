#!/usr/bin/env python3
"""qa-kit run_all.py — Legume Labs central QA orchestrator.

Runs the unit/e2e entrypoints declared in manifest.json, one repo at a
time, and reports a single aggregate verdict. Repos that declare a `setup`
entrypoint get it executed before their unit/e2e tiers (once per repo);
a failing setup blocks that repo's tests and fails the run. Test BODIES
live in their owning repos; this script only sequences them and records
results.

Usage:
  run_all.py                # unit tier, all active repos
  run_all.py --e2e          # e2e tier
  run_all.py --all          # setup then unit then e2e
  run_all.py --only beanfit-app [--e2e]
  run_all.py --manifest PATH --logs-dir PATH --only gate-kit --all

Stdlib only. Each run writes a distinct logs/run-<utcstamp>[-N].json report (override with
--manifest for a different registry and --logs-dir for a different output
directory).
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


class QaKitError(Exception):
    """Clear, user-facing failure: printed once to stderr, exit code 2."""


def load_manifest(path=None):
    manifest = Path(path).expanduser() if path else MANIFEST
    if not manifest.exists():
        raise QaKitError(f"manifest not found: {manifest}")
    try:
        data = json.loads(manifest.read_text())
    except (OSError, UnicodeError) as exc:
        raise QaKitError(f"cannot read manifest {manifest}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise QaKitError(f"malformed manifest {manifest}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("repos"), list):
        raise QaKitError(f"manifest {manifest}: missing 'repos' list")
    return data


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


def check_docs(repo):
    """Docs standard v1: README + AGENTS.md present, sections consistent."""
    root = expand(repo["path"])
    ag = root / "AGENTS.md"
    rd = root / "README.md"
    t0 = time.monotonic()
    problems = []
    if not ag.exists():
        problems.append("missing AGENTS.md")
    else:
        ag_text = ag.read_text()
        if "## Test commands" not in ag_text:
            problems.append("AGENTS.md lacks Test commands section")
        cmd = (repo.get("unit") or {}).get("cmd")
        if cmd and " ".join(cmd) not in ag_text.replace("`", ""):
            problems.append("AGENTS.md does not state manifest unit cmd")
    if not rd.exists():
        problems.append("missing README.md")
    elif "AGENTS.md" not in rd.read_text():
        problems.append("README does not reference AGENTS.md")
    return {"repo": repo["name"], "kind": "docs", "ok": not problems,
            "secs": round(time.monotonic() - t0, 2),
            "tail": "; ".join(problems)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--include-planned", action="store_true",
                    help="list planned/gap repos instead of skipping silently")
    ap.add_argument("--manifest", default=None,
                    help="path to manifest.json (default: this repo's manifest)")
    ap.add_argument("--logs-dir", default=None,
                    help="directory for run-*.json reports (default: logs/)")
    args = ap.parse_args()

    kinds = ["unit", "e2e"] if args.all else (["e2e"] if args.e2e else ["unit"])
    manifest_path = expand(args.manifest) if args.manifest else MANIFEST
    logs_dir = expand(args.logs_dir) if args.logs_dir else LOGS
    try:
        man = load_manifest(manifest_path)
    except QaKitError as exc:
        print(f"qa-kit error: {exc}", file=sys.stderr)
        sys.exit(2)
    results, skipped = [], []
    for repo in man["repos"]:
        if args.only and repo["name"] != args.only:
            continue
        if repo.get("status") == "planned":
            skipped.append({"repo": repo["name"],
                            "gap": repo.get("gap", "no entrypoint registered")})
            continue
        results.append(check_docs(repo))
        runnable = [kind for kind in kinds if (repo.get(kind) or {}).get("cmd")]
        if (repo.get("setup") or {}).get("cmd") and runnable:
            stage = run_repo(repo, "setup")
            results.append(stage)
            if not stage["ok"]:
                for kind in runnable:
                    results.append({"repo": repo["name"], "kind": kind, "ok": False,
                                    "secs": 0, "tail": "skipped: setup failed"})
                continue
        for kind in kinds:
            r = run_repo(repo, kind)
            if r:
                results.append(r)
            elif kind == "unit":
                results.append({"repo": repo["name"], "kind": "unit", "ok": False,
                                "secs": 0, "tail": "no unit entrypoint registered"})

    if not any(r["kind"] in kinds for r in results):
        results.append({"repo": args.only or "selection", "kind": "selection", "ok": False,
                        "secs": 0, "tail": "zero test entrypoints selected; check --only, tier, and manifest status"})

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

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = json.dumps(
        {"when": stamp, "results": results, "planned_skipped": skipped}, indent=2)
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        base = logs_dir / f"run-{stamp}.json"
        candidate = base
        suffix = 0
        while True:
            try:
                with candidate.open("x", encoding="utf-8") as f:
                    f.write(payload)
                break
            except FileExistsError:
                suffix += 1
                if suffix > 999:
                    raise OSError(f"too many report collisions for {base}")
                candidate = logs_dir / f"run-{stamp}-{suffix}.json"
    except OSError as exc:
        print(f"qa-kit error: cannot write report to logs dir {logs_dir}: {exc}",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
