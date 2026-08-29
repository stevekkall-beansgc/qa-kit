#!/usr/bin/env python3
"""check_standards.py — keep STANDARDS.md honest.

Enforces the kernel-file discipline:
  1. Every relative link resolves on disk.
  2. Every kernel line (a ** bold lead in the kernels section) links out
     — a kernel without a pointer is duplication waiting to rot.
  3. Code anchors referenced by kernels still exist (grep-level): if the
     symbol/file moved, the kernel is stale and this fails.

Exit 1 lists violations. Runs in qa-kit's own gate and the weekly
reconciler job.
"""
import re
import argparse
import sys
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
STANDARDS = HERE / "STANDARDS.md"


def workspace_root() -> Path:
    """Return the canonical Bean Labs root used for cross-repo references."""
    return Path(os.environ.get("BEAN_WORKSPACE_ROOT", str(Path.home() / "beans"))).expanduser()


def resolve_target(rel: str) -> Path:
    """Resolve a local link, falling back to the canonical workspace layout.

    Isolated repo worktrees do not contain sibling repositories, but the
    standards kernel intentionally links to those siblings. Keep local links
    authoritative when available and make isolated checks deterministic by
    resolving the same relative path from the canonical qa-kit location.
    """
    local = (HERE / rel).resolve()
    if local.exists():
        return local
    return (workspace_root() / "platform" / "qa-kit" / rel).resolve()

# kernel -> anchor that must exist for the kernel to be true
ANCHORS = {
    "Review contract": ("README.md", "regression test"),
    "Docs standard v1": ("bin/check_docs.py", "AGENTS.md"),
    "Registry law": ("manifest.json", '"repos"'),
    "Gate semantics": ("../gate-kit/bin/compliance.py", "advisory"),
    "Release standard v1": ("../agency/docs/RELEASE-STANDARD.md", None),
    "State machine truth": ("../agency/server/db.py", "TASK_TRANSITIONS"),
    "Surface contracts": ("../agency/contracts/CONTRACTS.md", "CONTRACT_VERSION"),
    "Layout law (ADR 0005)": ("../../mind/beanmind/scripts/check_layout.py", None),
    "Honesty rule (product)": ("../../products/beanfit/AGENTS.md", "never guess"),
    "Health pane": ("bin/health.py", "fleet"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-only", action="store_true",
                    help="verify only anchors available in this isolated checkout")
    args = ap.parse_args()
    problems = []
    s = STANDARDS.read_text()

    # 1. relative links resolve
    for m in re.finditer(r"\]\(([^)#h][^)]*)\)", s):
        target = resolve_target(m.group(1))
        if not target.exists():
            problems.append(f"broken link: {m.group(1)}")

    # 2. kernel discipline: bold-led lines in kernels section must link out
    in_kernels = False
    for line in s.splitlines():
        if line.startswith("## Standards kernels"):
            in_kernels = True
            continue
        if in_kernels and line.startswith("## "):
            in_kernels = False
        if in_kernels and line.startswith("**") and "→" not in line:
            problems.append(f"kernel without link-out: {line[:60]}")

    # 3. anchors still exist (drift catcher)
    anchors = ANCHORS
    if args.self_only:
        anchors = {k: v for k, v in ANCHORS.items()
                   if not v[0].startswith("../") and not v[0].startswith("../../")}
    for kernel, (rel, needle) in anchors.items():
        target = resolve_target(rel)
        if not target.exists():
            problems.append(f"kernel '{kernel}': target missing: {rel}")
        elif needle and needle not in target.read_text(errors="ignore"):
            problems.append(f"kernel '{kernel}': anchor '{needle}' not found in {rel}")

    if problems:
        print(f"STANDARDS.md violations ({len(problems)}):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"STANDARDS.md ok — {len(anchors)} kernel anchors verified")


if __name__ == "__main__":
    main()
