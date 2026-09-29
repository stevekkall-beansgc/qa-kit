# Fleet validation: composable profiles and selective management

Status: **design for review, 2026-09-28**. Owner: QA Kit. This package changes
documentation only. It enrolls no repository and supplies no new executable schema,
runner routing, workflow, CI pin or release authority.

Read with the [20-repo inventory](FLEET-VALIDATION-INVENTORY.md),
[standards index](STANDARDS.md) and
[provisional Ubuntu adapter](VALIDATION-PARITY.md). The inventory combines supplied
local review findings with inspected manifests, workflows and guidance. It proves
neither remote branch protection nor current runner availability or successful CI.

## Decision and boundaries

Use composable tasks, capability requirements, execution variants and required
selections. One repo can need Python, Node, a pinned fixture, loopback services and
Swift in different tasks. An exclusive language/OS profile cannot describe that.

Keep the exact-rendered Ubuntu adapter as a narrow prototype for simple workflows.
Its whole-file equality, Python/Node-only model, fixed events/timeout and rejection
of separate setup are not the fleet schema. Existing synthetic tests prove that
prototype's stated behavior only. Do not enroll repos or rewrite their workflows
merely to fit it. Review the profile contract before implementing its successor.

Centralize the rule, supported adapters and execution semantics. Keep test bodies,
product acceptance assertions and build logic in their owning repositories. A repo
may expose one command with a profile argument or several explicit entrypoints;
the same named task/variant must resolve to the same command and inputs locally
and in CI. No implicit reduction of coverage based on `CI`, host OS or missing tools.

## Composable model

| Element | Proposed contract | Owner / enforcement boundary |
|---|---|---|
| Task | Stable ID; repo-owned argv; working directory; phase; prerequisites; timeout; capabilities; data/effects; outputs | Repo declares implementation; QA Kit validates and plans execution |
| Profile | Versioned bundle of task roles/default requirements; freely composable when compatible | QA Kit catalog; repo explicitly maps its tasks |
| Capability | Typed runtime, toolchain, feature, platform, service, fixture or resource requirement | QA Kit definitions; adapter observes actual capability |
| Variant | Explicit OS/architecture/runtime combination with an independent result | Repo declares supported variants; central policy declares required coverage |
| Selection | Named required task/variant set, e.g. routine, full-offline, platform-acceptance, release-required | Repo proposes; central enrollment approves required minima |
| Runner authorization | Approved adapter, repository/event/ref/SHA context, runner group and allowed effects | Gate Kit/operational policy; a repo capability request cannot grant authority |
| Evidence | Source identity, plan/config/control-bundle digests, observations, task/variant outcomes and artifact provenance | Common result contract; Agency decides release acceptance |

Profiles are conveniences for composing requirements, not permission levels or
mutually exclusive classifications. A task claiming a capability does not prove
the host has it. Having a host capability does not authorize execution there.

## Candidate profiles and capabilities

These names are design candidates, not currently accepted checker identifiers.

| Candidate profile | Scope | Common capabilities; independent extensions |
|---|---|---|
| `portable-core` | Deterministic docs, static checks, unit and contract suites | Python/Node/shell as declared; dependency locks; repo-only inputs |
| `offline-integration` | Deterministic subsystem acceptance | Disposable SQLite, loopback HTTP, subprocesses, Worker/D1 emulation, pinned cross-repo fixtures |
| `package-acceptance` | Build/install/exercise the deliverable | OS/architecture variants, native wheel/archive tools, isolated install root, artifact checksums/provenance |
| `native-linux` | Linux-specific compilation or acceptance | Pinned Rust/toolchain, libc/target architecture, native library requirements |
| `native-macos` | macOS/Swift/Xcode requirements | Developer-tool readiness, Swift/SDK versions, architecture; no automatic license acceptance |
| `protected-local` | Approved host-private inputs or canonical workspace assumptions | Explicit data scope, source equality checks, workspace confinement, shared lock and cleanup policy |
| `live-observation` | Public-network or authenticated operational checks | Explicit endpoint/network scope and separate authorization; never silently included in deterministic/offline coverage |

Deploy/release mutation remains outside routine validation. A package can be built
and validated in scratch space without authorizing publication. An operational
lane may be independently required by a release policy, but it needs its own
evidence and authority rather than inheriting them from a unit pass.

The capability catalog should cover these orthogonal requirements:

- **Runtime/toolchain:** Python, Node, Rust/Cargo, Swift/Xcode, shell, compiler and
  package-manager constraints. Distinguish accepted ranges from the exact versions
  actually measured. A declared Python 3.14 task is not satisfied by `>=3.12`.
- **Feature:** e.g. Node SQLite support or Worker/D1 emulation. Version strings
  alone may not establish required features; use a safe capability probe.
- **Platform:** OS, architecture, target ABI/libc/SDK and native packaging variant.
  A Mac result does not cover a Linux package or an unexecuted Windows matrix cell.
- **Dependencies/fixtures:** lockfile digest, bootstrap command, network needs for
  setup, external repo/fixture revision, placement and consuming tasks. No implicit
  dependency on a developer's sibling checkout.
- **Services/resources:** loopback binding, disposable stores, CPU/memory budgets,
  timeout, concurrency and lock requirements. Resource availability is observed,
  not inferred from a runner label.
- **Environment/data/effects:** literal values versus repo-relative paths; locale,
  timezone and PATH policy; input classification; permitted read/write roots;
  temporary/generated output handling and log redaction. No credentials in contracts.

Incompatible pins, missing required capabilities and contradictory scopes must
produce a blocked/failed result. Profiles must never silently override one another.
Dependency installation can require network while subsequent tests remain offline;
record those phases and permissions separately.

## Candidate contract shape

The following is illustrative **design JSON**, not an enrollment file or the input
format of `bin/check_validation.py`. Pin names are placeholders, not approved releases.

```json
{
  "schema": "qa-kit.validation-contract/draft-2",
  "profiles": ["portable-core@1", "offline-integration@1"],
  "variants": {
    "linux-py314": {"os": "linux", "arch": "x86_64", "python": "3.14.*"},
    "mac-py314": {"os": "macos", "arch": "arm64", "python": "3.14.*"}
  },
  "tasks": {
    "bootstrap": {
      "phase": "setup",
      "argv": ["sh", "scripts/prepare-validation.sh"],
      "cwd": ".",
      "requires": {"node": "22.*", "dependency_lock": "package-lock.json"},
      "effects": {"writes": ["scratch", "repo-dependency-cache"], "network": "dependency-registries"}
    },
    "contracts": {
      "phase": "unit",
      "argv": ["sh", "scripts/validate.sh", "contracts"],
      "cwd": ".",
      "after": ["bootstrap"],
      "variants": ["linux-py314", "mac-py314"],
      "requires": {"node": "22.*", "services": ["loopback", "worker-d1-emulator"]},
      "env": {"TZ": {"literal": "UTC"}, "PYTHONPATH": {"repo_path": "src"}},
      "inputs": {"classification": "synthetic"},
      "effects": {"writes": ["scratch"], "network": "loopback-only"},
      "timeout_seconds": 900
    }
  },
  "selections": {
    "routine": {"required": ["contracts@mac-py314"]},
    "full-offline": {"required": ["contracts@linux-py314", "contracts@mac-py314"]}
  }
}
```

Variant-dependent prerequisites execute inside each variant's prepared workspace;
they are not reused across incompatible environments. Initially support a bounded
phase/prerequisite model, not an arbitrary workflow programming language.

The central enrollment record separately identifies repo, contract path/digest,
approved profile/catalog version, required selections, authorized adapter policy
and control-bundle ID. A candidate repo edit cannot weaken required central
coverage or self-authorize a trusted runner. Keep legacy manifest commands as
explicit projections/bridges during migration; do not maintain two silent sources
of truth once a repo is fully enrolled.

## Ownership and a common execution plan

| Surface | Owns | Must delegate / preserve |
|---|---|---|
| QA Kit | Policy, schema/catalog, enrollment inventory, common plan/result semantics, contract checking | Repo commands retain all product logic; authorization comes from approved runner policy |
| Repo | Task implementations, setup, tests, assertions, proposed variants and effect declarations | Required coverage and runner access cannot be reduced unilaterally |
| Gate Kit | GitHub event guards, trusted checkout, adapters, runtime preparation and check reporting | Consume the same plan/executor; preserve existing check identity and source guards |
| Agency release preflight | Required release selections, exact candidate and accepted evidence, release authority | Consume the common plan/executor; preserve exact-SHA compliance and publication gates |

QA Kit's future common planner/executor should validate the contract, resolve
exact source and fixtures, prepare an authorized environment, execute setup, stop
dependent tasks after setup failure, run the selected task/variant set and emit
consistent outcomes. Both Gate Kit and Agency should consume it rather than
reimplementing command/env/timeout behavior. The existing prototype does not yet
provide this shared execution system.

Observed motivation: QA Kit currently blocks tests on setup failure; Gate Kit's
CLI records the setup failure then continues; Agency's target QA routine executes
unit/e2e without setup. Existing relative environment values are interpreted as
paths. Preserve old behavior for unenrolled repos while the new semantics are
explicitly qualified. These findings do not authorize changing any current runner.

## Versioned control bundle and evidence

A control bundle must identify compatible **policy/catalog, workflow adapter,
checker, QA manifest/enrollment registry and shared fixtures** by immutable revision
and digest. Tags may be human labels, but evidence records resolved commits.
Unknown or incompatible combinations block adoption; the current source tree does
not prove what an older workflow tag loads. See the inventory's locally inspected
pin table. Migrations must support both qualified old and new bundles during rollout.

Each result should record candidate SHA and clean/dirty source status; contract
and execution-plan digests; control-bundle identity; task/variant IDs; observed
runtime/platform/fixture versions; setup outcome; exit/timeout result; data/effect
scope; sanitized logs; and artifact hashes where applicable. Local dirty-tree
results may assist development but cannot claim clean exact-commit release proof.

Report `pass`, `fail`, `blocked`, `not-run` and `not-applicable` distinctly.
Only explicit policy can establish not-applicable; missing prerequisites or matrix
cells are never a pass. A result from a different runtime/OS/configuration cannot
substitute for a required variant without a reviewed equivalence rule. Preserve
artifact-to-source identity through package installation tests. A receipt merely
asserting success is insufficient; establish its execution provenance in the
approved CI/local context before release acceptance.

Local/self-hosted compute can reduce hosted consumption while still producing an
actual GitHub check. A local-only receipt and a GitHub check remain different
evidence surfaces. A hosted billing block is unavailable evidence, not a test
failure or success. The current exact-SHA compliance requirement remains binding;
never fabricate a check, substitute stale green, or assume self-hosted dispatch
works while billing is blocked. Verify dispatch and outcome separately when
authorized. This design changes no billing configuration or release requirement.

## Selective management, rollout and rollback

Management states: **observed** (inventory only), **candidate** (reviewed proposed
contract), **shadow** (comparison without authority change), **enrolled** (explicit
required enforcement), and **exception** (owned reason and migration criteria).
Generated thin callers can be centrally managed. Complex repos can retain other
workflows alongside a managed validation job. Whole-file equality applies only to
explicitly generated/owned files; never extend the prototype with ad hoc YAML regexes.

| Gate | Acceptance before advancing | Rollback / stop condition |
|---|---|---|
| Inventory | All 20 rows accounted for; checks, effects, pins, variants and unknowns recorded | Keep observation-only status if access/evidence is missing |
| Model review | Composable requirements, authority separation and required task sets agreed | Revise the draft without changing existing execution |
| Schema/executor qualification | Synthetic cases cover setup stop behavior, env typing, runtime/variant mismatch, missing fixtures, source drift, timeouts and incompatible bundles | Reject the candidate bundle; preserve qualified legacy semantics |
| Representative pilots | Portable repo, then dependency/service repo; same candidate/config compared locally and in CI; failures and required coverage preserved | Restore prior reviewed caller/manifest bundle, retaining its required checks |
| Native/protected pilots | Linux artifact proof, OS matrices, Swift readiness and canonical locking each independently qualified; private scope expressly authorized | Keep unsupported variants blocked or retain an owned exception; never broaden access |
| Coordinated enrollment | QA/Gate/Agency pins and check names agree; runner readiness and release selection evidence verified | Use the recorded prior bundle; do not weaken checks to get green |
| Fleet expansion | Per-repo review and retained comparison evidence; operational/deploy lanes remain independent | Stop expansion on drift; correct forward or use the prior qualified configuration |

Use explicit opt-in cohorts. Do not infer runner trust from same-repository PR
membership alone; inventory existing exceptions, review event/ref/repo/SHA guards
and retain isolation. Do not migrate private or knowledge-mutating tasks from
workflow declarations alone. Adoption must not reset/clean canonical sources,
change system licenses, grant credential access or create another scheduler.

No rollback accepts missing required coverage, stale check evidence or a billing
bypass. A rollback that needs publication/runner changes retains the corresponding
approval boundary. Remote branch protection, runner state, remote tag resolution
and live outcomes must be verified separately before operational activation.
