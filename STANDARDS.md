# BeanLabs Engineering Standards — Master Index

**This file is the entry point.** Every standard, loop, and enforcement
mechanism is listed here with its source of truth. If something isn't
reachable from this file, it isn't a standard yet.

Owner repo: `qa-kit` · Binding on every session, human or agent.
Last amended: 2026-08-25

---

## 1. The four maintenance loops (automatic)

| Loop | Cadence | What it catches | Where |
|---|---|---|---|
| **Compliance gates** | every push / PR | docs standard violations, broken units, failing e2e | `gate-kit` workflow, per-repo `.github/workflows/gate.yml` |
| **CI monitor** | hourly (`ci-monitor` job) | red runs on main, any repo | `qa-kit/bin/ci_monitor.py` → FAIL row on scheduler board |
| **Fleet health** | 15 min (`fleet-health` job) | services down, tick lag, repo state | `/qa` pane (hub mount) + `qa-kit/bin/health.py` |
| **Registry reconciler** | weekly Mon 07:13 (`qa-kit-reconcile` job) | unregistered repos, dead paths | `qa-kit/bin/reconcile.py` |

Escalation path: gate red → PR blocked-by-policy · monitor red → scheduler
board FAIL row · reconciler red → stub row + FAIL row · pane red → you.

## 2. The review contract (binding, 6 rules)

Full text: [`qa-kit/README.md`](README.md). Summary:

1. Bug fixes ship with a **failing-first regression test**. No exception.
2. New user-facing flows ship with **in-repo unit tests + an owned e2e**,
   registered in `manifest.json` before merge.
3. **Done = `bin/run_all.py --only <repo> --all` green.**
4. New repos register in `manifest.json` **and** `agency/repos.json` day one.
5. Reviewer checklist: diff without tests → block; flow without manifest
   row → block.
6. `planned` repos graduate on next touch — never silently untested.

## 3. Docs standard v1 (every repo)

Enforced by `qa-kit/bin/check_docs.py`, run automatically in every gate:

- `README.md` — human wiki; must reference AGENTS.md
- `AGENTS.md` — agent wiki ([agents.md convention](https://agents.md)) with
  required `## Test commands` section **stating the exact manifest
  entrypoint** (drift between the two fails the gate)
- Repo-specific guardrails + known-debt register live in each AGENTS.md

## 4. Gate tiers & check names

Registry: [`qa-kit/manifest.json`](manifest.json) — tier, status
(`active`/`unit-only`/`planned`), exact entrypoints, per-repo `setup` hooks.

| Tier | Repos | Gate checks |
|---|---|---|
| A (product) | beanfit-app, beanfit, agency | docs · setup · unit (+e2e for beanfit-app via `full: true`) |
| B (tooling) | bean-sched, model-harness, beanmind, skillz, qa-kit, gate-kit | docs · unit |
| C (docs/meta) | BeanLabs (planned stub) | none yet — graduates on next touch |

Check names are the API — never rename: `docs`, `setup`, `unit`, `e2e`.
Gates are **advisory** (GitHub Free, private repos); binding enforcement =
`ag release` at tag time. Real merge-blocking = Team plan decision (held).

## 5. Related standards (source of truth lives elsewhere)

| Standard | Source of truth |
|---|---|
| Release standard v1 (semver, tags, pre-tag gates) | `agency/docs/RELEASE-STANDARD.md` + `agency/decisions/0004` |
| Hub/runner surface contracts (v0.6) | `agency/contracts/CONTRACTS.md` |
| Task lifecycle state machine | `agency/server/db.py::TASK_TRANSITIONS` (single source; conformance-tested) |
| Workspace layout law (ADR 0005) | `beanmind/decisions/0005-*`, enforced by `beanmind/scripts/check_layout.py` |
| Per-repo guardrails & known debt | each repo's `AGENTS.md` |
| Audit methodology + findings register | `BeanLabs/AUDIT-2026-08/` (63 defects found; register closed 2026-08-25) |
| PR-gate platform constraints (Free-tier limits, pricing) | `BeanLabs/AUDIT-2026-08/research/pr-gates-spec.md` |

## 6. Health pane

`/qa` on the hub — services, per-repo latest CI, QA baseline, monitor state.
Regenerated every 15 min by scheduler; machine JSON at `/qa/health.json`.
Generator: `qa-kit/bin/health.py`.
