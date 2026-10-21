# Companion audit review v1

`bin/audit_review.py` accounts for supplied audit evidence alongside existing
`qa-kit.validation-result/v1` receipts. It runs no tests, scanner, network call or
evidence URL. It changes no executor schema, registry, scorer, acceptance policy,
required check or repository enrollment. Agency still owns acceptance and UI;
QA Kit retains evidence normalization. The offline scorer candidate `8702077`
is not a dependency or assumed merged. Core17's October21 comment6306793968
retains six later-release findings and report-only semantics; enumeration,
exception acceptance and verified remediation remain separate.

Run the synthetic example from this repository:

```sh
python3 -I bin/audit_review.py --record examples/audit-review/record.json \
  --expected examples/audit-review/expected.json \
  --receipts examples/audit-review/receipts.json \
  --verification examples/audit-review/verification.json
```

The example deliberately exits 1 with native scope unavailable and a claimed
finding unverified. Exit 2 means invalid/unavailable input; 0 means no accounting
problems were found. **No exit code grants acceptance or a clean-security claim.**
Every report has `mode: report-only` and `acceptance_granted: false`. It does not
aggregate receipts into a release-approved selection or emit security ratings.

## Separate inputs and trust

The companion record has exactly `schema`, `target`, `receipts`, `scope`,
`findings`, `known_findings`, `exceptions`, and `review`. Its schema is
`qa-kit.audit-review/v1`. The example is the machine-readable field guide.

`target` binds repository, exact commit, tracked tree digest, source-path Git blob
identities, dependency snapshots, control identities and selection. `expected`
is a separately reviewed caller input with exactly `target`, `required_cells`
and `required_scope`. The caller must establish it from authoritative source and
controls. It must not adopt the audited record's own claims as expected truth.
Source blobs are compared to that binding; this tool does not read repositories
to authenticate blobs, timestamps, authorship or freshness itself.

`receipts` maps `sha256:<64 lowercase hex>` to supplied JSON receipt objects.
The digest is canonical compact sorted-key JSON, not a raw-file digest. A receipt
must match the externally expected repository, candidate before/after snapshot,
control and dependency identities and required cells. Each selected cell needs
passing task evidence, a passing receipt and no collection errors. Setup fail and
dependent blocked statuses remain separate. A pass on one variant cannot cover
another. Inspected product surfaces remain separate from passed software tests.
No receipt is changed, fetched, executed or promoted to CI/release evidence.

`verification` has exactly `reproductions`, `independence`, and `remediations` maps.
These are caller-supplied, separately reviewed corroboration, **not authenticated
proof**. The caller is responsible for qualifying reviewers and reproduction
receipts through its existing authority. Self-authored sidecars are not independent
validation. The output says `caller-corroborated`, never independent acceptance.

A confirmed finding needs a reproduction reference whose supplied entry binds the
exact target, outcome and canonical finding digest excluding its `reproduction`
field. Otherwise it reports unverified. Rejected hypotheses retain their evidence
and counterevidence; rejection without counterevidence reports unverified.
Independent-review corroboration binds distinct author/reviewer IDs and the exact
record digest; a different ID or bare declaration is insufficient.

Known finding IDs persist through absent/narrower scans and accepted exceptions.
A separately supplied remediation must bind the exact target and finding, identify
fix and verification evidence digests, declare outcome `remediated` and retain
caller qualification of its reviewer. This is accounting of supplied review, not a
clearance writer or a substitute for Core17's qualified normalization/ingestion.
No finding is deleted and an exception never becomes remediation automatically.

## Evidence handling and limits

Evidence references are inert digest IDs only. Raw private paths, transcripts and
URLs are held; they are never fetched, executed or copied into the report. Reports
emit only allowlisted IDs/statuses and digest references, with a public-rendering
hold when unsafe references occur. Free-text reasons, receipt errors and original
claims stay in the input. This is reference minimization, not a general secret
classifier or permission to publish the underlying inputs. Keep them local and
follow the existing disclosure review.

The validator checks structure and supplied bindings. It cannot establish semantic
truth, completeness of an inspection, genuine reviewer independence, source rights,
or that a caller has supplied every known finding. Review, actual product evidence
and Steve's acceptance remain separate prerequisites.
