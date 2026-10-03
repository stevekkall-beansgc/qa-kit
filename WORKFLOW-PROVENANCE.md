# Workflow action provenance

Source candidate based on QA Kit `38c7a7bfc078038cfd624ef58d24315e7230e0fe`.
On 2026-10-02, GitHub's public Git refs API was read through `gh api`:

| Action | Reviewed release ref | Immutable commit |
| --- | --- | --- |
| `actions/checkout` | `v5.0.0` | `08c6903cd8c0fde910a37f88322edcfb5dd907a8` |
| `actions/setup-python` | `v5.6.0` | `a26af69be951a213d495a4c3e4e4022e16d87065` |

Both refs resolved directly to commit objects. These same revisions are already
used by Gate Kit's hosted test workflow at `38741affd2034f9b110b4a302ecfc08c4046f722`.
This patch fixes the moving `@v5` resolution to those compatible major-version
revisions. It does not claim that every upstream source line or dependency is
audited, or that these are the newest releases.

Reproduce the identity check with `gh api repos/actions/checkout/git/ref/tags/v5.0.0`
and `gh api repos/actions/setup-python/git/ref/tags/v5.6.0`. Review any future
update as a source change; never replace the commit with a moving major ref.
`tests/test_workflow_pins.py` failed on all three previous mutable references
before this patch and checks third-party references in every checked-in workflow.

The existing internal reusable caller and validation/runner policy are separate
contracts. Local checks do not establish a hosted run of this uncommitted
candidate, publication-history clearance, vulnerability clearance, or a security
rating. Contribution and reuse authority are outside this pin review.

## Owned workflow boundaries (2026-10-03)

The permissions/checkout candidate is based on QA Kit
`d819d70cff052e7763296e5f6391065ae6ac02ec`. Both owned workflows declare
`contents: read`; scopes omitted from that mapping are disabled. The hosted
unit job inherits this ceiling, the Mac task job retains its explicit identical
grant, and the reusable compliance caller passes this ceiling to its called
workflow. Checkout needs source read access. The unit/stdlib checks and Task
self-check need no GitHub write token; Git regression fixtures create disposable
local repositories. Compliance produces a local report and step summary, which
do not require issues, pull-request, checks or actions write permissions.

Both owned source checkouts disable credential persistence. The hosted job keeps
the checkout action's default event source, including the PR merge ref. The Mac
job retains its exact `github.sha` ref and post-checkout HEAD assertion. Its
canonical-repository/main-push condition and runner-name check before checkout
are unchanged. The Python 3.12 commands, runner selection and check identifiers
remain `unittest`, `task-validate-local` and `compliance / compliance`.

The retained caller is
`gate-kit/.github/workflows/compliance.yml@v0.4.11`. Read-only GitHub API
verification on 2026-10-03 resolved annotated tag object
`abe11e42dac5de2c858661619f82c8d89b76b501` to commit
`89a4904a35ffb80408cefd9588889082d61ccce4`. That exact body checks out the
caller PR head or push SHA, released Gate control `v0.4.4`, QA manifest `v0.4.0`
and BeanFit fixture `v0.1.1`, then invokes the compliance CLI and copies its
report to the local step summary. Its historical action tags and credential
persistence remain a separate inherited dependency review. Version-tag callers
are the Gate repository contract; this candidate does not adopt a newer caller.
Resolving a tag today does not prove its future technical immutability.

The ten baseline workflow observations receive individual dispositions below.
Locations refer to the baseline's workflow/job fields, so added lines do not
change their identity. No scanner ignore or waiver is added.

| Observation | Baseline location | Candidate disposition |
| --- | --- | --- |
| excessive-permissions | `gate.yml` workflow | Explicit `contents: read` ceiling. |
| excessive-permissions | `gate.yml` / `compliance` | Inherits caller read ceiling; exact called commands need no write grant. |
| unpinned-uses | `gate.yml` / `compliance.uses` | Retain mandated version tag with resolved source identity; technical tag protection and inherited dependency qualification remain open. |
| artipacked | `test.yml` / `unittest.steps[0]` | Disable credential persistence; no artifact-upload step exists in either owned workflow. |
| excessive-permissions | `test.yml` workflow | Explicit `contents: read` ceiling. |
| excessive-permissions | `test.yml` / `unittest` | Inherits workflow read ceiling. |
| self-hosted-runner | `test.yml` / `task-validate-local.runs-on` | Retain trusted canonical main-push and pre-checkout runner guard; effective host isolation remains operationally unqualified. |
| anonymous-definition | `test.yml` / `unittest` | Retain job identifier as check API; informational naming finding alone does not justify a rename. |
| anonymous-definition | `test.yml` / `task-validate-local` | Retain job identifier as check API; no display-name change. |
| concurrency-limits | `test.yml` event/jobs | Retain per-event execution without new cancellation or grouping. |

Concurrency is deliberately unchanged: branch/PR grouping with cancellation
would interrupt exact-source checks; even without cancellation, a shared group
can replace an older pending run. That would reduce evidence for individual
commits. A unique-run group provides no useful resource bound. The hosted checks
use separate runner workspaces; the existing Mac runner's scheduling and host
isolation need separate operational evidence. This source candidate cannot prove
absence of all host races, and does not add runner or scheduler controls.

`tests/test_workflow.py` failed first against the unchanged workflows for the
missing ceilings and hosted checkout control. It inspects fields in their actual
mapping/step scope and rejects duplicate or unexpected fields. Negative mutations
cover removed ceilings, write grants, credential retention, PR-head/moving-source
checkout, untrusted events, weakened local guards, runner changes and caller
rollout. Existing action-pin and Python/Task command tests remain in force.
This is a narrow standard-library workflow contract test, not a general YAML
parser or an execution of GitHub's expression engine.

Local regression success does not establish effective hosted token permissions,
checkout availability, a normal-push CI result or runner isolation. Those claims
require a later authorized exact-source CI run and the corresponding operator
evidence; publication and wider supply-chain clearance remain separate.
