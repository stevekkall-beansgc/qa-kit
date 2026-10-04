# README human readability standard

Version: **1.0.1**, adopted October 4, 2026 by Stephen Kall, including the
informative-visual quality clarification. Previous published baseline: **1.0**.
Owner: QA Kit maintainers.

Every Legume Labs README is a front door for its intended human reader.
Someone unfamiliar with the repository should understand what it does, why
they might use it, and where to start before encountering internal process.
Technical rigor belongs behind that front door, not in place of it.

## Scope

Apply this standard to public and private repositories, products, libraries,
infrastructure, experiments and archives. Name the actual audience: a user,
developer, operator or maintainer, not automatically a hiring manager.
An archive explains its historical purpose and inspection path; it need not
pretend to offer a working installation. A private repo does not need a public
demo. An internal service names access prerequisites without exposing secrets.

Maintain this standard here. Other repos link to it through their engineering
standards instead of copying the rules. Its review feeds
[Documentation and Review efficiency](PORTFOLIO-READINESS.md#4-publication-readiness-score-p--100)
in the portfolio scorecard; it does not certify software behavior.

## Write for the reader

1. **Lead with purpose and benefit.** Explain the name, intended reader,
   concrete problem and useful result in plain language. Do not open with
   review approval, a commit hash, scanner results or policy compliance.
2. **Give one obvious next step.** Offer a supported quickstart, usable
   example, demo or inspection path with expected output. Put essential
   prerequisites and effects before commands. Link deeper setup and reference
   material rather than making the reader search the whole repository.
3. **Show the result.** Use a short real output, example, screenshot or direct
   proof link where it helps. Label synthetic data and estimates accurately.
   A useful visual explanation belongs with the reader path, not hidden in
   an audit appendix. Decoration and badges are not substitutes for evidence.
4. **Separate three layers.** README: purpose, starting path, result, status
   and navigation. Guides: detailed setup, architecture, decisions and
   troubleshooting. Evidence/agent records: provenance, hashes, review
   findings, historical observations and editing instructions. Keep a precise
   source reference near a claim when necessary, not a repeated audit narrative.
5. **Keep essential limits, once.** Keep payment mode, data handling, required
   permissions, supported environment and estimate basis beside the relevant
   claim. Move supporting provenance to linked records. Delete repetitions
   and self-protective commentary, not facts that prevent a wrong decision.
   Never turn an unsupported claim into confident marketing.
6. **Use a natural, consistent voice.** Prefer concrete verbs and familiar
   terms; explain acronyms and whimsical names. State contribution and material
   AI assistance plainly where relevant. Do not imply personal implementation,
   adoption or integration that the evidence does not support.
7. **Show the right scope.** A product explains its journey; a library shows
   a small API example; infrastructure shows the operator/developer entry;
   a portfolio gives a concise project/status/proof table and one featured
   path. A narrow technical case study must not silently replace a requested
   portfolio overview. Use only verified status labels.

Aim to make the purpose apparent in roughly 30 seconds and the starting path
easy to find within two minutes. A short first screen and about 600 words are
useful editing targets for a portfolio, not universal length limits. A long
reference README can pass when its opening and navigation work. No banned-word
list, negation quota, diagram count or reading-speed claim proves quality.

## Visual explanations

Visual explanation is a first-class part of our READMEs. Informative diagrams
take priority over decorative illustration. Show enough detail to explain the
project: component responsibilities, meaningful relationships, inputs and
outputs, a user journey, decision points or ownership boundaries. Match the
visual to the reader's question, rather than making every repo use the same
layout. Simple repositories need not acquire unnecessary diagrams.

For every visual, answer: **What can the reader understand or do because of
this visual?** An attractive scene or a row of named boxes does not satisfy
this requirement unless it explains something useful. Decoration may complement
the entry; it must not displace informative diagrams, examples or architecture
detail. Show useful maps and flows beside the relevant explanation, with
full-size links and equivalent prose where needed.

Do not remove or bury useful existing visuals merely to shorten a README.
Before a rewrite, inventory its images and diagrams, including those in earlier
versions. Retain, simplify or replace them with an equally useful explanation;
record a reason for an omission. Preserve explanatory coverage, not just asset
presence. A prettier or shorter replacement that drops supporting systems,
component responsibilities, meaningful connections or important flow steps is
a regression. Refresh stale labels rather than presenting an old architecture
or version as current.

Keep diagrams editable (for example, Mermaid source plus a rendered SVG).
Use readable labels at ordinary README width, meaningful alt text and a short
prose explanation. Label estimated, synthetic, planned and human-carried steps;
arrows must not invent automation or deployed integration. Verify that assets
load, text is legible and the visual agrees with the evaluated source.

This clarifies the existing Proof, Structure, Accuracy and Regression reviews;
it adds no score category, numerical floor or diagram quota.

## Accepted quality reference

The Legume Labs README restoration accepted by Stephen on October 4, 2026
is the portfolio reference for explanatory depth: separate product and tool
tables, a portfolio/delivery map, core and supporting agent capabilities with
human boundaries, and a conditional release flow with inspection steps.
The visuals explain how the work fits together, rather than merely picturing
the project names.

Compare rewrites with the owning repo's strongest accepted version and record
its artifact identity. Adapt this reference to the repo's purpose; it is not a
mandatory layout, diagram count or demand for a portfolio map in every repo.
Owner design acceptance is not unfamiliar-reader usability research or current
runtime qualification. Historical and proposed relationships remain labeled.

## Review checklist

For a new README, a material README/navigation change, or a new publication or
portfolio review, record each item as pass, fail or unknown with a location.
Use the same checklist for a before/after comparison; truth takes precedence
over shortening. Do not silently upgrade unchanged repos.

- [ ] Purpose: an unfamiliar intended reader can explain what it does, for
  whom, and why it is useful from the opening.
- [ ] Start: one obvious supported next step and expected result are reachable;
  prerequisites, access and consequential effects are visible before use.
- [ ] Proof: the strongest example/result is easy to reach and its scope is
  clear; synthetic, estimated and observed output are distinguished. Useful
  visual explanations are visible with the relevant reader path and answer
  a concrete reader question through useful roles, relationships or flow.
- [ ] Structure: reader guidance comes before internal process; deeper setup,
  architecture and evidence have useful, working navigation.
- [ ] Tone: plain, consistent language; no unexplained names, caveat stacks,
  repeated self-description or reviewer verdicts crowding out the product.
- [ ] Accuracy: current capability, maturity, contribution and AI assistance
  match evidence; essential limitations remain beside affected claims.
- [ ] Scope: the README represents the repository's intended purpose and
  audience; internal/private requirements and archives are handled honestly.
- [ ] Regression: the new entry is at least as clear as the previous entry,
  preserves explanatory coverage, useful visuals and meaningful incoming
  links/accessibility, and has no material new misunderstanding. Compare with
  the strongest accepted reference; record lost detail and the usefulness of
  replacements, not just asset presence, appearance or word count.

A failed or unknown required item means **revise** or **unknown**, not ready.
Do not waive an item as irrelevant: use the scope-appropriate inspection path
for archives or access instructions for private tools instead of a public demo.
Content safety and factual correctness remain independent requirements.

## Human readability rating

Award the highest fully supported integer rating. Record evidence and a brief
rationale, not just a number. These anchors apply to the README entry experience,
not implementation quality or popularity.

| Rating | Evidence |
|---:|---|
| 0 | Entry is missing, materially misleading or cannot be assessed. |
| 1 | Purpose or audience is buried; jargon/internal review process dominates; no useful starting path. |
| 2 | Purpose is partly clear, but a required checklist item fails or remains unknown; navigation, benefit or claim boundaries cause material confusion. |
| 3 | All checklist items pass by recorded review: purpose, useful starting path, result and scope are clear without author narration; evidence and essential limits remain accessible. |
| 4 | Level 3 plus an unfamiliar intended-reader review demonstrates successful navigation and explanation of purpose/result/limits; before/after findings and any corrections are retained. |

**Ready requires a rating of at least 3 and every checklist item passing.**
An unfamiliar review is useful for substantial rewrites and for level 4;
level 3 does not require recruiting a user. An author self-review must be
labeled as such, not claimed as independent. An agent read is a diagnostic,
not human usability research, external adoption or actual user feedback.

## Review record

Keep records with the owning project or its approved private evidence store.
Do not turn this checklist into another block of compliance prose in the README.

```text
Repository / evaluated commit or candidate diff:
README standard version / policy version and commit:
Reader and purpose:
Reviewer / date / author, unfamiliar person or agent diagnostic:
Checklist: purpose __; start __; proof __; structure __; tone __;
accuracy __; scope __; regression __ (pass / fail / unknown + locations).
Readability rating (0–4):
Evidence and navigation: actual answers, paths inspected, observed mismatches.
Visual preservation: prior assets; retained/replaced/omitted and why; render check.
Visual usefulness: reader question; roles/relationships/flow explained; comparison reference and gaps.
Before/after: improvement, regression or first entry; previous artifact ID.
Result: ready / revise / unknown
Required correction and recheck evidence:
```

## Rollout

This is the adopted central standard, not an assertion that every repo conforms.
Review each repo on its next material README change or publication assessment;
do not rewrite the fleet automatically. First repair the Legume Labs entry,
then prioritize intended featured repos. Code-only changes with no entry/claim
impact need not create a new readability exercise.

The current `bin/check_docs.py` checks structural documentation contracts; it
does not automatically judge human readability. Automated tests protect the
links and checklist/scorecard wiring, not the prose's meaning. A green CI badge
cannot replace the recorded review. No runtime Health/Security score, external
publication, release, deployment or outreach is authorized by this standard.
