# Repository scorecard candidate
Status: **review only; no runtime consumer or activation**  
Candidate version: 1.0.0-draft.1

This proposal adds reproducible Health and Security reporting alongside existing publication and hiring measures. It does not modify PORTFOLIO-READINESS.md, reporting-policy.json, manifest.json, workflows, gates, schedules, credentials, databases or deployments. Approval of this draft is separate from runtime adoption. Machine-readable proposal: [policy](scorecards/policy.candidate.json). Review cases: [fixtures](scorecards/acceptance-cases.json); these are specifications, not an executed repository test suite.

## Existing authority
- Publication P/100 and audience-specific hiring H/100 retain the canonical [portfolio rulebook](PORTFOLIO-READINESS.md), version 1.0.0 at qa-kit commit d452ff6c38e25d15d0767fbf1b99ccaf06eccc91. Do not duplicate or silently change its rubric, floors or blockers.
- Optional Showcase /10 is H divided by ten, for a named audience. Never mix audiences.
- QA Kit owns evidence normalization and scoring; Agency presents results; Bean Sched is the only periodic clock; Gate Kit retains its existing enforcement. BeanMind remains the knowledge layer; repository readability does not establish local runtime connectivity.
- No score, board assignment or approval field starts/resumes/injects Codex, grants execution authority, spends, publishes, deploys or merges. Existing approved free-resource handling is unchanged.
- Historical informal estimates are not verified baselines and must not be imported as official assessments.

## Scope and evidence
Before scoring, declare the stable repo identity, supported release/journey/mode, scope version, required checks, important failure modes and evidence requirements. Future optional roadmap work is not a defect. Required unfinished current-release behavior is a defect. A narrowed scope requires a new assessment, not rewriting old history.

Use existing D (declared), I (inspected), V (verified execution) and U (unknown) labels. Test files are I; a passing run tied to the evaluated commit/environment is V. Runtime behavior needs execution evidence. Define mandatory workflow/job coverage from reviewed repository requirements; a latest green workflow does not establish complete CI coverage. Skipped, missing, inaccessible and never-run required checks remain unknown. Scan failure is distinct from scan findings. Reading a stale receipt never refreshes it.

Each category must list its required evidence before rating. Unknown categories use null, earn zero demonstrated credit, and are visibly unknown rather than proven defective. Category coverage counts its weight only when all required evidence for that category is current, valid and complete. Do not renormalize over known categories. Show points and coverage separately. A failed executed check can have complete evidence while failing its requirement.

## Health /100
| Category | Weight | Level 3 requirement | Level 4 extension |
|---|---:|---|---|
| Core journeys and recovery | 40 | Every declared critical journey and relevant failure/recovery path has passing version-matched evidence | Additional verified adverse conditions or independent reproduction |
| Required tests and CI | 25 | Every required job/check ran and passed for the evaluated scope; assertions protect consequential behavior | Verified fault/property/concurrency/compatibility cases appropriate to risk |
| Release completeness | 20 | Current-release requirements reconciled with implementation and verification; no unresolved defects within the declared acceptance scope | Independent acceptance review or evidenced recurrence prevention |
| Setup/runtime/operations | 15 | Supported setup reproduced; runtime and recovery evidence where claimed; evidence current | Independent clean setup or verified operational recovery under adverse conditions |

Integer ratings: 0 = known unsatisfied requirement or no credit; 1 = major gaps/declarations; 2 = substantial implementation with important gaps; 3 = meets all category requirements; 4 = meets 3 plus stronger relevant evidence. Unknown is null, never a fabricated zero rating.

Points = sum(weight * rating / 4), with unknown contributing zero credit. Retain exact values for decisions; display one decimal without threshold rounding. Health thresholds are proposed Legume rules, not an external standard.

Evaluate status in order:
1. Known blocking failure -> Red, regardless of points or missing evidence.
2. Any missing/stale/invalid required evidence -> Unknown.
3. At least 85 with all ratings >=3 -> Green.
4. At least 60 -> Amber (including a failed category floor).
5. Below 60 -> Red.

Blockers: broken supported core journey, failed required check, unfinished release-critical requirement. Known blockers persist until verified clearance; expiry alone never clears them. Thus all level-3 categories yield 75/Amber; Green intentionally asks for stronger assurance. Health means evidenced behavior within scope, not absence of all possible bugs.

## Security
Keep native OpenSSF Scorecard practices results /10, tool version and individual checks; do not invent an overall security-certification percentage. Aggregate scores alone cannot override findings.

Evidence producers: OpenSSF Scorecard; OSV-Scanner for dependencies; Gitleaks CLI for secrets including reviewed history coverage; zizmor for Actions; risk-specific authorization/isolation/data tests. Selection, pinned versions, license/maintenance review and permission requirements must be verified before installation. No tool is installed by this change.

Per-repo scope determines applicable checks. An exclusion needs reviewed rationale; inaccessible or unsupported checks are not silently excluded. Preserve raw tool results separately from sanitized summaries. A report-only workflow's successful exit does not establish zero findings.

Status precedence: confirmed critical blocker -> Red; unresolved findings -> Amber; otherwise incomplete/stale required evidence -> Unknown; otherwise Green. Even Amber/Red must retain an explicit incomplete-coverage warning. Green means no unresolved findings within fully checked scope, not secure certification.

Security blockers: confirmed exposed credential, serious reachable vulnerability, failed critical security boundary. Record severity, confidence, reachability disposition and affected versions. Exceptions require owner, reason, scope, approval and expiry; retain the finding and raw score. An exception does not turn an unresolved finding Green or waive existing release rules.

## Freshness and current views
Preserve existing fleet reporting-policy.json (currently sweep-and-current with 24-hour maximum age); this proposal does not rewrite it. Proposed security freshness is 24 hours, subject to explicit activation review and resource capacity.
A changed commit invalidates affected evidence. Carry-forward requires an explicit unchanged-scope justification tied to the new assessment. Changed claims/audience trigger relevant P/H review; do not manufacture daily human reviews.
Show historical assessment time and current freshness separately. Invalidation/revocation appends a record and changes the current projection without changing the historical score. Source time and ingestion time are distinct; delayed older evidence cannot supersede newer evidence solely by arrival order. Future source timestamps are invalid.

## History and Firestore integration design
Firestore is the selected hosted-history candidate, not provisioned or authorized for cloud writes by this PR. Cloudflare receives no new score-history storage. No project/database identifiers or credentials belong in this public proposal.

Proposed logical records:
- assessments: immutable envelope, exact scope/commit/policy and per-metric ratings/status/coverage; evidence references and canonical content hash
- collection_attempts: succeeded/failed/partial attempts, separate from successful assessments
- assessment_events: corrections, invalidations, revocations and verified blocker-clearance events
- current projections: rebuildable pointers; never the historical source of truth

Use deterministic IDs, canonical serialization and atomic create-if-absent semantics. Same ID/hash is a no-op; same ID/different hash is rejected. Corrections append a superseding record. Out-of-order valid evidence is retained historically. Enforce a bounded summary size and reject raw secrets/transcripts. Record private evidence by safe IDs; access must be checked separately.

Reuse reviewed local durability patterns for offline delivery; never open a second writer against agency.db. No existing sync contract is implicitly extended. Schema, authentication, projection routing and acceptance tests need their own implementation review.

Before cloud activation verify the actual GCP project, region, free database eligibility, shared usage, account billing exposure, least privilege, explicit data classification/disclosure approval, backup/restore, indexed bounded queries and quota budgets. Budget alerts alone are not a hard spending cap. If no-new-spend operation cannot be established, remain disabled. Do not enable billing, create credentials or expand access as a workaround.

No automatic TTL/deletion. Plan retention with measured bytes and backup needs; preserve existing minimum retention and owner-review requirements. At capacity stop cloud writes safely with bounded local pending evidence and a visible blocker; do not upgrade or delete automatically. A sustainable archival/retention plan remains a rollout decision, not a promise of unlimited free storage.

For comparisons require matching repo/scope and metric meaning. Separate incompatible policy majors; record exact minor/patch and policy commit. Tool-version changes split security comparisons unless calibrated explicitly. P/H audience changes split series. Missing observations are gaps, never interpolated passes.

## Pilot and acceptance
Start with qa-kit and gate-kit using synthetic, private or approved-safe evidence. Display repo, commit, P/H/Health/Security, status, coverage, source time, expiry, blockers and evidence drilldown in the existing read-only Hub surface. Do not automatically create/remediate tasks.

The JSON fixtures provide nine Health boundary cases and integration acceptance requirements. A later implementation must convert these to executable tests covering idempotency/conflicts, stale and missing evidence, report-only scanner findings, policy changes, out-of-order delivery, privacy, quota failure, current projection recovery and execution isolation. Validate UI repeat/refresh/error states and relevant repository aggregate checks. An empty or unknown baseline is preferable to invented scores.

The candidate contains no evaluator, database adapter, installed scanner, schedule or UI implementation. Do not call the system implemented after merging configuration alone.

## Review instructions
Review this branch independently, inspect repository rules and canonical portfolio policy, and run required repo checks in an authorized environment. Report exact commit, commands, pass/fail/skip, findings and limits. Do not merge, deploy, provision, start services or enable recurring work without separate approval. Preserve concurrent work and scope changes to this proposal. Return a concise decision and implementation sequence for the owner.

## Sources inspected
- Existing qa-kit PORTFOLIO-READINESS.md, reporting-policy.json, bin/health.py and AGENTS.md
- Agency repo cards, QA mount, repository registry and hub-sync schema at 47f31020236dc0210e5d8508220a1cb64e66c15e
- [OpenSSF Scorecard](https://github.com/ossf/scorecard)
- [OSV-Scanner](https://github.com/google/osv-scanner)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [zizmor](https://docs.zizmor.sh/)
- [Firestore free quota documentation](https://docs.cloud.google.com/firestore/quotas)
Research date: 2026-09-30. Repository source inspection does not verify runtime deployment or account quotas.
