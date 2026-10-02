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
