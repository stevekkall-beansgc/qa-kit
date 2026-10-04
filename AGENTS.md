# AGENTS.md — qa-kit


> **Entry point for all standards:** [STANDARDS.md](STANDARDS.md)

Central QA orchestration. Test bodies live in the repos that own the code;
this repo registers entrypoints, runs them uniformly, records verdicts.

## Layout
- `manifest.json` — THE registry: repo → tier → unit/e2e entrypoints →
  status (`active` / `unit-only` / `planned` + named gap).
- `bin/run_all.py` — stdlib orchestrator (`--unit/--e2e/--all/--only/
  --include-planned`), writes `logs/run-<stamp>.json`.
- `bin/check_docs.py` — docs standard validator (README + AGENTS.md per
  active repo, section + command consistency).
- `bin/validation.py` — opt-in shared task/variant planner and executor; protocol
  and trust boundary in `VALIDATION-EXECUTOR.md`. Empty default registry;
  enrollment, trusted controls and qualified adapters are separate rollout steps.
- `FLEET-VALIDATION-DESIGN.md` — review-only composable profile/capability design,
  ownership, authorization, evidence and rollout gates; not an executable schema.
- `FLEET-VALIDATION-INVENTORY.md` — all QA manifest repos, local-source observations,
  proposed mappings and unknowns; not proof of remote protection or runner health.
- `VALIDATION-PARITY.md` — provisional Ubuntu adapter contract, not the fleet schema.
- `bin/check_validation.py` — provisional opt-in contract/workflow/runtime checker; adopted
  rows fail before tests in `run_all.py` when parity fails. Existing Gate Kit and
  release preflight pins need explicit integration before they enforce this rule.

## Commands
- Everything: `python3 bin/run_all.py --all`
- One repo: `python3 bin/run_all.py --only beanfit-app --all`
- Docs standard: `python3 bin/check_docs.py`

## Test commands
- Deterministic repository checks (Task 3 and Python 3.12): `task validate`
- Self-check (docs, standards kernels, and offline regression tests): `bash bin/qa_selfcheck.sh`
- Full sweep: `python3 bin/run_all.py --all`

## The contract (binding on every session, human or agent)
1. Bug fixes ship with a failing-first regression test.
2. New user-facing flows land with in-repo unit tests AND an owned e2e
   registered in manifest.json before merge.
3. Done = run_all green for the touched repo.
4. New repos register here day one (mirrors agency repos.json law) — the
   weekly bean-sched reconciler job catches misses and fails loudly.
5. Reviewer checklist: diff without tests → block; new flow without a
   manifest row → block; planned repos graduate on next touch.
6. New READMEs, material README/navigation changes, and publication/portfolio
   reviews use [README-STANDARD.md](README-STANDARD.md): record the checklist,
   readability rating and before/after disposition. Typo-only corrections do
   not require a new full review. Automated
   docs checks alone do not establish readability; preserve essential limits
   and keep review paperwork out of the human entry.

## Adding a repo
Give it runnable entrypoints at its own root → append manifest row →
`run_all.py --only <name> --all` green before landing.
