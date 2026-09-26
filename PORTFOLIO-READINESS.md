# Portfolio readiness rulebook

Policy version: **1.0.0**  
Owner: **qa-kit maintainers; Stephen Kall is the decision owner**  
Adopted: **2026-09-25**  
Reference research observed: **2026-09-22**  
Status: **Adopted for repository publication and hiring-portfolio reviews**

Canonical source: `qa-kit/PORTFOLIO-READINESS.md`. Start from
[STANDARDS.md](STANDARDS.md); maintain the complete policy only here.

A repository should be publicly showcased when a reviewer can verify what it
does, understand the builder's contribution, reproduce its central behavior,
and see sound judgment about its limitations.

Two decisions remain separate:

- **Publication readiness:** Is the repository sufficiently safe,
  understandable, and reproducible for its stated purpose?
- **Hiring usefulness:** Does it provide compelling evidence of the
  capabilities sought by a particular hiring audience?

Publication does not imply production readiness. An explicitly bounded
prototype can be publishable and valuable. A polished application can be
publishable yet provide little evidence of senior-level ownership.

## Policy authority and maintenance

This policy adds a review standard; it does not waive the existing
[engineering review contract](README.md#review-process-contract),
[release standard](../agency/docs/RELEASE-STANDARD.md), repository-specific
rules, or required publication/deployment approval. A passing assessment is
evidence for a decision, never authorization to publish, push, release, deploy,
or contact anyone. Existing mandatory gates take precedence over a score.

Record the policy version **and the qa-kit policy commit**, the evaluated
repository commit, reviewer, date, evidence, and decision in every audit.
Identify a separately assessed deployed/demo version explicitly. Never update
an old assessment in place to imply that a new version was reviewed: append a
new assessment or a versioned amendment with its reason.

Keep repository-specific reports with their owning project or approved private
evidence store. Private hiring evaluations, personal data, and confidential
evidence do not belong in this public policy. Use safe evidence identifiers
where direct links would expose private material. Other repositories link here;
they do not maintain copied rubrics.

For policy updates, use a focused reviewed change and update the revision
history. A **major** policy version changes score meaning, weights, floors,
thresholds, blockers, or decision outcomes; a **minor** version adds compatible
guidance or optional examples; a **patch** fixes wording or references without
changing decisions. This document's version is separate from qa-kit's software
release version. Do not compare scores across major policy versions without
rescoring. Even within one major version, record the exact version and commit.

Review sources and calibration when a relevant practice changes or repeated
audits expose ambiguity. Record the actual observation date; editing this file
does not refresh the underlying research. Re-audit affected evidence when code,
dependencies, deployment exposure, data, or claims change. A newer policy does
not retroactively certify an older project assessment.

## 1. What the reference sample demonstrates

This is a purposive sample of eight substantial software repositories, covering
developer tools, infrastructure, AI systems, and product applications. Star
counts are rounded GitHub display values observed on 2026-09-22. They establish
the sample's popularity criterion; they earn no quality points and are not
represented as current after that date.

“Observed” means visible in source, configuration, or project documentation.
It does not mean independently built, tested, or security-audited.

| Repository / category | Observed stars | Observed practice | Transferable solo-builder expectation |
|---|---:|---|---|
| [Ruff](https://github.com/astral-sh/ruff) — developer tooling | 49.7k | Its contribution guide maps crates, supplies lint/test commands, describes snapshot review, and explains ecosystem comparisons against real projects. [Guide](https://github.com/astral-sh/ruff/blob/main/CONTRIBUTING.md) | Explain where important logic lives; test representative behavior and regressions, including compatibility where claimed. |
| [Bun](https://github.com/oven-sh/bun) — runtime/tooling | 96.0k | Debug builds and AddressSanitizer testing are documented. Review guidance covers failure paths, resource limits, and security checks across routes to protected operations. [Testing](https://github.com/oven-sh/bun/blob/main/CONTRIBUTING.md), [review guidance](https://github.com/oven-sh/bun/blob/main/REVIEW.md) | Select checks addressing the language and system's actual failure modes. A formatter alone cannot establish correctness. |
| [Caddy](https://github.com/caddyserver/caddy) — network infrastructure | 76.0k | CI builds and smoke-tests across Linux, macOS, and Windows and runs short tests with race detection. Security policy identifies supported versions and report scope. [CI](https://github.com/caddyserver/caddy/blob/master/.github/workflows/ci.yml), [security](https://github.com/caddyserver/caddy/security) | Verify promised platforms, startup, and relevant concurrency; state supported deployment boundaries. |
| [Prometheus](https://github.com/prometheus/prometheus) — monitoring infrastructure | 66.2k | Documentation explains architecture and excludes uses requiring complete per-request billing accuracy. Release guidance describes candidates, benchmark observation, and user-facing change notes. [Overview](https://prometheus.io/docs/introduction/overview/), [releases](https://github.com/prometheus/prometheus/blob/main/RELEASE.md) | Explain unsuitable uses and release risk. Monitoring measurements must not silently become authoritative billing records. |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) — AI inference | 129.2k | Benchmarks distinguish prompt processing from generation, repeat measurements, report variation, and export model/hardware/build metadata. Tokenization and sampling time are explicitly excluded. [Benchmark docs](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md) | Make performance claims reproducible and state measurement inclusions and exclusions. |
| [vLLM](https://github.com/vllm-project/vllm) — AI serving | 92.4k | Contribution guidance supplies pytest commands, acknowledges incomplete type checking, and warns aggregate CI status can conceal blocked tests. Security docs explain API-key coverage limitations and network assumptions. [Contributing](https://docs.vllm.ai/en/latest/contributing/), [security](https://docs.vllm.ai/en/latest/usage/security/) | Inspect which tests ran. Document authentication boundaries and incomplete checks. |
| [Immich](https://github.com/immich-app/immich) — consumer application | 114.8k | README links installation, roadmap, and demo resources and emphasizes backups. Tests separate component checks, use frozen dependency installation in relevant jobs, and pin referenced actions to commits. [README](https://github.com/immich-app/immich#readme), [workflow](https://github.com/immich-app/immich/blob/main/.github/workflows/test.yml) | Provide a visible product journey, reproducible dependencies, and recovery guidance for entrusted data. |
| [Cal.diy](https://github.com/calcom/cal.diy) — scheduling application/infrastructure | 48.6k | The former calcom/cal.com URL redirected here during review. README documents environment setup, seeded local users, database setup, and end-to-end test/report commands. [Setup/testing](https://github.com/calcom/cal.diy#readme) | Reproduce a realistic workflow using synthetic data and explicit integration prerequisites. Confine development credentials to development. |

These are learning examples, not endorsements of every practice. Caddy's
inspected workflow contains an optional job allowed to fail; vLLM warns that
an aggregate status need not prove required tests ran. Inspect a badge's scope.
[Caddy workflow](https://github.com/caddyserver/caddy/blob/master/.github/workflows/ci.yml),
[vLLM CI guidance](https://docs.vllm.ai/en/latest/contributing/).

The rubric and thresholds are Legume Labs decision rules, not published hiring
standards or statistically validated predictors of hiring outcomes.

## 2. Establish scope before awarding points

Every audit identifies:

- Repository URL, exact commit, audit date, and separately evaluated release.
- Intended audience and capability the repository is meant to demonstrate.
- Maturity: experiment, demonstrable prototype, maintained tool, or operated service.
- Supported execution mode: local, hosted sandbox, self-hosted, or production.
- Critical user journey and important failure modes.
- Data, external services, privileges, and financial or irreversible effects.
- Builder's contribution, inherited components, collaborators, and material AI assistance.

Score the declared scope. A local simulator need not process live payments; a
simulator presented as a working payment platform needs its claim corrected.
An older finished project can remain useful. Age matters through dependency
exposure, reproducibility, and maintenance accuracy, not commit frequency alone.

## 3. Evidence and reviewer discipline

| Label | Meaning | Establishes |
|---|---|---|
| D — Declared | README, diagram, policy, or author statement | Intent or a claim |
| I — Inspected | Relevant implementation, assertions, configuration, or history examined | Mechanism exists within inspected scope |
| V — Verified | Inspectable execution result tied to evaluated commit and environment | Tested behavior occurred under those conditions |
| U — Unknown | Missing, inaccessible, stale, or inconclusive evidence | No affirmative conclusion |

A screenshot verifies appearance, not persistence. A test file establishes an
assertion, not a passing run. A green workflow establishes only executed jobs.
For each category, record specific evidence and a short rationale. Prefer
commit permalinks, CI runs, versioned reports, and identifiable demo builds.

1. Missing evidence earns zero demonstrated credit. Mark unknown rather than
   claiming the implementation is necessarily defective.
2. Plans earn no implementation credit. Roadmaps cannot substitute for behavior.
3. Runtime claims need runtime evidence. Documentation alone cannot verify
   reproducibility, correctness, or performance.
4. Documentation categories can be established by inspection. Clear reuse
   terms, limitations, and accurate instructions do not require production.
5. Evidence must match the evaluated version. Changed code invalidates affected
   older results; unchanged components can retain traceable evidence.
6. Reviewers score independently before reconciling against artifacts. An
   unresolved blocker or threshold-changing disagreement means hold, not an average.

No entire category is not applicable. Scale requirements to the project: a
stateless CLI can demonstrate input/output boundaries and no external transmission.

## 4. Publication readiness score: P / 100

Use integer ratings; award the highest level fully supported:

| Rating | Anchor |
|---:|---|
| 0 | Absent, contradicted, or unassessable |
| 1 | Declared or fragmentary; substantial gaps |
| 2 | Substantially implemented/documented; important verification or completeness gaps |
| 3 | Meets the category's evidence standard within declared scope |
| 4 | Meets level 3 plus stronger validation of important risks, boundaries, or changes |

More files, tools, tests, or prose do not automatically increase a score.
**P = sum(weight × rating / 4).** Retain the exact result for threshold decisions;
display one decimal place without rounding upward into a passing band.

| Category | Weight | Level 3 evidence | Examples supporting level 4 |
|---|---:|---|---|
| Architecture | 12 | Component/data-flow explanation matching inspected code; entry points, state ownership, dependencies, trust boundaries, and consequential choice rationale. | Traced failure/recovery path; meaningful changes preserve boundaries. |
| Code quality | 12 | Main journey and highest-risk module reviewed; clear naming/control flow; appropriate input validation, errors, cleanup; relevant static checks pass. | Invariants and regression fixes remain clear under difficult inputs or changes. |
| Tests and CI | 18 | Inspectable passing checks on evaluated commit; substantive assertions for core journey, meaningful failure, relevant boundaries; critical checks cannot silently skip or ignore failure. | Relevant property, concurrency, compatibility, fault-injection, or evaluation tests with actionable failures. |
| Security, privacy, and provenance | 18 | Data/privilege boundaries; dependencies/findings reviewed; secret scan of intended publication history/artifacts; synthetic examples; reuse terms/attribution; applicable authorization/isolation checks; vulnerability contact. | Verified abuse resistance, retention/deletion, and supply-chain/recovery controls proportionate to exposure. |
| Reproducibility | 12 | Successful clean-environment run using documented prerequisites, dependency resolution, configuration, sample data, commands, and expected results; hardware, paid services, and resource costs disclosed. | Independent replay or multiple clean environments, with troubleshooting/reset instructions. |
| Documentation | 8 | README explains user, problem, supported behavior, setup, example output, limitations, architecture location, and verification commands; links/examples match evaluated version. | Newcomer completes workflow and diagnoses common failures without author help. |
| Releases and change safety | 6 | Identifiable tested version or named snapshot; user-relevant changes, compatibility expectations, migration/recovery instructions for persistent-state changes. | Repeatable artifact creation, provenance, and verified upgrade/recovery where relevant. |
| Maintenance | 4 | Accurate active/paused/archived status, known issues, realistic support expectations; dependency review and reproducibility check at audit date. | Substantive diagnosis, correction, and recurrence prevention example. |
| Demo and product story | 5 | Complete representative journey, believable synthetic inputs, observable output; working demo or versioned recording/output plus runnable instructions; mocks/dependencies identified. | Reviewer explores a consequential edge case and understands practical benefit without narration. |
| Honesty of claims | 5 | Material claims have evidence or are labeled hypotheses; authorship, simulation, deployment scope, and limitations are accurate. | Quantified claims include method, baseline, denominator, uncertainty, and reproducible results. |
| Total | 100 | | |

A project meeting level 3 throughout earns 75/100, intentionally sufficient
for publication. Solo builders need not be exceptional in every category.

## 5. Critical blockers and publication decisions

A blocker overrides the score. Unknown clearance of a safety or ownership
blocker means hold; it does not establish a proven violation.

| Blocker | Decision affected | Clearance evidence |
|---|---|---|
| Exposed credentials, confidential/personal records, or unclear authority to publish included assets | All publication | Scope reviewed, exposure resolved; exposed live credentials revoked/rotated; history and distributed artifacts accounted for. |
| Serious reachable vulnerability or unsafe default within promoted mode | That executable release or hosted demo | Fix or verified containment; instructions/claims updated. A disclaimer alone is not containment. |
| Broken or unreproducible core workflow | Publication as usable tool or demonstrable application | Traceable successful run, or explicitly narrowed archival/experimental scope. |
| Missing correctness controls for a claimed consequential operation, such as duplicate charges or cross-user access | Showcase of that capability | Inspected implementation and passing risk-specific tests. |
| Fabricated results, concealed mocks, misleading ownership, or unsupported production/compliance claims | Publication and hiring showcase | Corrected claims and provenance. |
| Release/demo/evidence materially disagree on version or behavior | Promotion of that release/demo | Version alignment and affected checks repeated. |

| P score | Decision |
|---|---|
| P < 55 | No-go as a usable portfolio project |
| 55 ≤ P < 70 | Hold; close evidence/implementation gaps |
| 70 ≤ P < 85 | Go only with no blockers, all ratings ≥2, and security/privacy/provenance, reproducibility, and honesty each ≥3 |
| P ≥ 85 | Strong publication evidence, subject to the same blockers/floors; not blanket production certification |

An explicitly labeled historical archive can undergo a narrower review when
it cannot run today. Record **archive only—not approved as a usable project**;
do not represent it as passing P. An archival designation cannot waive
publication safety, ownership, or honesty blockers.
Use this exception only for an explicitly historical archive that cannot run
today; it cannot clear a broken workflow for a project still presented as a
usable tool. A changed scope requires a new assessment. An experimental label
alone does not clear a failed core workflow within the newly declared scope.

Evaluate a hosted demo separately. Public source can pass while an
internet-facing deployment remains no-go.

## 6. Hiring usefulness score: H / 100

Score independently for each intended audience using the same integer 0–4
anchors and weighted formula: **H = sum(weight × rating / 4)**. Retain exact
results for decisions and display one decimal without rounding up to pass.

| Dimension | Weight | Level 3 evidence |
|---|---:|---|
| Audience relevance | 20 | Specific connection between demonstrated work and target-role decisions/responsibilities. |
| Builder's ownership | 20 | Credible account of what the builder designed, implemented, validated, operated; attributable code, history, decisions, or artifacts. |
| Senior-level judgment | 25 | At least two consequential decisions: constraints, alternatives, tradeoffs, failure consequences, and changes needed at greater scale. |
| Validation and outcomes | 25 | Central idea tested against a meaningful baseline or success criterion; results and limits visible. Customers/revenue are not mandatory. |
| Review efficiency | 10 | Reviewer quickly understands the point, sees central behavior, and reaches strongest implementation/evidence without searching the entire repo. |
| Total | 100 | |

Level 4 requires particularly compelling inspectable proof, such as independent
reproduction, measured iteration after feedback, or a clear resolution of a
difficult correctness/performance tradeoff, not stronger adjectives.

| H score | Decision for that audience |
|---|---|
| H < 60 | Omit |
| 60 ≤ H < 75 | Supporting example for a specific conversation |
| 75 ≤ H < 85 | Feature-worthy if publication passes |
| H ≥ 85 | Flagship candidate if publication passes |

Featuring also requires relevance, ownership, judgment, and validation each ≥3.
Communication cannot compensate for missing substance. A high-H project with
a publication blocker may support a separately reviewed sanitized case study;
its score never authorizes repository exposure.

## 7. Audience-specific evidence

These requirements depend on the project's claims. Do not add unrelated features.

| Audience | Strong evidence | Claims needing scrutiny |
|---|---|---|
| Senior AI | Versioned evaluation set, baseline, model/configuration, quality/latency/cost results, error analysis, provider failures, agent permission/tool boundaries. | Accurate/autonomous/cheaper/production-ready based on selected examples, irreproducible prompts, or hidden human intervention. |
| Senior product | Defined user problem, complete journey, discovery/friction evidence, reasoned scope, usability/accessibility, iteration linked to feedback. | User enthusiasm without observations, or features presented as demand. |
| Monetization | Value metric, pricing hypothesis, event definitions, entitlements, cost assumptions; sandbox billing lifecycle tests where billing exists. | Revenue/conversion without dates, denominators, cohorts, and actual-versus-simulated transaction labels. |
| Economic infrastructure | Invariants/state transitions, exact amounts/units where money exists, idempotency, concurrency, reconciliation, auditability, recovery. | Exactly once, ledger, settlement, or financial-grade without retry/partial-failure/conflict evidence. |

AI evaluation separates tuning fixtures from assessment fixtures, documents
grading, and reports failures. A fixed seed alone does not establish
cross-environment reproducibility.

Monetization evidence distinguishes causal experiments, correlations, and
modeled scenarios. A clearly scoped simulator can demonstrate commercial judgment.

Economic infrastructure traces duplicate, delayed, reordered, and missing
events. Where balances exist, show preserved invariants and discrepancy
detection. Prometheus's explicit billing limitation illustrates why this
boundary matters. [Suitability guidance](https://prometheus.io/docs/introduction/overview/).

## 8. Solo-builder calibration and portfolio selection

Expect a small amount of strong evidence: one working supported setup, one
complete journey, tests protecting consequential behavior, concise architecture,
a few well-explained decisions, and honest status/limitations/outcomes.

Do not require multiple maintainers, enterprise governance, daily commits,
broad platform coverage, paid observability, a large test count, or a live
service for every project. A monolith can earn full architecture credit; a CLI
transcript can satisfy a demo; an accurately documented paused project can
earn maintenance credit. Existing mandatory Legume Labs checks still apply.

AI assistance is neither a bonus nor a penalty. Assess whether the builder can
explain the design, identify generated/inherited parts, verify consequential
behavior, and take responsibility. Commit volume alone does not prove ownership.

Select roughly three to five complementary projects. Prefer distinct evidence,
such as AI evaluation, observed product learning, and infrastructure correctness
under failure. Additional projects should add a capability or stronger proof.

For each featured project provide:
**Problem → demonstration → contribution → consequential decisions → evidence → limitations.**

Suggested reading targets are 30 seconds for relevance, five minutes for the
central result, and a deeper path to implementation/validation. These are
portfolio design targets, not universal recruiter-behavior claims.

## 9. Standard audit template

Copy this template into an assessment, not the policy itself. Keep evidence and
decisions in the appropriate public or private project record.

```text
Policy version / qa-kit policy commit:
Repository URL / evaluated commit / release / demo version:
Reviewer / date:
Target audience:
Maturity / supported execution mode:
Critical journey / highest-risk behavior:
Builder contribution / inherited code / material AI assistance:

Evidence index:
E1 — safe permalink or evidence ID; D/I/V/U; supported claim; version/environment.
Repeat for each material artifact.

Blockers: clear / present / unknown.
For each: affected scope, evidence, consequence, exact clearance requirement.

Publication ratings (0–4), with evidence IDs and one-sentence rationale each:
Architecture __; code __; tests/CI __; security/privacy/provenance __;
reproducibility __; documentation __; releases __; maintenance __;
demo __; honesty __.
P = __/100. All floors satisfied: yes/no. Blockers cleared: yes/no.

Hiring ratings (0–4), with evidence IDs and one-sentence rationale each:
Relevance __; ownership __; judgment __; validation __; efficiency __.
H = __/100 for [audience]. All floors satisfied: yes/no.

Verification: executed/inspected checks, commit, environment, results,
skips, inaccessible evidence, retained report identifiers.
Claim check: claim → evidence → supported / qualified / unsupported.

Decision:
Publication: go / hold / no-go / archive only.
Hosted demo: go / hold / no-go / not in scope.
Portfolio: omit / supporting / feature / flagship candidate.
Decision owner / date / separate action authorization reference, if any:

Three strongest proofs:
Up to three required fixes, with acceptance evidence:
Uncertainties / reviewer disagreements and disposition:
Re-audit trigger: relevant code, dependency, deployment, data, or claim changes.
Previous assessment reference and reason for amendment, if applicable:
```

## Limitations

The sample is current to its recorded observation date but non-random. Its
funding, staffing, histories, and operational requirements differ from solo
work. Visible practices show possible standards, not consistent execution of
every practice in every project.

Sources include mutable default branches, documentation, and rendered GitHub
snapshots. Counts and contents change. These observations are not comprehensive
source audits, independent benchmark replications, or verified current CI
success. The original research evaluated no Stephen Kall repository and
approved none for publication or showcase. Policy adoption likewise certifies
no repository; each needs a scoped assessment.

## Revision history

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-09-25 | Adopted the 2026-09-22 research rulebook as the canonical qa-kit standard, with policy ownership/versioning, separate action authorization, immutable audit references, private-evidence handling, and reusable template. |
