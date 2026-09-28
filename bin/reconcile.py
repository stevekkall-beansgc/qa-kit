#!/usr/bin/env python3
"""reconcile.py — registry drift catcher for Legume Labs.

Enumerates git repos actually on disk (beans layout + known legacy paths),
then diffs against BOTH registries: this manifest and agency's repos.json.

Fails (exit 1) on:
  - a live repo missing from either registry     -> registration drift
  - a manifest/repos.json row pointing at a dead path
Archived disk-only storage adds no test requirements. Registered dormant
exemptions require explicit policy; unreadable registries fail closed.

`--fix` appends stub manifest rows (status=planned, gap=auto-detected) for
unregistered disk repos so humans/agents graduate them on next touch.
Designed to run unattended via bean-sched; stdout is the audit trail.
"""
import json
import sys
from pathlib import Path
from reporting import common_identity

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


def registry_drift(qa, agency, disk, path_exists=None, exemptions=None):
    """Each live row belongs in each registry; archive storage adds no tests."""
    path_exists = path_exists or (lambda p: expand(p).exists())
    problems, unregistered = [], []
    exemptions = exemptions or {}
    registries = [('QA', qa), ('Agency', agency)]
    maps = {}
    identities = {}
    cached = {}
    def common(path):
        if path not in cached:
            cached[path] = common_identity(path)
        return cached[path]
    for label, rows in registries:
        mapping = {}
        for row in rows:
            name = row['name']; path = str(expand(row['path']))
            if name in mapping:
                problems.append(f'{label} duplicate name: {name}')
            mapping[name] = path
            if not path_exists(path):
                problems.append(f'{label} row {name} path missing: {path}')
        maps[label] = mapping
        identities[label] = {value for p in mapping.values() if (value := common(p)) is not None}
    for name in set(maps['QA']) & set(maps['Agency']):
        if maps['QA'][name] != maps['Agency'][name]:
            problems.append(f'registry path mismatch: {name}')
    for label, rows in registries:
        other = 'Agency' if label == 'QA' else 'QA'
        for row in rows:
            if row['name'] not in maps[other]:
                exempt = exemptions.get(row['name'])
                if label == 'Agency' and isinstance(exempt,dict) and row.get('archived') is True and \
                    str(expand(row['path'])) == str(expand(exempt['path'])) and 'archive' in expand(row['path']).parts:
                    continue
                problems.append(f'{other} missing row: {row["name"]} (present in {label})')
    for path, name in disk.items():
        # Deliberately archived assets do not acquire validation requirements.
        if 'archive' in Path(path).parts:
            continue
        source = common(path)
        missing = [label for label in maps if path not in maps[label].values()
                   and (source is None or source not in identities[label])]
        if missing:
            problems.append(f'repo on disk missing from {" and ".join(missing)}: {path}')
            if 'QA' in missing:
                unregistered.append((path, name))
    return problems, unregistered


def read_registry(path):
    data = json.loads(path.read_text())
    rows = data.get('repos') if isinstance(data, dict) else None
    if not isinstance(rows, list) or any(not isinstance(r, dict) or
        not isinstance(r.get('name'), str) or not isinstance(r.get('path'), str) for r in rows):
        raise ValueError('expected repos list with name/path rows')
    return data


def read_exemptions(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data,dict) or data.get('schema_version') != 1 or not isinstance(data.get('registry'),dict):
        raise ValueError('invalid reporting exemption policy')
    rows = data['registry'].get('archived_exemptions')
    if not isinstance(rows,list) or any(not isinstance(r,dict) or
        any(not isinstance(r.get(k),str) or not r[k] for k in ('name','path','owner')) or
        'archive' not in expand(r['path']).parts for r in rows):
        raise ValueError('invalid archived exemption identity')
    if len({r['name'] for r in rows}) != len(rows):
        raise ValueError('duplicate archived exemption')
    return {r['name']:r for r in rows}


def main():
    fix = "--fix" in sys.argv
    try:
        man = read_registry(MANIFEST)
    except (OSError, ValueError) as exc:
        print(f'DRIFT: unreadable QA registry: {type(exc).__name__}')
        sys.exit(1)

    repos_json_path = BEANS / "platform" / "agency" / "repos.json"
    if not repos_json_path.exists():
        if LEGACY:
            repos_json_path = LEGACY[-1] / "repos.json"
    try:
        other = read_registry(repos_json_path)
    except (OSError, ValueError) as exc:
        print(f'DRIFT: unreadable Agency registry: {type(exc).__name__}; no automatic changes')
        sys.exit(1)
    try:
        exemptions = read_exemptions(HERE/'reporting-policy.json')
    except (OSError,ValueError) as exc:
        print(f'DRIFT: unreadable/malformed exemption policy: {type(exc).__name__}; no automatic changes')
        sys.exit(1)
    disk = disk_repos()
    problems, unregistered = registry_drift(man['repos'], other['repos'], disk, exemptions=exemptions)
    if fix:
        for path, name in unregistered:
            if any(row['name'] == name for row in man['repos']):
                continue
            man["repos"].append({
                "name": name, "path": str(path).replace(str(Path.home()), "~"),
                "tier": "C", "status": "planned",
                "gap": "auto-detected by reconcile.py --fix; needs entrypoints + review",
            })

    print(f"disk repos scanned: {len(disk)}; manifest: {len(man['repos'])} rows")
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
