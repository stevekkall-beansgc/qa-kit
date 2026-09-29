# Fleet validation inventory — local source snapshot

Date: 2026-09-28. **20 of 20 QA manifest repos recorded; all mappings proposed.**
Companion: [fleet design and candidate profiles](FLEET-VALIDATION-DESIGN.md).

Coverage anchor: [manifest.json](manifest.json) at this worktree's base commit
`5abb9031b9cd1166823d913c1dd437d47c283708`, SHA-256
`86f730ef34a62448fc0b1533163723b8010d92a1b3b66deef6bdda985d472e49`.
This is the inventory scope, not an assertion that every caller loads that manifest.
Inventory updates should refresh the snapshot and mappings explicitly.

## Evidence and interpretation

Sources are locally available manifests, workflow files, package metadata and
guidance, plus the supplied three-agent local inventories. Their findings were
incorporated without executing repository tests or live operations. Workflow and
manifest declarations describe intended checks, not successful outcomes. Specific
service/fixture details supplied by the inventory reviews are called out below.
No Job Search datasets, application content or generated artifacts were inspected.

`M<n>` links to this QA manifest's declaration. Other source locators are relative
to `~/beans`, followed by a one-based line; these refer to canonical local source
snapshots, not checked remote content. They remain useful in an isolated worktree
without constructing misleading sibling links.

Global unknowns apply to every row: remote branch protection, registered runner
state/availability, actual current remote tag resolution, live workflow outcomes,
and whether hosted billing restrictions also block self-hosted dispatch. No row
grants runner permission or certifies coverage. Existing `active` / `unit-only`
statuses are registry metadata, not fresh passes.

Candidate profile abbreviations: **PC** portable-core; **OI** offline-integration;
**PA** package-acceptance; **NL** native-linux; **NM** native-macos;
**PL** protected-local; **LO** live-observation. They are composable: PC+OI+NM is
valid in principle, subject to per-task requirements and authorization review.

## Per-repo inventory

| Repo / manifest status | Current declared validation shape | Candidate profiles / capabilities | Gaps and unresolved evidence | Local source locators |
|---|---|---|---|---|
| **beanfit-app** / active | `npm ci`, `npm test`, `npm run test:e2e`; reusable gate v0.4.18 with full checks | PC+OI; Node, locked npm dependencies, pinned external BeanFit CLI fixture | Supplied inventory identifies CLI fixture consumption. Record its revision, checkout placement and consuming tasks; qualify clean-checkout setup and E2E before changing the pin | [M11](manifest.json#L11); `products/beanfit-app/.github/workflows/gate.yml:6`; `platform/gate-kit/.github/workflows/compliance.yml:244` |
| **beanfit** / active | Python unit with PYTHONPATH; manifest offline E2E. CI adds Python 3.10/3.13 across macOS/Linux/Windows for PRs, system-Python Mac pushes, pinned lint, activation and install smoke. Separate live catalog workflow | PC+OI+PA+LO; Python/OS variants, typed path env, packaging and public registry network scope | Manifest does not express full matrix/lint/package coverage; its offline E2E command differs from activation CI. A local system interpreter cannot represent all required variants; live catalog remains separate | [M40](manifest.json#L40); `products/beanfit/.github/workflows/ci.yml:17,45,50,65`; `products/beanfit/.github/workflows/catalog.yml:16` |
| **agency** / active | Python venv/bootstrap plus optional component bootstrap; pytest unit and external-session E2E; gate v0.4.11 full | PC+OI; explicit Python/tool dependencies, isolated venv, subsystem fixture requirements | Bootstrap is a manifest shell program with runtime fallback. Repo tests' effects and fixture requirements need explicit declarations. Release preflight must share setup semantics rather than relying on an already-prepared checkout | [M66](manifest.json#L66); `platform/agency/.github/workflows/gate.yml:14`; `platform/agency/deploy/release_controls.py:139` |
| **beanlaunch** / active | Shell unit entrypoint; beans-mac test and gate lanes; gate v0.4.22, full false | PC; shell/tool requirements; NM only for requirements demonstrated by task review | Runner label alone does not establish platform need. Preserve current event scope; determine environment/mocking assumptions before generalizing or providing hosted parity | [M98](manifest.json#L98); `platform/beanlaunch/.github/workflows/test.yml:13`; `platform/beanlaunch/.github/workflows/gate.yml:12` |
| **fantasy-draft-assistant** / unit-only | Python unittest; gate v0.4.14 explicitly selects beans-mac, including declared PR event | PC; Python; PL only if task/input review establishes a need | Existing PR-to-local routing needs an explicit trust disposition before enrollment. Dataset/fixture safety and exact runtime requirements are not established by the gate declaration | [M115](manifest.json#L115); `fantasy-draft-assistant/.github/workflows/gate.yml:6,14,18` |
| **bean-sched** / active | Base snapshot manifest runs `unittest test_sched`; separate test lane runs discovery and stdlib checks, hosted macOS for PRs/local Mac otherwise; gate uses hosted Ubuntu for PRs and full true. Isolated QA candidate `6a137ec` adds the repo-owned `python3 scripts/offline_scheduler_e2e.py` E2E, with an offline/disposable-fixture note | PC+OI; Python, shell/OS assumptions, isolated scheduler fixtures | Owner reports paired exact-candidate QA/Bean Sched proof for QA Kit `6a137ec` + Bean Sched `47871fd`: docs/unit/e2e 5/5, clean before/after; receipt `outputs/qa-kit-remediation-validation-2026-09-28/run-20260928T161846Z.json`. This report has not been independently re-run here. The base fleet manifest and currently published Gate pins remain unchanged; do not claim hosted E2E coverage until a compatible immutable control bundle is reviewed and adopted | [M136](manifest.json#L136); candidate manifest commit `6a137ec`; `platform/bean-sched/.github/workflows/test.yml:14,21`; `platform/bean-sched/.github/workflows/gate.yml:14` |
| **model-harness** / active | Python unittest; beans-mac gate v0.4.22, full false | PC initially; add OI or LO only for explicitly classified tasks | Workflow/manifest do not prove offline/model/network behavior or a macOS requirement. Qualify fixtures, runtime and effects before automatic local execution | [M154](manifest.json#L154); `labs/model-harness/.github/workflows/gate.yml:14,18` |
| **beanmind** / active | Unit and subprocess E2E in manifest. Validation additionally checks/queries knowledge, performs capture smoke, stdlib and continuity acceptance; same-repository PR/local routing | PC+OI+PL; Python, subprocesses, confined knowledge fixtures, explicit input/write roots | Supplied inventory reports knowledge-file reads/mutations; workflow capture step visibly writes. Split disposable synthetic acceptance from authorized canonical knowledge access. Review PR routing and reconcile differing E2E selections | [M173](manifest.json#L173); `mind/beanmind/.github/workflows/validate.yml:13,33,39,45`; `mind/beanmind/.github/workflows/gate.yml:15` |
| **skillz** / active | Python unit and install-doctor E2E in manifest; separate catalog validation/stdlib workflow, freshness and tool-scan automation | PC+OI+LO; Python, confined installation fixtures, catalog checks, separate public-network observations | Keep network automation and its write effects outside deterministic validation; inventory discrepancies in clocks are observations, not authority to change them. Reconcile catalog checks with manifest unit scope | [M205](manifest.json#L205); `catalog/skillz/.github/workflows/validate.yml:17`; `catalog/skillz/.github/workflows/freshness.yml:3`; `catalog/skillz/.github/workflows/tool-scan.yml:3,18` |
| **job-search** / active | Manifest npm unit plus scanner-plan E2E. Hosted CI Python 3.12/Node 22 adds repository/artifact and model/tool/schema checks; push compliance uses beans-mac | PC plus separately authorized PL where necessary; Python+Node, explicit data scope and private-source variants | Command coverage differs. **Script/data safety is unknown under this task's access restrictions**; no runtime validation or automatic migration is permitted from this inventory. Preserve the completed release state | [M234](manifest.json#L234); `labs/job-search/.github/workflows/ci.yml:13,18,21,23,27,30`; `labs/job-search/.github/workflows/gate.yml:5,9` |
| **beanlabs** / active | npm component setup plus Python unit/offline flows. Custom prediction gate pins QA/CLI, Python 3.14, Node 22 and SQLite feature; additional design-system and Swift/Xcode compilation lanes | PC+OI+NM; Python/Node, Worker/D1/loopback, pinned native wheels, node:sqlite, Swift/Xcode readiness | Worker/D1/wheel requirements come from supplied inventories and custom setup declarations; preserve per-task pinning. Swift compile is not hardware inference acceptance. Review same-repository PR/local routing and aggregate gate dependency chain | [M255](manifest.json#L255); `labs/beanlabs/.github/workflows/gate.yml:49,55,61,67,69,89`; `labs/beanlabs/.github/workflows/ane-lab.yml:24,29,77`; `labs/beanlabs/.github/workflows/design-system.yml:15,44` |
| **bean-commons** / unit-only | Python suite; hosted matrix 3.12/3.13, local Mac 3.12/3.14; separate gate v0.4.11 | PC+OI as required by fixture review; explicit Python/OS matrix variants | Current matrices differ. A 3.14 local pass cannot stand for hosted 3.13 coverage; decide required variants and support claims explicitly | [M282](manifest.json#L282); `platform/bean-commons/.github/workflows/ci.yml:24,34,39`; `platform/bean-commons/.github/workflows/gate.yml:7` |
| **jumping-beans** / unit-only | Node product check in manifest and hosted Node 22 workflow; separate deploy workflow; gate v0.4.4 | PC; Node and declared repo artifacts; PA only if additional artifact acceptance is registered | Resolve old gate/manifest coverage. Keep authenticated deployment effects and provenance gates independent; do not infer browser/live acceptance from product checks | [M303](manifest.json#L303); `products/jumping-beans/.github/workflows/checks.yml:9,14,15`; `products/jumping-beans/.github/workflows/gate.yml:7`; `products/jumping-beans/.github/workflows/deploy-cloudflare.yml` |
| **jumping-beans-v2** / unit-only | Manifest product check; hosted Node 22 first builds inventory index then checks product; separate protected deployment; gate v0.4.8 | PC; Node, explicit generated-index prerequisite/effects; separate deployment authority | Manifest lacks the CI index-generation step. Determine generated-output ownership/cleanliness and preserve deployment's exact-release provenance | [M319](manifest.json#L319); `products/jumping-beans-v2/.github/workflows/checks.yml:18,19,20`; `products/jumping-beans-v2/.github/workflows/gate.yml:13`; `products/jumping-beans-v2/.github/workflows/deploy-cloudflare.yml:45` |
| **picks-v0** / unit-only | Manifest Node test argv; hosted Node 22 CI additionally verifies packaged assets, builds and runs component checks/runtime checks; gate v0.4.9 | PC+OI+PA; Node/npm, frozen installs, packaged asset checks, declared component/service requirements | CI coverage exceeds manifest. Preserve prerequisite order and clarify shell glob versus direct argv expansion; classify build outputs and component runtime effects before migration | [M335](manifest.json#L335); `picks-v0/.github/workflows/ci.yml:20,50,52,83,89`; `picks-v0/.github/workflows/gate.yml:13` |
| **bean-labs** / unit-only | Showcase checker under registry name bean-labs; hosted Python validation; gate v0.4.23 | PC; Python, repo-local showcase policy/assets | Keep registry/display/path identity distinct. Resolve effective gate/manifest pin and runtime; static checker does not imply live portfolio availability | [M353](manifest.json#L353); `showcase/beanlabs-showcase/.github/workflows/validate.yml:13,17`; `showcase/beanlabs-showcase/.github/workflows/gate.yml:14` |
| **qa-kit** / unit-only | Manifest shell self-check varies scope on CI; hosted Python 3.12 directly runs tests plus stdlib; gate v0.4.11 | PC+OI; Python, disposable fixtures, loopback tests, isolated docs/standards validation | Portable suite and fleet checks need explicit separation; CI bypasses shared script. Prototype is not enrolled. Preserve check identities and qualify gate runtime before using this repo as a pilot | [M369](manifest.json#L369); `platform/qa-kit/bin/qa_selfcheck.sh:6`; `platform/qa-kit/.github/workflows/test.yml:14,15,16`; `platform/qa-kit/.github/workflows/gate.yml:5` |
| **gate-kit** / unit-only | Python unit manifest; hosted 3.12 unit+stdlib; separate workflow-security lane; reusable workflow has repo-specific setup/routing | PC; Python, workflow-policy analysis, immutable control bundles; OI where synthetic fixtures require it | Unit command alone omits stdlib/security lanes. Current source and historical reusable tags load different manifests. Retain guards and external compliance check identity during consolidation | [M385](manifest.json#L385); `platform/gate-kit/.github/workflows/test.yml:19,20,21`; `platform/gate-kit/.github/workflows/workflow-security.yml`; pin table below |
| **agents** / unit-only | Beanstalk package/guidance requires Python 3.14; manifest venv setup accepts >=3.12. Trusted push gate v0.4.13 uses beans-mac with canonical locking/source checks and long timeout | PC+PL; Python 3.14, isolated venv, canonical-source equality, shared lock, resource/time budget | Runtime declarations conflict. Preserve canonical lock and source guards; do not substitute ephemeral checkout semantics or infer other interpreters are supported | [M406](manifest.json#L406); `catalog/agents/pyproject.toml:9`; `catalog/agents/AGENTS.md:25,41,43`; `catalog/agents/.github/workflows/gate.yml:3,7`; `platform/gate-kit/AGENTS.md:43` |
| **bean-counter** / active | Setup+unit+E2E scripts for pinned Rust/Python, offline SQLite; hosted full gate v0.4.19. Separate Ubuntu 24.04 x86_64 package build/install/proof lane uses Rust 1.98.1 | PC+OI+PA+NL; Rust/Python/Node, SQLite, target ABI, archive checksums and exact-source installation proof | Preserve independent artifact proof, not just unit success. Current accepted scope is local SQLite; deferred stores do not become supported via a generic profile | [M435](manifest.json#L435); `products/bean-counter/.github/workflows/gate.yml:17,20`; `products/bean-counter/.github/workflows/setup-linux-candidate.yml:18,33,39,48`; `products/bean-counter/AGENTS.md:19,22` |

## Locally inspected control pins

These pairs were read with local Git object lookup in
`platform/gate-kit/.github/workflows/compliance.yml`. No fetch or remote tag
verification was performed. The last row describes locally available HEAD source,
not what every consumer runs. Tags alone are not future evidence-bundle identities.

| Local workflow ref | Gate CLI ref it checks out | QA manifest ref it checks out | BeanFit fixture ref | Source lines in that workflow version |
|---|---|---|---|---|
| v0.4.11 | v0.4.4 | v0.4.0 | v0.1.1 | 35–48 |
| v0.4.13 | v0.4.4 | v0.4.0 | v0.1.1 | 231–244 |
| v0.4.19 | v0.4.4 | v0.6.1 | v0.4.0 | 231–244 |
| v0.4.22 | v0.4.4 | v0.6.1 | v0.4.0 | 232–247 |
| Current local source snapshot | v0.4.4 | v0.6.6 | v0.4.0 | 232–247 |

Other caller tags listed in the repo table were observed in caller files; their
transitive refs are not resolved by this table. Beanlabs also declares a custom
QA checkout at `dc4546904f2f95cc17d879967ad1edc3a4251782` and Gate CLI at
`bbf2f16096d6c2e13228de2f68c804fdff8da7d8`, then depends on that job before its
legacy reusable gate. Keep that dependency chain in the adoption review.

## Shared gaps and adoption dispositions

1. **Coverage:** manifest unit/e2e labels do not fully describe matrix, static,
   package, native or operational workflow coverage. Map tasks before deduplicating.
2. **Execution:** `platform/qa-kit/bin/run_all.py` blocks tests after setup failure;
   `platform/gate-kit/bin/compliance.py:217` continues after recording setup failure;
   `platform/agency/deploy/release_controls.py:177` selects only unit/e2e. Timeouts
   and environment handling also need a common contract.
3. **Authority/data:** fantasy PR routing, same-repository PR/local routes, Beanstalk
   canonical state and BeanMind knowledge mutation need explicit dispositions.
   Job Search remains unqualified for runtime adoption under the current data scope.
4. **Environment:** Python matrices, Python 3.14 package requirements, Swift/Xcode,
   Node features, native wheels, locked Rust and external fixtures cannot be reduced
   to a runner label or a broad language version string.
5. **Release proof:** preserve native artifact identity and actual exact-SHA GitHub
   compliance evidence. Hosted billing blockage is unavailable evidence; record
   it separately from test failure and verify any self-hosted alternative's dispatch.

All rows remain observation/candidate mappings. Prioritize profile/schema review,
then a portable synthetic-safe pilot and a service/fixture pilot. Qualify native
and protected profiles separately. Remote-state verification and explicit adoption
are prerequisites to operational rollout, not outcomes of this inventory.
