#!/usr/bin/env bash
# qa-kit self-check: docs standard + standards kernels. One entrypoint for
# manifest/CI/AGENTS — run from repo root.
set -e
cd "$(dirname "$0")/.."
if [[ "${CI:-}" == "true" ]]; then
  python3 bin/check_docs.py --self-only
  python3 bin/check_standards.py --self-only
else
  python3 bin/check_docs.py
  python3 bin/check_standards.py
fi
