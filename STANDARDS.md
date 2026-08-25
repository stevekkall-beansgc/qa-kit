# BeanLabs Engineering Standards — Kernels

**Rule of this file:** one imperative per standard, same-line link out.
Full requirements live at the link — never duplicate them here. If a
standard has no home yet, it gets a home before it gets a kernel line.

Owner repo: `qa-kit` · Binding on every session, human or agent.
Amended: 2026-08-25

---

## Maintenance loops (automatic)

| Loop | Cadence | Catches | Kernel owner |
|---|---|---|---|
| Compliance gates | every push/PR | docs, unit, e2e violations | [gate-kit](https://github.com/stevekkall-beansgc/gate-kit) |
| CI monitor | hourly | red main, any repo | [bin/ci_monitor.py](bin/ci_monitor.py) |
| Fleet health | 15 min | services down, tick lag | [bin/health.py](bin/health.py) → hub `/qa` |
| Registry reconciler | weekly | unregistered repos, dead paths | [bin/reconcile.py](bin/reconcile.py) |

## Standards kernels

**Review contract** — done = tests exist and run_all green; fixes ship failing-first; flows ship with owned e2e. → [README §contract](README.md)

**Docs standard v1** — every repo carries README (human) + AGENTS.md (agent, Test commands = manifest entrypoint exactly). → [bin/check_docs.py](bin/check_docs.py)

**Registry law** — new repos register in manifest.json AND agency/repos.json day one, with tier + entrypoints. → [manifest.json](manifest.json)

**Graduation rule** — a planned row graduates to active on its next touch; never silently untested. → [manifest.json](manifest.json)

**Gate semantics** — check names (docs/setup/unit/e2e) are the API; gates advisory (Free tier); binding at release. → [gate-kit/bin/compliance.py](../gate-kit/bin/compliance.py)

**Release standard v1** — semver + annotated tag + pre-tag gates via `ag release` only. → [agency/docs/RELEASE-STANDARD.md](../../../agency/docs/RELEASE-STANDARD.md)

**State machine truth** — lifecycle edges live in exactly one table: agency server db.py TASK_TRANSITIONS, conformance-tested. → [server/db.py](../../../agency/server/db.py)

**Surface contracts** — hub/runner shapes are versioned; breaking a documented shape requires bumping CONTRACTS.md. → [contracts](../../../agency/contracts/CONTRACTS.md)

**Layout law (ADR 0005)** — repos under ~/beans/<group>/<repo>, registered day one, no scratch elsewhere. → [check_layout.py](../../mind/beanmind/scripts/check_layout.py)

**Honesty rule (product)** — estimates ship uncertainty; catalog pins measured, never guessed; no fantasy numbers off-platform. → [beanfit AGENTS](../../products/beanfit/AGENTS.md)

**Scheduled-binary rule** — launchd/bean-sched context has no homebrew PATH; scheduled scripts resolve binaries absolutely. → [bin/ci_monitor.py](bin/ci_monitor.py)

**Health pane** — one glance: services up, repo CI, QA baseline age, monitor coverage. → [bin/health.py](bin/health.py) · hub `/qa`

## Relative-path note

`../../../` links resolve on disk (repo siblings); use the disk for full
navigation or each repo's GitHub for its own standards.
