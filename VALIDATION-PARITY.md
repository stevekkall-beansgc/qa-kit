# Validation parity v1 — provisional Ubuntu adapter

Owner: QA Kit. Status: **narrow implementation prototype; no fleet enrollment**.
The executable pilot uses disposable synthetic repos. This document describes
`bin/check_validation.py` as implemented; its version-1 contract is not the fleet
profile schema and must not be treated as the general adoption target.

The [fleet profile design](FLEET-VALIDATION-DESIGN.md) and
[20-repo inventory](FLEET-VALIDATION-INVENTORY.md) define the next review step.
They propose composable tasks/capabilities, separate runner authorization and
versioned evidence. They do not change this prototype's execution behavior.

## Prototype contract

Each repository explicitly enrolled in this prototype owns one deterministic validation entrypoint. Local
validation, its hosted CI validation job, and the QA manifest's unit command
invoke that exact command from the repository root. Test bodies and their order
stay in the repository. QA Kit owns this policy, its contract checker and the
thin workflow adapter. Gate Kit owns the separately released compliance workflow.

The shared command must propagate failures, run without publication or live
service credentials, and work from a clean checkout. It owns dependency setup
(using lockfiles where needed), suite selection and environment normalization.
It must not select a smaller suite because `CI` is set. Declare and check required
runtime versions before tests. Document supported operating systems, shell,
locale/timezone and filesystem assumptions alongside the command; normalize
relevant environment values there so direct invocation behaves like CI. Do not
print credentials or private dataset values.

Additional checks may stay in the manifest's e2e tier. Document that extra coverage
explicitly. A unit/parity result does not claim e2e, private-source, live-service,
deployment or release coverage.

## Ownership and enforcement

- Repos own `.qa/validation.json`, their entrypoint, tests and hosted workflow.
  Review these together; wrappers may provide convenient aliases.
- `bin/check_validation.py` verifies the contract, manifest command, entrypoint
  existence and complete hosted workflow without running the entrypoint.
  `--runtime` additionally probes local Python/Node versions.
- `bin/run_all.py` checks adopted rows, including runtimes, before selected test
  tiers. A failed `validation` result blocks them and fails the report. Existing
  docs/setup/unit/e2e names and unadopted rows are unchanged.
- Gate Kit's currently pinned checker and manifest do **not** enforce this new
  check. A future immutable release should invoke it against the exact caller
  checkout and pinned manifest before compliance tests, propagating failure and
  preserving the external `compliance / compliance` check identity.
- Agency release preflight executes manifest commands independently of `run_all`.
  It needs an explicit integration with this checker before claiming enforcement.

## Contract and supported adapter

V1 supports one hosted Ubuntu job, pushes to `main`, pull requests, and Python
and/or Node. It compares the entire rendered workflow instead of trying to parse
arbitrary YAML. Workflows with matrices, extra jobs, different events, custom
setup, platforms or self-hosted routing need a separately reviewed adapter version.
Never delete useful existing behavior merely to satisfy this checker. Other
workflow files are outside its scope.

Treat the v1 adapter as a versioned contract: changes to its behavior or action
pins require a new adapter version and an explicit migration. Keep older enrolled
versions supported until migrated; updating QA Kit must not silently reroute jobs.

Example repo-owned `.qa/validation.json` (all fields required):

```json
{
  "version": 1,
  "command": ["bash", "scripts/validate.sh"],
  "workflow": ".github/workflows/ci.yml",
  "workflow_name": "CI",
  "job_id": "validate",
  "runtimes": {"python": "3.12", "node": "22"}
}
```

Python pins the major/minor and Node pins the major. These select hosted setup
actions and must match local `python3`/`node` before `run_all` proceeds. The
adapter pins action revisions, uses read-only repository permissions, disables
checkout credential persistence and sets a 15-minute timeout. Pull requests always
use hosted infrastructure. Preserve workflow/job names when adopting the rule;
consumers can depend on their check names.

The command uses `bash`, `sh`, `python3` or `node`, followed by an existing repo
script and optional literal arguments. Shell fragments, dynamic GitHub expressions,
parent traversal and symlinked scripts are rejected. Declare every Python/Node
runtime used by the script; the checker cannot infer transitive dependencies.

An adopted manifest row adds this explicit registration:

```json
"validation": {"contract": ".qa/validation.json"}
```

Its `unit.cmd` must exactly equal the contract's command. V1 rejects separate
manifest `setup.cmd` and `unit.env`; these would introduce local-only behavior.
The existing manifest environment mechanism also interprets relative values as
paths, so it is unsuitable for literals such as `CI=true`. Normalize those inside
the entrypoint. Missing/malformed contracts fail for adopted rows. Unadopted rows
retain their behavior and do not produce a parity verdict.

## Local use

From an isolated QA Kit checkout, using trusted candidate paths:

```sh
python3 bin/check_validation.py --root /path/to/candidate --emit-workflow
python3 bin/check_validation.py --root /path/to/candidate \
  --manifest /path/to/candidate-manifest.json --repo example --runtime
python3 bin/run_all.py --manifest /path/to/candidate-manifest.json \
  --logs-dir /path/to/disposable-reports --only example --all
```

`--emit-workflow` prints a proposal to stdout; saving it is a separate reviewed
edit. The checker never installs runtimes, changes runner configuration, dispatches
workflows or rewrites source. Direct checking refuses unknown or unadopted selections.
Without `--runtime`, success explicitly says static only. Runtime checks use the
current PATH; prepare that PATH before invoking validation.

Static equality proves command/configuration linkage, not script semantics or OS
equivalence. Review scripts for ignored exit statuses, environment-dependent suite
selection and hidden network/data dependencies. Run the same candidate SHA on
supported platforms and retain sanitized evidence. Direct script invocation should
include its own runtime guard; central orchestration cannot enforce a guard when
someone bypasses it. Inputs are trusted executable configuration, not a sandbox.

## Prototype disposition and next review

Retain the checker and its synthetic tests as a bounded example of static linkage,
runtime checks and blocked execution on drift. Keep enrollment empty while the
fleet contract is reviewed. Future management may retain this generated Ubuntu
adapter for simple repos while supporting additional reviewed adapters.

Its restrictions are intentional prototype limits: a single job, Python/Node,
fixed events/timeout, no separate setup or manifest environment. They cannot
represent the fleet's matrices, native packaging, Swift, cross-repo fixtures or
protected workspaces. Do not remove those requirements to satisfy this checker.

Use the [design's rollout/rollback gates](FLEET-VALIDATION-DESIGN.md#selective-management-rollout-and-rollback)
for future work. QA Kit itself first needs explicit separation of portable and
fleet checks because its self-check changes scope on `CI=true` and hosted CI
bypasses it. Keep private-data access, runner configuration, immutable CI pins
and release-policy activation behind their respective reviewed migration steps.

A hosted billing block means hosted evidence is unavailable. Local results provide
feedback, but release still requires the existing successful compliance check for
the exact candidate SHA. Do not synthesize a green check or bypass that gate.
Whether a billing block also prevents self-hosted dispatch must be established
from current workflow evidence. This policy/check does not query or change billing.
