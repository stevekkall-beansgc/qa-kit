#!/usr/bin/env python3
"""Check opt-in validation parity contracts without running repository commands.

V1 deliberately supports one small, completely rendered hosted workflow. Comparing
the whole file avoids pretending to parse arbitrary YAML with regular expressions.
Existing workflows need review before adoption; the checker never rewrites them.
"""
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path


CONTRACT = ".qa/validation.json"
INTERPRETERS = {"bash", "sh", "python3", "node"}


def owned_file(root, name):
    """Require a regular repository file, with no symlink traversal."""
    path = Path(name)
    if path.is_absolute() or not path.parts or name.startswith("-") or any(p in {".", ".."} for p in path.parts):
        raise ValueError("contract paths must be relative repository files")
    target = root / path
    if any((root / Path(*path.parts[:i])).is_symlink()
           for i in range(1, len(path.parts) + 1)):
        raise ValueError("contract paths must not traverse symlinks")
    if not target.is_file():
        raise ValueError(f"required file missing: {name}")
    return target


def load_contract(root):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate contract key: {key}")
            result[key] = value
        return result

    spec = json.loads(owned_file(root, CONTRACT).read_text(), object_pairs_hook=unique)
    keys = {"version", "command", "workflow", "workflow_name", "job_id", "runtimes"}
    if not isinstance(spec, dict) or set(spec) != keys or type(spec["version"]) is not int or spec["version"] != 1:
        raise ValueError("expected validation contract v1 with exactly the documented fields")
    cmd = spec["command"]
    if (not isinstance(cmd, list) or len(cmd) < 2
            or any(not isinstance(arg, str) or not arg or any(c in arg for c in "\n\r\x00") or "${{" in arg for arg in cmd)
            or cmd[0] not in INTERPRETERS):
        raise ValueError("command must invoke bash, sh, python3 or node with a repo-owned script")
    owned_file(root, cmd[1])
    if not isinstance(spec["workflow"], str) or not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", spec["workflow"]):
        raise ValueError("workflow must name one file under .github/workflows")
    for field in ("workflow_name", "job_id"):
        if not isinstance(spec[field], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", spec[field]):
            raise ValueError(f"invalid {field}")
    runtimes = spec["runtimes"]
    if not isinstance(runtimes, dict) or not runtimes or set(runtimes) - {"python", "node"}:
        raise ValueError("runtimes must declare python and/or node")
    for name, version in runtimes.items():
        pattern = r"3\.[0-9]+" if name == "python" else r"[1-9][0-9]*"
        if not isinstance(version, str) or not re.fullmatch(pattern, version):
            raise ValueError(f"invalid {name} runtime pin")
    needed = {"python3": "python", "node": "node"}.get(cmd[0])
    if needed and needed not in runtimes:
        raise ValueError("entrypoint interpreter must have a runtime pin")
    return spec


def render_workflow(spec):
    """The reviewed, intentionally narrow v1 hosted adapter; no repo test bodies."""
    lines = [
        "# Generated from .qa/validation.json by qa-kit; review contract and workflow together.",
        "name: " + json.dumps(spec["workflow_name"]),
        "on:", "  push:", "    branches: [main]", "  pull_request:",
        "permissions:", "  contents: read", "jobs:",
        "  " + json.dumps(spec["job_id"]) + ":", "    runs-on: ubuntu-latest", "    timeout-minutes: 15",
        "    steps:",
        "      - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5",
        "        with:", "          persist-credentials: false",
    ]
    if "python" in spec["runtimes"]:
        lines += [
            "      - uses: actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c # v6",
            "        with:", f"          python-version: \"{spec['runtimes']['python']}\"",
        ]
    if "node" in spec["runtimes"]:
        lines += [
            "      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4",
            "        with:", f"          node-version: \"{spec['runtimes']['node']}\"",
        ]
    # A quoted scalar avoids YAML interpreting colons, hashes or booleans in argv.
    lines += ["      - name: Repository validation", "        shell: bash",
              "        working-directory: .",
              "        run: " + json.dumps(shlex.join(spec["command"]))]
    return "\n".join(lines) + "\n"


def check_runtimes(spec):
    issues = []
    for runtime, expected in spec["runtimes"].items():
        binary = "python3" if runtime == "python" else "node"
        try:
            proc = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            issues.append(f"{runtime}: runtime unavailable")
            continue
        match = re.fullmatch(r"Python (\d+\.\d+)\.\d+", proc.stdout.strip()) if runtime == "python" else re.fullmatch(r"v(\d+)\.\d+\.\d+", proc.stdout.strip())
        if proc.returncode or not match or match[1] != expected:
            issues.append(f"{runtime}: expected {expected}; prepare the declared runtime before validation")
    return issues


def check(repo, root_override=None, runtime=False):
    """Only explicit registrations adopt v1; malformed registrations fail closed."""
    if "validation" not in repo:
        return []
    if repo["validation"] != {"contract": CONTRACT}:
        return [f"validation registration must be {{'contract': '{CONTRACT}'}}"]
    try:
        root = Path(root_override if root_override is not None else repo["path"]).expanduser()
        spec = load_contract(root)
        issues = []
        unit = repo.get("unit") or {}
        setup = repo.get("setup") or {}
        if not isinstance(unit, dict) or not isinstance(setup, dict):
            raise ValueError("manifest unit/setup entries must be objects")
        if unit.get("cmd") != spec["command"]:
            issues.append("manifest unit command differs from validation contract")
        if unit.get("env") or setup.get("cmd"):
            issues.append("v1 requires setup and environment normalization inside the shared entrypoint")
        if owned_file(root, spec["workflow"]).read_text() != render_workflow(spec):
            issues.append("workflow differs from the contract's hosted adapter; regenerate and review")
        if runtime:
            issues += check_runtimes(spec)
        return issues
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return [f"invalid validation contract: {exc}"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repo")
    parser.add_argument("--runtime", action="store_true", help="also verify local Python/Node versions")
    parser.add_argument("--emit-workflow", action="store_true", help="print the adapter to stdout; never writes files")
    args = parser.parse_args()
    if args.emit_workflow:
        try:
            print(render_workflow(load_contract(args.root)), end="")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            parser.exit(2, f"validation error: {exc}\n")
        return
    if not args.manifest or not args.repo:
        parser.error("--manifest and --repo are required for checking")
    try:
        rows = json.loads(args.manifest.read_text())["repos"]
        matches = [row for row in rows if row["name"] == args.repo]
        if len(matches) != 1 or "validation" not in matches[0]:
            raise ValueError("select exactly one explicitly adopted repository")
        issues = check(matches[0], args.root, runtime=args.runtime)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"validation error: {exc}\n")
    for issue in issues:
        print(issue)
    if not issues:
        print("validation parity contract OK" + (" (runtime checked)" if args.runtime else " (static only)"))
    raise SystemExit(bool(issues))


if __name__ == "__main__":
    main()
