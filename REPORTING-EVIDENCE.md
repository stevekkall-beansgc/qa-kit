# Reporting evidence

QA Kit distinguishes a scoped result from fleet health. A passing run for one
repository is displayed with its repository names and check kinds; it cannot
replace the latest known failure of another repository. Per-repository results
are scoped observations, with their timestamps, not release approval.

## Receipt provenance

`run_all.py` preserves its existing result fields, commands, ordering and exit
codes. It adds an `evidence` object with `schema_version: 1`:

- `source`: QA Kit Git HEAD and dirty state.
- `manifest`: absolute path and SHA256 of the exact bytes used for selection.
  A read race or a change during execution makes the digest unknown and records
  a collection error.
- `selection`: selected repository names, tiers, `only` and `include_planned`.
- `expected_checks`: declared checks captured before execution.
- `repos`: Git HEAD and dirty state before and after each selected repository.
- `runtime`: Python version, operating-system name and boolean CI label.
- `collection_errors`: unavailable or changing manifest evidence.

Unavailable Git metadata is `null`; synthetic/non-Git fixtures continue to run.
Changed filenames, arbitrary environment values and credentials are excluded.
Receipts and local paths remain private; the public synthetic sample retains its
sanitized contract. Same-second receipt suffixes are ordered numerically.

The health consumer accepts legacy receipts for scoped display. They cannot
prove a fleet baseline. A complete candidate requires the current manifest
digest, every eligible repository and declared check, a known clean QA source,
and known clean, unchanged before/after repository identities matching current
local identities. Candidate proof does not establish remote CI or approved age.

**Fleet coverage and maximum age are pending an owner decision.** Until that
policy and its CI acceptance rules are implemented, fleet status is UNVERIFIED;
a complete candidate remains separate from the latest scoped run. No fleet
enrollment or runner authorization changes are part of this increment.

## CI monitor and dashboard

`ci-state.json` schema 2 separates `attempted` from `verified`. `verified` means
the eligible repository queries completed successfully, not that tests passed.
Each registered repository has its current state, last verified time and
completed-run watermark. Legacy wrapper keys are removed; legacy `checked`
timestamps migrate as attempts only. Authentication/API/malformed responses are
unknown and fail the monitor. Missing repositories are unknown. Local-only,
no-runs, queued and running states never count as successful CI.

Git resolves remotes for both ordinary repositories and linked worktrees.
In-flight runs do not advance the completed-run watermark, so a later failure
of the same run is still detected. Writes replace the state atomically.

## Backup evidence

The dashboard separately shows local replication, sync process state/runtime,
last timestamped successful sync completion, offsite object age, local restore,
offsite restore and overall recovery. A historical exit zero cannot make an
active/stuck process green. A successful sync-completion timestamp is unknown
until Agency supplies authoritative evidence. A nonzero offsite query is unknown
even if stdout contains object-like timestamps.

Restore phases use their own structured fields. A phase not reached is unknown.
A failed snapshot/live comparison is not labeled corruption. Overall recovery
remains unverified until Agency supplies an agreed snapshot-consistent recovery
objective and current offsite/restore proof. Existing freshness tolerances are
retained for individual observations; they are not a new approved recovery target.

## Registry drift

The reconciler validates the QA and Agency registries independently, detects
name/path disagreements and dead paths in either source, and fails closed on
unreadable or malformed sources. It does not automatically fix Agency's registry.
Linked task checkouts share their registered source's Git common identity;
they do not become new repositories or acquire separate test obligations.
Archived disk-only storage retains its existing no-test treatment. Registered
archived rows missing from the other registry remain unresolved drift until an
explicit exemption policy is approved; no test entrypoints are added for them.

## Integration boundary

The separately owned `codex/validation-parity-policy` draft also edits
`run_all.py`. Its `validation` result kind and fail-before-tests behavior must
survive a coordinated integration. Expected checks already reserve a declared
validation check, but the provisional adapter is not enrolled fleet evidence.
Any parity contract/control digest added by that integration must join receipt
provenance. QA Kit reporting changes do not authorize Gate/release pin updates,
scheduler changes, service cutover or historical checkout retirement.
