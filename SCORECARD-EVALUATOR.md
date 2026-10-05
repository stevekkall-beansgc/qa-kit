# Offline scorecard evaluator slice

This module turns the candidate's nine Health examples into executable runtime
checks and provides a conservative Security status primitive. It is a library,
not an activated collector, official assessment, scanner, or Hub integration.

Source base: cec33d5e474f4ce26c1100b5c68501dafc55f5f8.
Tracking: https://github.com/stevekkall-beansgc/legume-labs-core/issues/17

## Contract

`bin/scorecard_evaluator.py` exports `health` and `security`. Neither function
reads files, accesses a network, executes a command, writes history, or changes
its input. Callers supply the existing candidate policy explicitly. The policy,
fleet dashboard, schedules, registry, and activation flags remain unchanged.

Health accepts reviewed integer 0–4/null category ratings and boolean evidence
completeness. An incomplete category must be null. Exact quarter-point arithmetic
is used before comparing thresholds. Blockers take precedence over missing
coverage. Bad shapes, boolean ratings, and unknown blocker names are refused.

Security accepts a reviewed nonempty required-producer list, exact commit and
scope, evaluation time, and an explicit positive freshness limit. It does not
silently activate the proposed 24-hour rule. Each normalized scan requires a
producer/version, commit/scope, source time, completed result, safe evidence
reference, and explicit findings list. Duplicate producer records are rejected
rather than selecting a favorable one. Errors, stale/future/mismatched records,
and missing producers prevent complete coverage. Findings from stale records
remain unresolved; critical blockers win over all other states. A successful
report-only job cannot suppress supplied findings. Native OpenSSF score remains
null because native individual-check ingestion is not implemented in this slice.

## Trust and limits

These functions validate supplied normalized inputs; they do not authenticate
receipts, infer category ratings, attest independent review, or prove actual
repository health. The caller must retain unresolved findings/blockers across
observations until verified clearance. There is no persistence or automatic
clearance mechanism here. Exception approval/expiry, producer-specific parsers,
carry-forward, revoked-evidence history, and the read-only Agency view remain
unfinished. Do not treat these primitives as completion of Core #17.

There is no CLI or new user-facing flow, and nothing is wired into `health.py`.
No scanner or baseline collection was executed. The original specification
fixtures remain labeled specifications; the new test imports the runtime module
and runs each of the nine examples against it.

## Verification, October 5, 2026

- Initial test run: one import error because the new module did not yet exist.
  This is a missing-module baseline, not 20 observed behavioral failures.
- Focused evaluator suite: 20 tests passed, including nine fixture subcases.
- Python 3.12.14 Linux: `CI=true bash bin/qa_selfcheck.sh` passed all 187 tests,
  docs/standards checks and three synthetic quickstart scenarios.
- `python3 scripts/check_stdlib.py bin/` passed (12 files).
- Task executable unavailable; the two commands of `task validate` were run
  directly under the required Python 3.12 interpreter.
- The cross-repository `run_all --only qa-kit --all` workspace gate, native Mac
  qualification, independent review, real pilot evidence, and Hub UI are unrun.

Inspect `evidence/scorecard-before.txt`, `scorecard-after.txt`, and
`scorecard-selfcheck.txt`. These are synthetic tests, not production scores.
