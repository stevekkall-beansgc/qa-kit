#!/usr/bin/env bash
# qa-kit self-check: docs standard + standards kernels. One entrypoint for
# manifest/CI/AGENTS — run from repo root.
set -e
cd "$(dirname "$0")/.."
python3 bin/check_docs.py
python3 bin/check_standards.py
