# qa-kit — BeanLabs central QA orchestration


> **Entry point for all standards:** [STANDARDS.md](STANDARDS.md)

**Principle: test bodies live in the repo that owns the code. qa-kit only
knows how to find them, run them, and record the verdict.**

A central test repository was evaluated and rejected:

1. Tests must fail in the same commit that breaks them. A separate repo
   decouples test updates from code changes — drift becomes inevitable
   (our 2026-08 audit documented this rot class repeatedly).
2. E2E suites need their repo's build artifacts, env files, and services;
   centralizing duplicates deployment knowledge for every repo.
3. Required PR checks are per-repo; centralized suites cannot gate merges.

What IS central here:

- `manifest.json` — the registry: every repo, its tier, its unit/e2e
  entrypoints, its status (`active` / `unit-only` / `planned` + gap note).
- `bin/run_all.py` — one command that runs every registered entrypoint and
  emits an aggregate pass/fail with a timestamped log under `logs/`.

## Usage

```bash
python3 bin/run_all.py                 # unit tier everywhere
python3 bin/run_all.py --e2e           # e2e tier
python3 bin/run_all.py --all           # both
python3 bin/run_all.py --only beanfit-app --e2e
python3 bin/run_all.py --include-planned   # surface known gaps
```

## The review-process contract

Binding for every session, human or agent, effective 2026-08-24:

1. **Bug fixes ship with a regression test** that fails on the old code
   and passes on the new. No exception.
2. **New user-facing flows** land with (a) unit tests for changed modules
   in-repo, and (b) an e2e owned by the repo exposing the flow, registered
   in `manifest.json` before merge.
3. **Done means green**: a change is complete only when
   `bin/run_all.py --only <repo> --all` passes.
4. **New repos register here day one**, mirroring the repos.json layout law.
5. **Reviewer checklist**: a diff without tests → request tests; a new flow
   without a manifest row → block the merge.
6. **Baseline rule**: any repo marked `planned` must graduate to `active`
   within its next touch — "established or will be established", never
   silently untested.

## Adding a repo

1. Give it a unit entrypoint (and e2e where flows exist) runnable from its
   own root.
2. Append a row to `manifest.json` with the exact cmd array.
3. Run `bin/run_all.py --only <name> --all` once; land it green.

---

**Agents:** see [AGENTS.md](AGENTS.md) before changing anything here.
