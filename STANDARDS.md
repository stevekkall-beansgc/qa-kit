# BeanLabs Engineering Standards — Kernels

**Rule of this file:** one imperative per standard, then link out. Full
requirements live at the link — never duplicate them here. If a standard
has no home yet, it gets a home before it gets a kernel line.

Owner repo: `qa-kit` · Binding on every session, human or agent.
Amended: 2026-08-25

---

## Maintenance loops (automatic)

| Loop | Cadence | Catches | Kernel owner |
|---|---|---|---|
| Compliance gates | every push/PR | docs, unit, e2e violations | [gate-kit](https://github.com/stevekkall-beansgc/gate-kit) |
| CI monitor | hourly | red main, any repo | [bin/ci_monitor.py](bin/ci_monitor.py) |
| Fleet health | 15 min | services down, tick lag | [bin/health.py](bin/health.py) → [/qa](/) |
| Registry reconciler | weekly | unregistered repos, dead paths | [bin/reconcile.py](bin/reconcile.py) |

## Standards kernels

**Review contract** — a change is done only when its tests exist and
`run_all` is green; fixes ship failing-first; flows ship with owned e2e.
→ Full 6 rules: [README.md §contract](README.md)

**Docs standard v1** — every repo carries `README.md` (human) +
`AGENTS.md` (agent, with `## Test commands` matching the manifest
entrypoint exactly). Enforced in every gate.
→ Checker: [bin/check_docs.py](bin/check_docs.py)

**Registry law** — new repos register in `qa-kit/manifest.json` AND
`agency/repos.json` on day one, with tier + entrypoints.
→ Registry: [manifest.json](manifest.json)

**Graduation rule** — a `planned` row graduates to `active` on its next
touch. Never silently untested.
→ [manifest.json status field](manifest.json)

**Gate semantics** — check names (`docs/setup/unit/e2e`) are the API;
gates are advisory (Free tier); binding enforcement is at release.
→ Platform constraints: [pr-gates-spec](../../../Desktop/BeanLabs/AUDIT-2026-08/research/pr-gates-spec.md)

**Release standard v1** — semver + annotated tag + pre-tag gates
(clean tree, green CI, remote, audit) via `ag release` only.
→ [agency/docs/RELEASE-STANDARD.md](../../../agency/docs/RELEASE-STANDARD.md)

**State machine truth** — task lifecycle edges live in exactly one table:
`agency/server/db.py::TASK_TRANSITIONS` (conformance-tested; PATCH gating
derives from it).
→ [server/db.py](../../../agency/server/db.py)

**Surface contracts** — hub API/runner shapes are versioned; breaking a
documented shape requires bumping `contracts/CONTRACTS.md`.
→ [agency/contracts/CONTRACTS.md](../../../agency/contracts/CONTRACTS.md)

**Layout law (ADR 0005)** — all repos under `~/beans/<group>/<repo>`;
registered day one; no scratch outside sanctioned dirs.
→ Enforced by `beanmind/scripts/check_layout.py`

**Honesty rule (product)** — estimates ship uncertainty; catalog pins are
measured, never guessed; no fantasy numbers on unsupported platforms.
→ Per-repo detail: `beanfit/AGENTS.md`

**Health pane** — one glance answers: services up, repo CI state, QA
baseline age, monitor coverage.
→ Generator: [bin/health.py](bin/health.py) · served at hub `/qa`

## Relative-path note

Links marked `../../../` resolve on disk (repo siblings under
`~/beans/platform`); GitHub renders them from the qa-kit repo view only
when the target repo is checked out beside it — use the disk for full
navigation, or each repo's GitHub for its own standards.
