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
  entrypoints, its optional `setup` stage, its status (`active` / `unit-only`
  / `planned` + gap note).
- `bin/run_all.py` — one command that runs every registered entrypoint and
  emits an aggregate pass/fail with a timestamped log under `logs/`.

## Usage

```bash
python3 bin/run_all.py                 # unit tier everywhere
python3 bin/run_all.py --e2e           # e2e tier
python3 bin/run_all.py --all           # both
python3 bin/run_all.py --only beanfit-app --e2e
python3 bin/run_all.py --include-planned   # surface known gaps
python3 bin/run_all.py --manifest PATH --logs-dir PATH # alternate registry/output
```

`--manifest PATH` points at a different registry than `manifest.json`, and
`--logs-dir PATH` writes the `run-*.json` reports to a different directory
than `logs/` (created if missing). A missing or malformed manifest, a
manifest without a `repos` list, or an unwritable `--logs-dir` exits nonzero
with a single-line error — never a traceback or a false green.

An unknown repository, an empty selection, or a selected tier with no runnable
test entrypoints fails and records a failed selection in the report. Docs alone
cannot make QA green. `--all` still permits a unit-only repo with no E2E command;
a missing required unit command fails even when another repo passes.

Repos that declare a `setup` entrypoint run it once, before their selected
unit/e2e tiers, so a clean checkout installs its own dependencies first
(e.g. beanfit-app runs lockfile-pinned `npm ci`). A failing setup blocks that
repo's tests — the tests are recorded as skipped and the aggregate run fails.

For a small cross-repository replay, check out gate-kit at the path registered
in `manifest.json`, then run:

```bash
python3 bin/run_all.py --only gate-kit --all
```

The report includes separate `docs` and `unit` verdicts (the latter runs
gate-kit's regression suite), an aggregate count, and a timestamped JSON file
under `logs/`. This is a local integration check, not proof that a public CI
run or release passed. Because gate-kit is registered as `unit-only`, this
command does not claim E2E coverage.

## Clean-room synthetic quickstart

`examples/synthetic_quickstart.py` runs the real `bin/run_all.py` against a
disposable synthetic repo created under a temp directory — no BeanLabs
workspace, no network, no real data. It writes timestamped JSON reports to a
disposable `--logs-dir` and demonstrates, with exit codes and report files:

1. a passing docs + unit run,
2. a failing docs run, and
3. a failing unit run (each nonzero-exit with its JSON report preserved).

```bash
python3 examples/synthetic_quickstart.py
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

## Agency Clawstr setup

Agency's setup installs its Python test dependencies, then runs the
repo-owned `setup/clawstr/bootstrap.sh` when that package is present. A
missing or failed bootstrap fails setup; older checkouts without Clawstr
remain supported. The shell preserves the CI-provided runtime PATH. The
bootstrap requires Node.js 22+ and installs the checked-in npm lockfile with
lifecycle scripts disabled. Gate-kit prepares Node before invoking setup.

The existing Agency E2E command now also covers Clawstr via a temporary
loopback relay and dummy signer. Tests never use the real key, journal,
public relay, or model. `run_all.py` runs Agency's registered setup before
its tests; call the setup entrypoint directly any time dependencies must be
installed outside that flow. qa-kit's
registered self-check also runs its regression tests, including setup
success, missing/failed bootstrap, and Python-install failure cases.

---

**Agents:** see [AGENTS.md](AGENTS.md) before changing anything here.
