# qa-kit

`qa-kit` is a small, standard-library QA orchestrator. It reads repo-owned
check commands from a manifest, runs selected tiers, and records JSON verdicts.
Test bodies stay in the repositories that own the code.

For a public, standalone demonstration, start below. Commands that require the
private BeanLabs workspace are separated in
[BeanLabs fleet operations](#beanlabs-fleet-operations-private-workspace).

> **Engineering standards:** [STANDARDS.md](STANDARDS.md)
>
> **Publication and portfolio reviews:** [Portfolio readiness rulebook](PORTFOLIO-READINESS.md)
>
> **Private vulnerability reports:** [SECURITY.md](SECURITY.md)
>
> **Public contribution guide:** [CONTRIBUTING.md](CONTRIBUTING.md)

## Five-minute public showcase

### 1. Clone and run

Prerequisites are Git and Python 3.12. The tested public runtime contract is
the repository's GitHub Actions job: `ubuntu-latest` with Python 3.12, as
configured in `.github/workflows/test.yml`. The code is standard-library-only,
but other Python versions, implementations, and operating systems are not
claimed as supported. Use `python3` only when it resolves to Python 3.12 for a
supported run.

```bash
git clone https://github.com/stevekkall-beansgc/qa-kit.git
cd qa-kit
python3 --version
python3 examples/synthetic_quickstart.py
```

The final line should be:

```text
synthetic quickstart OK (3/3 scenarios, all output in disposable dirs)
```

No package installation, BeanLabs workspace, network access, credentials, or
real repository is needed. The quickstart reads this checkout and writes only
to a system temporary directory.

### 2. See the pass and both failure paths

`examples/synthetic_quickstart.py` invokes the real
[`bin/run_all.py`](bin/run_all.py), not a demonstration-only reimplementation.
It creates a disposable synthetic repository and manifest, then proves:

1. docs and unit checks pass with exit code `0`;
2. a docs check fails with a nonzero exit and a failed `docs` result; and
3. a unit check fails with a nonzero exit and a failed `unit` result.

A JSON report must exist after every scenario. The script reads that report and
fails its own quickstart if the expected exit code or failed verdict is absent.
The console lines prefixed `PASS` are the visible evidence; the underlying
report contains `when`, `results`, and `planned_skipped`, with each result
recording `repo`, `kind`, `ok`, `secs`, and captured output in `tail`.

### 3. Verify the checked-in public report sample

The stable sample at
[`examples/synthetic_quickstart_report.json`](examples/synthetic_quickstart_report.json)
is a sanitized, normalized copy of the quickstart's real passing docs-and-unit
scenario. It contains no private paths, credentials, or real data. Its fixed
`when` and `secs` values, and the `<elapsed>s` test-duration marker, make the
artifact reproducible; the verdicts and result fields come from an actual run
of `bin/run_all.py`.

Verify the sample against a fresh execution of all three synthetic scenarios:

```bash
python3 examples/synthetic_quickstart.py --verify-sample examples/synthetic_quickstart_report.json
```

When the sample itself needs an intentional refresh, use:

```bash
python3 examples/synthetic_quickstart.py --write-sample examples/synthetic_quickstart_report.json
```

The write command runs the real quickstart, normalizes only the documented
dynamic fields, and overwrites the sample after review. The quickstart still
uses disposable temporary fixtures and never reads the private fleet manifest.

### 4. Understand the core manifest runner

A manifest is executable configuration. Each row registers a repository path,
status, and optional `setup`, `unit`, and `e2e` commands. Only use manifests,
paths, and commands you trust because selected commands run locally with the
user's permissions.

```bash
python3 bin/run_all.py --all \
  --manifest /path/to/your-manifest.json \
  --logs-dir /path/to/your-reports
```

For each selected non-planned repository, the runner checks its README/AGENTS.md
contract, runs an optional setup stage once before selected runnable tiers,
executes the selected unit/e2e commands from the registered repository path,
and writes one timestamped `run-*.json` report. Exit code `0` means every selected result passed, `1` means
a docs/setup/test/selection result failed, and `2` means the manifest or report
destination was unusable.

The synthetic quickstart already supplies isolated `--manifest` and
`--logs-dir` paths, so third parties should use it instead of the repository's
default fleet manifest.

## Exact limitations

- The quickstart demonstrates docs and unit behavior only. Its synthetic manifest
  does not register setup or e2e commands, so it does not exercise those paths.
- It uses disposable fixtures. It makes no claim about live services, private
  fleet health, production behavior, external CI, or release status.
- Each raw JSON report from the three quickstart scenarios exists only during
  that scenario; the temporary directory is deleted when the quickstart exits.
  The checked-in sample is a separate, sanitized copy of the passing scenario,
  not a retained report from a later run.
- The checked-in sample covers the passing docs-and-unit path only. The
  quickstart itself still exercises both failure paths and is the route for
  checking them.
- The default `manifest.json` points to a private BeanLabs workspace. The
  standalone quickstart does not read it.
- Local quickstart success is a regression check, not evidence of an external
  CI run, release approval, or security audit.
- The tested runtime is Python 3.12 on `ubuntu-latest`; no broader runtime or
  platform support is asserted here.

To run qa-kit's own validators and regression suite in an isolated checkout
without following fleet paths, use the script's self-check mode:

```bash
CI=true bash bin/qa_selfcheck.sh
```

Plain `bash bin/qa_selfcheck.sh` validates all active entries in the default
fleet manifest and therefore requires that private workspace.

## BeanLabs fleet operations (private workspace)

Everything in this section assumes the `~/beans/...` paths in the default
`manifest.json` exist. It is not required for the public showcase.

### Fleet sweep

```bash
python3 bin/run_all.py                 # unit tier everywhere
python3 bin/run_all.py --e2e           # e2e tier
python3 bin/run_all.py --all           # both
python3 bin/run_all.py --only beanfit-app --e2e
python3 bin/run_all.py --include-planned   # surface known gaps
python3 bin/run_all.py --manifest PATH --logs-dir PATH # alternate registry/output
```

`--manifest PATH` points at a different registry than `manifest.json`, and
`--logs-dir PATH` writes the `run-*.json` reports to a different directory than
`logs/` (created if missing). A missing or malformed manifest, a manifest
without a `repos` list, or an unwritable `--logs-dir` exits nonzero with a
single-line error, never a traceback or false green.

An unknown repository, an empty selection, or a selected tier with no runnable
test entrypoints fails and records a failed selection in the report. Docs alone
cannot make QA green. `--all` still permits a unit-only repo with no E2E command;
a missing required unit command fails even when another repo passes.

Repos that declare a `setup` entrypoint run it once before their selected
unit/e2e tiers, so a clean checkout installs its own dependencies first (for
example, `beanfit-app` runs lockfile-pinned `npm ci`). A failing setup blocks
that repo's tests: the tests are recorded as skipped and the aggregate run
fails.

For a small cross-repository replay, check out `gate-kit` at the path registered
in `manifest.json`, then run:

```bash
python3 bin/run_all.py --only gate-kit --all
```

The report includes separate `docs` and `unit` verdicts, an aggregate count, and
a timestamped JSON file under `logs/`. This is a local integration check, not
proof that a public CI run or release passed. Because `gate-kit` is registered
as `unit-only`, this command does not claim E2E coverage.

### Review-process contract

Binding for every BeanLabs session, human or agent, effective 2026-08-24:

1. **Bug fixes ship with a regression test** that fails on the old code and
   passes on the new. No exception.
2. **New user-facing flows** land with unit tests for changed modules in-repo
   and an e2e owned by the repo exposing the flow, registered in
   `manifest.json` before merge.
3. **Done means green**: a change is complete only when
   `bin/run_all.py --only <repo> --all` passes.
4. **New repos register here day one**, mirroring the `repos.json` layout law.
5. **Reviewer checklist**: a diff without tests means request tests; a new flow
   without a manifest row blocks the merge.
6. **Baseline rule**: a `planned` repo must graduate to `active` within its next
   touch. "Established or will be established" is never sufficient.

### Add a fleet repo

1. Give it a unit entrypoint, plus e2e where flows exist, runnable from its own
   root.
2. Append a row to `manifest.json` with the exact command array.
3. Run `bin/run_all.py --only <name> --all` once and land it green.

### Agency Clawstr setup

Agency's setup installs its Python test dependencies, then runs the repo-owned
`setup/clawstr/bootstrap.sh` when that package is present. A missing or failed
bootstrap fails setup; older checkouts without Clawstr remain supported. The
shell preserves the CI-provided runtime PATH. The bootstrap requires Node.js 22+
and installs the checked-in npm lockfile with lifecycle scripts disabled.
Gate-kit prepares Node before invoking setup.

The existing Agency E2E command also covers Clawstr via a temporary loopback
relay and dummy signer. Tests never use the real key, journal, public relay, or
model. `run_all.py` runs Agency's registered setup before its tests; call the
setup entrypoint directly whenever dependencies must be installed outside that
flow. qa-kit's registered self-check also runs its regression tests, including
setup success, missing/failed bootstrap, and Python-install failure cases.

---

**Agents:** see [AGENTS.md](AGENTS.md) before changing anything here.
