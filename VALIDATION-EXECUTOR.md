# Shared validation executor v1

`bin/validation.py` provides an opt-in, standard-library execution contract. The
default `validation/registry.json` is empty. Existing manifest entrypoints retain
their legacy behavior until their owner reviews an enrollment and its controls.
The earlier [Ubuntu prototype](VALIDATION-PARITY.md) remains a separate, unenrolled
prototype; its workflow renderer is not this contract.

## Ownership and trust

Repositories own commands and product assertions. QA Kit owns the execution
protocol and central required coverage. Gate Kit owns GitHub event, repository,
candidate, runner and check identity guards. Agency owns release acceptance.
An executor receipt with `context: ci` does not establish a GitHub check: Gate must
bind it to the actual run, event, checkout and check result. Local evidence remains
local. A task's declared capabilities/effects do not grant runner access.

An invoking adapter must verify its trusted **control checkout commit**, ensure
registry/bundle/authorization files are tracked regular files contained there,
and obtain the expected bundle digest from reviewed pinned configuration. Passing
self-authored JSON and its hash is not authorization. Use `python3 -I` to isolate
the executor's import path. The CLI derives its own QA source root; it does not
accept a substitute source root argument.

The executor checks physical tracked bytes and executable modes against Git HEAD,
clean status, hidden index flags, exact commits and digests before execution and
after every task. Symlinks and submodules are currently unsupported. Ignored build
outputs may change; they are **not** evidence of pinned dependency contents. Any
dependency requiring immutable provenance must be a declared clean Git fixture,
or wait for a qualified input type. Install commands and their lockfile assertions
remain repo-owned. No protected knowledge or live/provider profile is qualified.

## JSON inputs

All schemas reject duplicate object keys and unknown fields. Identifiers are
letters/digits/dots/underscores/hyphens; selection cells are `task@variant`.

### Repository contract: `qa-kit.validation-contract/v1`

Required fields:

- `schema`: the schema string above.
- `variants`: map of variant name to `{os, arch, runtimes}`. OS is `linux`,
  `darwin` or `windows`; v1 execution is qualified only on POSIX. Architecture
  matches Python's observed `platform.machine()`. Runtimes map `python`, `node`,
  `bash`, or `npm` to numeric version prefixes, e.g. `3.12`, `22`, `5`. The exact
  version, resolved binary and SHA-256 are recorded. `sh` is rejected because its
  version cannot be established portably. Unsupported features remain blocked.
- `tasks`: map to `{argv, cwd, after, variants, env, effects, fixtures,
  timeout_seconds}`. Prerequisites in `after` execute in the same variant.
  Commands are argv arrays, never implicitly evaluated as shell strings.
  The executable must be a declared observed runtime (or its exact resolved path).
  Timeouts are positive seconds, bounded at four hours.
- `selections`: map from selection name to nonempty required `task@variant` lists.

`env` values use one explicit type: `{"literal":"UTC"}`,
`{"repo_path":"src"}`, or
`{"fixture_path":{"name":"sample","path":"input.json"}}`.
Paths must exist and stay within the relevant checkout without symlinks/traversal.
`PYTHONPATH` must use a path type. PATH, HOME and loader overrides are rejected.
Environment values and raw child output are not copied into receipts.

Supported effects are `repo-write`, `scratch-write`, `loopback`,
`dependency-network`, and `public-network`. Each used effect must be authorized.
These declarations support review; the executor is **not an OS or network
sandbox**. Runner isolation and authorization remain mandatory adapter duties.
Child environments have temporary HOME/TMPDIR, an executor scratch directory,
and declared interpreter bindings ahead of `/usr/bin:/bin`. Ambient credentials,
user PATH entries, shell startup overrides and Python import paths are removed.
Scripts must declare and review their transitive tools: this is not syscall
tracing or proof that arbitrary shell code uses no other absolute executable.

### Registry: `qa-kit.validation-registry/v1`

`{schema, repos}`; each repository entry has:

```json
{
  "contract": ".qa/validation.json",
  "contract_sha256": "<64 hex digest of exact contract bytes>",
  "github_repository": "owner/repository",
  "selections": {"ci-required": ["checks@linux-py312"]},
  "required_selections": {"ci": "ci-required"}
}
```

Contract selections must exactly equal the central required selections. CI and
release invocations must select the name registered for their context. The
adapter checks actual GitHub repository identity against `github_repository`.
Key presence establishes enrollment, including malformed/empty entries: errors
must never fall back to legacy. Rollout must also add a manifest `validation` key
so an adapter missing the new controls cannot silently treat enrollment as legacy.

### Bundle: `qa-kit.validation-bundle/v1`

Required fields: `schema`, `protocol: "1.0"`, `qa_commit`, `registry_sha256`,
`authorization_sha256`, `adapters` (context to exact Git commit), and `fixtures`
(fixture name to exact Git commit). Each fixture passed to the invocation must
be required by a selected task and pinned in the bundle. Its tracked byte digest,
HEAD and cleanliness are checked before and after execution.

### Authorization: `qa-kit.validation-authorization/v1`

`{schema, contexts, variants, effects}`; each latter field is a string list. Its
exact digest is pinned in the bundle. It must originate in the trusted control
checkout, not the candidate repository's proposed contract. A local caller cannot
turn a local receipt into CI/release authority by changing a context string.

## CLI and results

```sh
python3 -I /pinned/qa-kit/bin/validation.py \
  --root /candidate --repo sample \
  --registry /controls/validation/registry.json \
  --bundle /controls/validation/bundles/sample.json \
  --authorization /controls/validation/authorizations/sample.json \
  --expected-bundle BUNDLE_SHA256 --expected-head CANDIDATE_SHA \
  --selection ci-required --variant linux-py312 --context ci \
  --adapter-root /pinned/gate-kit --output /scratch/new-result.json
```

Add `--fixture NAME=/exact/fixture` for each required fixture. Output must not
already exist. CLI exits zero only when the invoked variant's task closure passes;
nonzero covers blocked preconditions, failures, cancellation and source drift.
CI/release require an exact clean adapter checkout matching the bundle. The CLI
always requires an externally pinned bundle digest, including local comparisons.

Result schema `qa-kit.validation-result/v1` records:

- `status`, `repo`, `github_repository`, `selection`, `variant`, `context`, `when`.
- `required`, `selected`, `remaining_required`, `selection_complete`.
- Exact `candidate.before/after`, `controls.qa/adapter`, `fixtures.before/after`.
- Contract, registry, bundle, authorization and plan SHA-256 digests.
- Observed platform/runtime binary identities.
- Per-task status, exit code, timeout/cancellation, duration and stdout/stderr
  hashes. Raw output is discarded to avoid transporting secrets or private data.

`pass` covers only the selected variant. **Whole-selection acceptance also
requires `selection_complete == true` and exact required-cell equality.** A
multi-variant selection remains partial after one invocation. V1 does not merge
external receipts; consumers must block whole-selection release until a reviewed
aggregation mechanism exists. Never split coverage just to obtain a green result.

Failed setup blocks dependent tasks. Timeout terminates the child process group,
including descendants. SIGTERM/SIGINT cancellation is forwarded through cleanup;
remaining tasks are blocked. Candidate, fixture or control drift stops the rest
of the plan. Missing capabilities are blocked, never not-applicable or pass.

`run_all.py` detects central registry key presence, uses the same executor and
stores its receipt under a `validation` result without rerunning legacy commands.
Supply `--validation-registry`, `--validation-bundle`,
`--validation-authorization`, `--validation-selection`, `--validation-variant`,
`--validation-expected-bundle`, and optional repeated `--validation-fixture`.
It accepts only a complete selected plan. Legacy receipt kinds do not establish
new task/variant coverage; reporting v1.1, scheduler auth and cursors are unchanged.

## Publication and rollback

1. Publish additive QA executor with an empty registry.
2. Publish compatible Gate and Agency adapters pinned to that executor.
3. Publish a later control commit containing registry, authorization and bundles
   that reference those earlier exact commits. This avoids self-referential pins.
4. Review and enroll one candidate at a time; retain prior qualified workflow and
   control bytes. Compare exact local and actual GitHub evidence before expansion.

The executor lives at its pinned implementation commit; control files can live at
a later QA Kit commit. No source branch/tag movement changes an accepted bundle.
Rollback restores the prior qualified bundle and required checks. A missing GitHub
check, unavailable runner, billing restriction or partial selection is not green.

Qualification: `python3 -m unittest discover -s tests -p test_validation_executor.py -v`.
Fixtures are disposable Git repositories with synthetic scripts. No product or
private datasets are used in these tests.
