# Implementation Status

**Last updated:** 2026-09-03 — Official-data refresh Task 10 is closed. The 35-case
organizer corpus, final HCX load/soak evidence, independent 0C/0I review, clean-room
image, and covered release manifest are sealed against commit `b0cf204`.

## Frozen baseline

- [x] Official task PDF included
- [x] Eight official workbooks included with ASCII filenames
- [x] Input checksums and audit baseline defined
- [x] Final architecture and domain contracts frozen
- [x] Machine-readable seed policies and JSON schemas included
- [x] TDD phase plans and Codex prompts included

## Phase 1 — Repository and data foundation

Plan: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`

- [x] Task 1: bootstrap settings, version bundle, CLI, and handoff/source checks in tests/CI
- [x] Task 2: implement source manifest and streaming workbook reader with row lineage
- [x] Task 3: normalize domestic bonds and domestic listed products
- [x] Task 4: normalize overseas listed products and public funds with quarantine
- [x] Task 5: build Parquet/DuckDB artifacts, exact links, quality report, and reproducibility check
- [x] Phase 1 gate passed

## Phase 2 — Deterministic query, policy, evidence, and answer engine

Plan: `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`

- [x] Task 1: domain contracts and registry loaders
- [x] Task 2: entity resolution and exact cross-source links
- [x] Task 3: QueryPlan semantic validator and allowlisted SQL compiler
- [x] Task 4: repositories/executor and differential reference
- [x] Task 5: state, metric, comparability, and conditional dual-lens policy
- [x] Task 6: evidence, claim verifier, deterministic Korean renderer, and core service
- [x] Phase 2 gate passed

## Phase 3 — HyperCLOVA X planner and evaluation API

Plan: `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`

- [x] Task 1: HCX client and recorded contract fixtures
- [x] Task 2: structured/strict JSON planner, repair, and rule fallback
- [x] Task 3: API application, exact `/answer`, and safe errors
- [x] Task 4: bounded timeout/retry/concurrency and structured observability
- [x] Task 5: Docker/reproduction and end-to-end API tests
- [x] Phase 3 gate passed

## Phase 4 — Evaluation, hardening, proposal evidence, and release

Plan: `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`

- [x] Task 1: canonical golden set and scoring harness — harness complete; 265 reviewed
  canonical cases committed (24 cases in each of batches 001–011 plus 1 official
  clarification case)
- [x] Task 2: paraphrase, metamorphic, differential, quality, and adversarial suites
- [ ] Task 3: ablation and latency/load/resilience/soak measurement
- [x] Task 4: competition compliance and independent review closure
- [x] Task 5: clean-room reproduction, immutable release manifest, and submission freeze
- [ ] Phase 4 gate passed

## Current next task

**Phase 4 Task 3: reconcile and close the existing ablation outputs and proposal
measurements without changing the sealed runtime candidate.** If that work requires a
behavior/data/prompt/policy/image change, create and verify a new covered candidate.

## Official-data refresh Task 10 closure

- Candidate commits: `af16c1d` (release candidate), `347f53a` (single bounded review
  correction), `4cf620c`/`ecda44e`/`424d06f` (mandatory-gate August fixture alignment),
  and `b0cf204` (direct release-verifier CLI correction). Final covered commit:
  `b0cf204f27d41811df69c52d02c8791afb69cfa0`.
- The approved organizer corpus contains 35 cases: easy 10, medium 10, hard 10, and
  unanswerable 5. Reviewer 곽태성 approved v3 questions/plans and expected
  results/answers on 2026-08-29; the expected packet SHA-256 is
  `859602d78d005b66e4417a8093c4585a8198cde6890f6066c7216100a625f38c`.
- Final live acceptance: 35/35 load requests, zero failures, mean 7,347.939 ms and p95
  11,351.361 ms; 20 soak cycles/80 observations, 517.0632837210433 active seconds,
  zero failures, and zero drift. D-041 explicitly does not claim a 24-hour soak.
- Initial independent review returned Critical 0 / Important 3. The single bounded
  correction closed all three; re-review returned Critical 0 / Important 0 / READY.
- Focused release-CLI RED failed with `ModuleNotFoundError: tools`; GREEN passed, and
  the related release-manifest aggregate passed 8 tests. Earlier focused August profile
  corrections passed their three official integration cases and a 474-test aggregate.
- Final clean-clone gate on `b0cf204`: Ruff format/check PASS (335 files), mypy PASS
  (335 files), pytest `2963 passed, 9 skipped, 5 warnings in 3122.83s`, source audit
  PASS at 53,375 rows, and handoff PASS at 61 files / 9 inputs / 19,074,953 bytes.
- Clean-room reproduction checked out the exact detached commit, passed compliance and
  release contracts (`12 passed`), and built image
  `sha256:5ef62fa1e665ec2626b84d5878eb2c084b5ac74c100da162efa80797a7f8a7be`.
  Artifact logical hash is
  `977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8`;
  `release/manifest.json` verification passed.
- Residual risks: the clean soak is short-duration, sealed holdings coverage is
  unavailable, and hidden organizer latency scoring is unknown. The organizer
  `repeat_stability` 0/0 axis is not used as evidence.
- User-owned ablation JSON changes, both PDFs, and `evaluation/review_batches/*`
  remained untouched and unstaged.

## Official-data refresh Task 9 closure

- Implementation commit: `826aeba` (`feat: require verified HCX answer pipeline`).
  Single bounded review-correction commit: `177c4e1` (`fix: bind verified facts in
  evaluation`).
- Focused TDD closed the ingress +293/+295 deadline, centralized five-string
  publication, mandatory HCX-007 Structured Outputs planner, exact fact-pack wording
  verification, two-call ceilings, one shared client/deadline identity, and safe
  terminal publication. Approved non-content diagnostics isolated provider plan
  failures without printing credentials or provider content; field allowlists,
  native-grain repair guidance, and qualitative-rank guidance were corrected without
  weakening canonical or semantic validation.
- The final authorized live acceptance ran once after the qualitative-rank correction
  and passed: `1 passed, 2 deselected in 10.30s`. The provider plan, repaired plan,
  verbalizer response, and local exact-surface verification completed without fallback.
- The first independent code review returned Critical 0 / Important 2. Focused RED
  reproduced empty END_TO_END observations and a missing right-side comparison entity;
  focused GREEN was 3 passed, the related bundle was 38 passed, and the correction now
  observes verified claims from the FactPack result and binds both evidence-derived
  comparison entity IDs/names fail-closed.
- The corrected Task 9 candidate gate passed: 254 tests, 3 expected non-opted-in live
  skips, and one upstream TestClient deprecation warning; scoped Ruff format/check,
  mypy over 38 files, the 53,375-row source audit, 61-file/9-input handoff verification,
  and diff checks all passed. Bounded re-review returned Critical 0 / Important 0.
- Pre-existing evaluation JSON changes, both untracked PDFs, and user-owned
  `evaluation/review_batches/*` remained untouched and unstaged.

## Official-data refresh Task 8 closure

- Implementation commit: `5dfa42c83a6536f9a0f0d4ecbb5664b2c1571094`
  (`feat: query sealed constituent evidence`). Single correction commit:
  `ce7130b47bf2ed4bd3bd9040c0718ad1f30c0b8d`
  (`fix: preserve constituent evidence limits`).
- Focused TDD added exact constituent resolution, five-type native segmentation and
  parameterized correlated `EXISTS`, overseas-ETF 1Y pruning, canonical holding/coverage
  evidence, bounded v3 serialization, and synthetic cross-product execution. The Task 8
  aggregate passed 244 tests; scoped Ruff, clean non-incremental mypy, source audit at
  53,375 rows, handoff at 61 files / 9 inputs / 19,074,953 bytes, and diff checks passed.
- Initial independent code review returned Critical 0 / Important 3. One bounded
  RED→GREEN correction preserved every exact alias, rejected cross-record provenance
  divergence, and retained non-absence limitations for mixed complete/unavailable
  coverage. Its focused tests passed 6, 2, and 2 cases; the related aggregate passed 16
  tests, and scoped Ruff/mypy/diff checks passed.
- Bounded re-review closed all three implementation findings with Critical 0 / Important
  0. A non-code selector transcription in the ignored correction report was corrected
  mechanically and freshly re-observed as 2 passed in 0.84 seconds; no further review
  loop or production change was made.
- Nonblocking backlog: narrow holding evidence DTO product-type fields to their admitted
  owner-type literals if a future contract revision needs earlier rejection of impossible
  DTOs. User evaluation JSON, PDFs, and review-batch files remained untouched and
  unstaged.

## Official-data refresh Task 7 closure

- Implementation commit: `e5e13997d7b61f26608b744661c66a0cb4329578`
  (`feat: add sealed holdings coverage`).
- No external source met the cutoff, immutable-artifact, exact-crosswalk, and reuse-basis
  admission boundary. The official artifact therefore contains zero fabricated holding
  rows and 31,492 explicit `unavailable` coverage rows.
- The sole official A/B pair used distinct timestamps and produced identical logical
  bytes for all 13 tables, the same independently scanned 217 exact-link pairs, and 434
  direct evidence rows. Overall logical SHA-256 is
  `977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8`.
- Focused holdings/structure checks passed 45 tests. The retained-B official aggregate
  passed 31 tests in 1,586.04 seconds; source audit passed 53,375 rows; handoff verified
  61 required files, 9 inputs, and 19,074,953 bytes. Scoped Ruff, clean non-incremental
  mypy, clean-wheel packaged-resource verification, and staged diff checks passed.
- Independent review of `04731dc..e5e1399` returned Critical 0 / Important 0 / Minor 0.
  No correction round was required. User evaluation JSON, PDFs, and review-batch files
  remained untouched and unstaged.

## Phase 4 Task 1 batch-001 checkpoint

- Reference-generation checkpoint: `6236020` (`test: build approved canonical
  reference batch`). Canonical-promotion checkpoint: `9a8bc77` (`test: promote
  approved canonical batch`).
- Human approval is versioned as reviewer `곽태성`, review date `2026-08-24`, bound to
  reference packet SHA-256
  `4db47c4dfcb0ea63a32c70cd5883e4d6e695f0219bffba9a67c336876d2655d8` and artifact
  manifest logical hash
  `59d8b566b7f3e8986b5c46ae2bebfe2325e7ae12d29ba5d663299fb5ebded236`.
- Focused promotion TDD: 11 expected RED failures before the module existed, then 11
  passed in 0.32 seconds. Related evaluation/authoring aggregate: 62 passed in 0.37
  seconds. Scoped Ruff format/check and clean non-incremental mypy passed.
- Canonical inventory: lookup 4, screen 5, rank 4, compare 3, aggregate 2,
  cross-product 2, clarification 2 (1 official + 1 batch), and quality 3; 25 unique
  IDs total. The existing `OFFICIAL-CLARIFY-001` line was preserved unchanged.
- Independent promotion review of `6236020..9a8bc77`: Critical 0 / Important 0 /
  Minor 0. No correction round was required.
- Repository-wide pytest/Ruff/mypy and the final handoff/source gates were deliberately
  not repeated at this partial authoring checkpoint; they remain reserved for the
  final Task 1 commit candidate.

## Phase 4 Task 1 batch-002 checkpoint

- Deterministic-reference commits: `f4253b9` (`fix: preserve approved reference plan
  fields`) and `9f130da` (`fix: preserve reviewed reference evidence policies`).
  Canonical-promotion checkpoint: `42820f7` (`test: promote approved canonical
  batch-002`).
- Human canonical-reference approval is versioned as reviewer `곽태성`, review date
  `2026-08-25`, bound to reference packet SHA-256
  `fe0b7ec67714ac73d870207f1233465a80f4d128c24778fbf3683bec215020b5`. The immutable
  packet retains its earlier question/draft-plan review date `2026-08-24`.
- Focused promotion TDD covered the independent approval date, repeated same-product
  compatibility partitions in execution traces, and Decimal-filter JSON round trips.
  Final promotion suite: 13 passed. Related evaluation/authoring aggregate: 65 passed.
  Scoped Ruff format/check and clean non-incremental mypy passed.
- Canonical inventory: lookup 8, screen 10, rank 8, compare 6, aggregate 4,
  cross-product 4, clarification 3 (1 official + 2 batches), and quality 6; 49 unique
  IDs total. All 25 prior canonical lines were preserved as exact byte prefixes.
- Independent promotion review of `9f130da..42820f7`: Critical 0 / Important 0 /
  Minor 0. No correction round was required.
- Repository-wide pytest/Ruff/mypy and the final handoff/source gates were deliberately
  not repeated at this partial authoring checkpoint; they remain reserved for the
  final Task 1 commit candidate.

## Phase 4 Task 1 batch-003 checkpoint

- Deterministic quality-lens commits: `51c179f`, `eacf5eb`, and `282dd67`;
  final reference checkpoint: `ec74e16` (`test: refresh batch-003 quality reference`).
  Canonical-approval/promotion checkpoints: `82736bb` and `cfbfd12`
  (`test: promote approved canonical batch-003`).
- Human canonical-reference approval is versioned as reviewer `곽태성`, review date
  `2026-08-25`, bound to reference packet SHA-256
  `580f950b20198f3769e1c6ef709d0501907f26d6cec312fd71025e2877586879` and artifact
  manifest logical hash
  `59d8b566b7f3e8986b5c46ae2bebfe2325e7ae12d29ba5d663299fb5ebded236`.
- Focused RED→GREEN preserved the source-recorded/state-validated count lenses,
  recorded-zero/comparison-valid metric lenses, the 50-product evidence bound, and
  full product evidence identity. The final quality/evidence aggregate passed 54 tests,
  with scoped Ruff format/check clean. The promotion aggregate passed 66 tests;
  scoped Ruff and clean non-incremental mypy passed for the promoter and its test.
- `CQ-003-022` preserves source count 325 and state-validated count 254 in both the
  verified answer and canonical answer semantics. `CQ-003-023` preserves five
  recorded-zero and five positive comparison values with the explicit unverified-zero
  warning. `CQ-003-024` preserves all nine `fund_item` risk-grade groups totaling
  11,138 items.
- Canonical inventory: lookup 12, screen 15, rank 12, compare 9, aggregate 6,
  cross-product 6, clarification 4 (1 official + 3 batches), and quality 9; 73 unique
  IDs total. All 49 prior canonical lines were preserved as exact byte prefixes.
- Independent implementation, reference, promoter, and final promotion reviews each
  closed at Critical 0 / Important 0 / Minor 0. The final promotion review covered
  `82736bb..cfbfd12`.
- Pre-promotion handoff passed with 61 required files, 9 official inputs, and
  41,384,928 source bytes; the official source audit passed at 145,393 rows and snapshot
  `2026-07-11`. Repository-wide pytest/Ruff/mypy and the final full gate were
  deliberately not repeated at this partial checkpoint; they remain reserved for the
  final Task 1 commit candidate.

## Phase 4 Task 1 batch-004 checkpoint

- Candidate generator checkpoint: `7c387f8`. Deterministic reference checkpoint:
  `19ee9e5`. Approval/promotion-boundary checkpoints: `585048b` and `1baabb0`.
  Canonical promotion checkpoint: `5254855` (`test: promote approved canonical
  batch-004`).
- Human canonical-reference approval is versioned as reviewer `곽태성`, review date
  `2026-08-25`, bound to reference packet SHA-256
  `cc4aed0d151555c6f4e6e62bfc1edb9c4913fa03eda81bf9d8d068c9c1546923`, approved
  question/plan packet SHA-256
  `dacf05f0571e963148f345b1d16b771036d3cc05a1c2fb6af75d1644fe6edd5a`, and artifact
  manifest logical hash
  `59d8b566b7f3e8986b5c46ae2bebfe2325e7ae12d29ba5d663299fb5ebded236`.
- Focused RED→GREEN removed bounded product/partition row leakage from aggregate
  answers, added a source-linked 90-day remaining-days comparison, made missing fixed
  FX explicit for cross-currency AUM, and taught the promoter the one approved
  synthetic integer evidence field without adding it to the query registry. The final
  answer/evidence aggregate passed 27 tests; reference authoring passed 18 tests;
  promotion passed 15 tests; and the unit evaluation aggregate passed 94 tests. Scoped
  Ruff and both clean non-incremental and standard mypy passed.
- `CQ-004-014` preserves the evidenced 90-day difference and identifies
  `KR101501DD47` as longer. `CQ-004-017` and `CQ-004-018` expose aggregate results
  without bounded sample rows. `CQ-004-020` and `CQ-004-022` preserve currency
  separation and state that no integrated rank is provided without a fixed FX basis.
- Canonical inventory: lookup 16, screen 20, rank 16, compare 12, aggregate 8,
  cross-product 8, clarification 5 (1 official + 4 batches), and quality 12; 97 unique
  IDs total. All 73 prior canonical lines were preserved as exact byte prefixes.
- Independent implementation review found one Important exact-byte lineage mismatch
  caused by removing the approved packet's terminal blank line. Commit `1baabb0`
  restored the approved bytes; the bounded re-review closed at Critical 0 / Important
  0 / Minor 0. No other correction round was required.
- Repository-wide pytest/Ruff/mypy and the final handoff/source gates were deliberately
  not repeated at this partial checkpoint; they remain reserved for the final Task 1
  commit candidate.

## Phase 4 Task 1 batch-005 checkpoint

- Deterministic-reference checkpoints: `4ed483d` and `f598c45`; canonical promotion
  checkpoint: `cf51139` (`test: promote approved canonical batch-005`).
- Human canonical-reference approval is versioned as reviewer `곽태성`, review date
  `2026-08-26`, bound to reference packet SHA-256
  `dce110eed040f0fda0c26ced2ba5726d8f0a0c3e0584c63ff6ceb99d1eb04e3d`, approved
  question/plan packet SHA-256
  `89951e3a10cb180a9633ca20307e53410019d3b4821a85a2e31d7380bd970998`, and artifact
  manifest logical hash
  `59d8b566b7f3e8986b5c46ae2bebfe2325e7ae12d29ba5d663299fb5ebded236`.
- Initial reference review found one Important nonnumeric DISPLAY evidence gap. One
  focused correction round restored CQ-005-001's `AAA`/`2031-07-21` evidence and
  CQ-005-014's two grounded `AAA` values while preserving all-missing numeric, rank,
  and aggregate behavior. The affected aggregate passed 101 tests; scoped re-review
  closed at Critical 0 / Important 0 / Minor 0.
- Focused promotion RED→GREEN bound the exact approval and four key case boundaries.
  The promoter suite passed 16 tests and the related evaluation/authoring aggregate
  passed 68 tests. Scoped Ruff, clean non-incremental mypy, source audit, handoff, and
  diff checks passed; the generic promoter required no production-code change.
- Canonical inventory: lookup 20, screen 25, rank 20, compare 15, aggregate 10,
  cross-product 10, clarification 6 (1 official + 5 batches), and quality 15; 121
  unique IDs total. All 97 prior canonical lines were preserved as exact byte
  prefixes.
- Independent promotion review of `f598c45..cf51139`: spec and task quality PASS;
  Critical 0 / Important 0 / Minor 0. No correction round was required.
- Repository-wide pytest/Ruff/mypy and the final Task 1 full gate were deliberately
  not repeated at this partial checkpoint. The next bounded checkpoint is batch-006
  candidate generation after explicit HCX external-transfer approval.

## Phase 4 Task 1 batches 006–011 closure

- Final deterministic-reference checkpoint: `2d18c49` (`fix: resolve final reference
  contract violations`). Canonical promotion checkpoint: `ddd5632` (`test: promote
  approved canonical batches 006-011`).
- Human approval was received verbatim as `batch-006~011 expected results/answers
  144개 승인` from reviewer `곽태성` on `2026-08-27`. The six approved reference
  SHA-256 values are: 006 `a03a47de8b9e1430047f512efd265e5be7bc0a76c0496fb3a3ccf2dfcc7cd34f`;
  007 `670972fb2fbf4acc31e4d15b7bbd5ca054aa3b424fcae5f19e60db5893eda7db`;
  008 `3795abceaa3fbbf3e38184b0dff96db8e8cd1ddb0a536ea70cb409b37909b470`;
  009 `20a9afd88af3f5a33473f2d6bcd8f038490f7f32a130b7c2779af8690b25cdf0`;
  010 `6cd8077ae18b4c6e846d95e21b1221126c6f63814bac31ec7f924da83122f108`;
  011 `c56ed018507889902be0b9fb765dd1a0d9523a0abed603a7da98720afe982ef9`.
- Approval-record SHA-256 values are: 006 `906cdb68f54677e6aec84bd9ba45fb16bb7f3f533955489cee49a37cde37a4ff`;
  007 `4814404942402074c85b788e739ebb10e9dad7502dc29ef6ad128ea89f32985d`;
  008 `1a78585f90f175cb055d6649a3e8722b69d098bc8caa6dde258849b05245a97c`;
  009 `2bf737c4bfc125ce8145084102c04d8afe207cb5b6ba024e01d3922533175600`;
  010 `fc1dc3982a4d33b7afbe0caac30f4a29e9e9345d452521abbea289dae2221d13`;
  011 `690c4958206b73ad83fb4ef8a54ab1d25a58c882ca57928fd580d843750c915c`.
- Focused promotion TDD produced the expected RED (`1 failed, 18 passed`) because the
  batch-006 approval record was absent, then GREEN at 19 passed. The related
  evaluation/authoring aggregate passed 71 tests; scoped Ruff and clean
  non-incremental plus standard mypy passed.
- Canonical inventory is 265 unique cases: lookup 44, screen 55, rank 44, compare 33,
  aggregate 22, cross-product 22, clarification 12, and quality 33. All prior 121
  canonical lines remain exact byte prefixes.
- Independent promotion review of `2d18c49..ddd5632`: spec and task quality PASS;
  Critical 0 / Important 0 / Minor 0. No correction round was required.
- The first sandbox full-pytest attempt exposed only environment state: an incomplete
  official-artifact cache and nested `uv` online index refreshes. No repository code
  changed. The prior 3.6 GB partial cache was preserved at
  `/private/tmp/finproof-pre-final-gate-official-published-manifest-643a157719d94f17c5f17578c5f4869ec5061f46381f1f5a70fd9d31a6253f57`.
  A clean official-cache focused rebuild passed 1 test in 8,292.16 seconds; the
  corrected offline contract/API prefix passed 157 tests with 3 expected skips.
- Final unchanged-candidate gate: Ruff format reported 291 files already formatted; Ruff
  check passed; mypy found no issues in 291 source files; pytest passed 2,817 tests
  with 8 expected skips and 5 warnings in 8,003.08 seconds; source audit passed at
  145,393 rows and snapshot `2026-07-11`; handoff passed with 61 required files,
  9 official inputs, and 41,384,928 source bytes. The final pytest used the populated
  `/private/tmp/finproof-uv-cache` with `UV_OFFLINE=1` so nested package builds stayed
  inside the validated cache.
- Phase 4 Task 1 therefore closes at 265 reviewed cases. Exact next task is Phase 4
  Task 2; it is intentionally not started in this checkpoint.

## Phase 4 Task 2 closure

- Implementation checkpoint: `5522406` (`test: harden FinProof language and policy
  behavior`). The one bounded correction is `c252b70` (`fix: verify adversarial
  answer boundaries`); `a0e9b6c` binds the generated robustness report to the
  reviewed correction commit.
- Focused RED→GREEN covered paraphrase invariance and numeric-token preservation,
  seven metamorphic relation kinds, all 17 frozen critical regressions, 11
  adversarial scenarios, targetless global counts, and explicit currency/product
  partition wording. The direct REDs were the incompatible-partition count error,
  a `global` rather than `per_product_type` fallback plan, and acceptance of unsafe
  untraced answer text. Their focused selectors passed after the minimum changes;
  the related evaluation/differential/property/planner/query aggregate passed 93
  tests with one known warning.
- `finproof evaluate --suite robustness` ran in deterministic fallback-only mode
  against the validated official artifact. The committed report records 42 evaluated
  quality/paraphrase cases, 11/11 adversarial cases, and all seven metamorphic relation
  definitions. Low canonical fallback scores are retained as Task 3/4 evidence and
  backlog rather than hidden or promoted to a Task 2 threshold.
- The first full gate exposed one test-fixture collision with the newly planned
  `artifacts/evaluation/robustness.json`; isolating that fixture in `tmp_path` passed
  its focused selector. The final corrected-candidate gate reported Ruff format/check
  clean; clean non-incremental and standard mypy clean across 298 source files; pytest
  2,875 passed, 8 expected skips, and 5 known warnings in 10,371.73 seconds; source
  audit 145,393 rows at snapshot `2026-07-11`; and handoff 61 required files, 9
  official inputs, and 41,384,928 source bytes.
- The first independent review returned Critical 0 / Important 3. Root adjudication
  rejected one runner expansion outside the frozen Task 2 contract and corrected the
  two direct issues: adversarial trace/claim validation and report commit binding.
  The bounded re-review closed at Critical 0 / Important 0. No official question or
  blocker remains; expected skips/warnings and low fallback-only scores remain visible.
- Exact next task is Phase 4 Task 3: ablation, latency, load, resilience, and soak
  measurement. It is intentionally not started in this checkpoint.

## Phase 1 Task 5 design and plan record

The artifact-build contract was implemented from
`docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md`. D-022 and
D-023 freeze logical-versus-physical identity, exact artifact inventory, bounded
external ordering, guarded publication, wide Silver scope, and the raw exact-link rule.
The authoritative detailed plan is
`docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md`; the legacy Task 5
body and dedicated plan now record all eight checkpoints complete.

Observed design-gate evidence on 2026-08-14:

- independent final review: Critical 0 / Important 0 / Minor 0;
- `python3 tools/verify_handoff.py`: 61 required files, 9 official inputs,
  41,384,928 bytes;
- `python3 tools/audit_source_data.py --check`: 145,393 rows, snapshot 2026-07-11;
- `uv run pytest tests/contract -q`: 39 passed in 45.28 seconds;
- `uv run pre-commit run --all-files`: Ruff check and Ruff format passed;
- `git diff --check`: passed.

The detailed plan contains eight checkpoints and passed independent final review with
Critical 0 / Important 0 / Minor 0 after its executable resource-loading, stale
editable-copy, first-publication rollback, bounded-memory, packaging, and strict TDD
boundaries were corrected. The narrow resource design correction was independently
approved with Critical 0 / Important 0 / Minor 0 and committed as `0dec136`.

Checkpoint 1 implementation and review evidence on 2026-08-15:

- reviewed commit series: `2546833` (`feat: add artifact build foundations`),
  `fa7b98e` (`fix: close Task 5 checkpoint 1 review gaps`), and `756a791`
  (`fix: verify missing-resource ancestor identity`);
- final independent review at `756a791`: Critical 0 / Important 0 / Minor 0;
- exact CP1 focused suite: 277 passed; unchanged Task 1–4 regression: 533 passed;
  reviewer-selected focused regression: 12 passed;
- full implementation suite: 920 passed in 574.36 seconds;
- Ruff format/check and mypy passed over 91 source files;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required
  files, 9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- final worktree was clean, official source files were read-only, and the official
  expected-contract source remained absent.

Checkpoint 2 implementation and review evidence on 2026-08-15:

- reviewed commit series: `0db3e79` (`feat: add strict artifact manifest and logical
  hashing`), `ac5d4ee` (`fix: close Task 5 checkpoint 2 review gaps`), and `75a2bfc`
  (`fix: snapshot artifact rows before hashing`);
- final independent review at `75a2bfc`: Critical 0 / Important 0 / Minor 0;
- hashing regression: 46 passed; exact CP2 focused suite: 341 passed; CP1+CP2
  aggregate: 576 passed; unchanged Task 1–4 regression: 533 passed;
- full implementation suite: 1,248 passed and 1 explicit AF_UNIX-unavailable skip in
  578.71 seconds;
- Ruff format/check and mypy passed over 98 source files;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required files,
  9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- wheel and resource checks passed with byte-identical manifest/quality schemas and no
  expected-contract resource or candidate tooling; both expected-contract paths and
  `artifacts/` were absent, official source files were read-only, and the final
  worktree was clean.

Checkpoint 3 implementation and review evidence on 2026-08-15:

- complete commit lineage from approved redo base `d983f1a`: `ec2ad7e`, `bd055cb`,
  and `4d5bc9b` (approved plan/evidence corrections); `065e9fc` (`feat: freeze
  artifact table and Parquet contracts`); `ac7d8eb` and `07aeca2` (first review plan/fix);
  `d61cca7` and `aa3f410` (third correction plan/fix); `97473d2` and `94ee69e`
  (fourth correction plan/fix); and `45c330f` and `a80ef32` (fifth correction
  plan/fix);
- final independent review at `a80ef32`: Critical 0 / Important 0 / Minor 0;
- final correction aggregate: 617 passed and 1 explicit AF_UNIX-unavailable skip;
  CP2+CP3 focused gate: 802 passed, 1 skipped, and 4 warnings; unchanged Task 1–4
  regression: 533 passed;
- full repository suite: 1,837 passed with 4 warnings in 322.38 seconds;
- Ruff format/check and mypy passed over 107 source files;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required files,
  9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- pre-commit passed; both expected-contract paths and runtime `artifacts/` remained
  absent, official source files were read-only, and the reviewed worktree was clean.

Checkpoint 4 implementation and review evidence on 2026-08-15:

- reviewed implementation/correction lineage: `e91ed04` (`feat: stream complete
  Bronze artifacts`), `278d20ce` (`fix: close Task 5 checkpoint 4 review gaps`), and
  `4bdebfbf` (`fix: close final Task 5 checkpoint 4 review gap`);
- final narrow independent verification at `4bdebfbf`: Critical 0 / Important 0,
  with no backlog item;
- final new lifecycle selector matrix: 4 passed; related Parquet/staging/Bronze
  regression: 140 passed; final CP4 focused aggregate: 761 passed and 1 explicit
  AF_UNIX-unavailable capability skip; unchanged Task 1–4 regression at the
  implementation checkpoint: 533 passed;
- final network-enabled full repository suite: 2,015 passed with 4 deliberate
  adversarial Pydantic serialization warnings in 324.75 seconds;
- Ruff format/check and both fresh no-incremental and clean-cache standard mypy passed
  over 116 source files; pre-commit passed;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required files,
  9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- both expected-contract paths and runtime `artifacts/` remained absent, official
  source files were read-only, and the final worktree was clean.

Checkpoint 5 implementation and review evidence on 2026-08-15:

- reviewed implementation/correction lineage: `9c43201` (`feat: stream Silver and
  persisted quality artifacts`), `8c8c6c` (`fix: close Task 5 checkpoint 5 review
  gaps`), and `6c29bcbc` (`fix: preserve exact Silver result provenance`);
- final narrow independent verification at `6c29bcbc`: Critical 0 / Important 0;
- the ignored repository TDD report records all 29 mandatory RED/GREEN selectors and
  seven explicitly derived first-GREEN acceptances; the final carrier correction
  selector passed 2 tests and the final CP5 aggregate passed 276 tests in 10.52
  seconds;
- unchanged Task 1–4 regression: 553 passed in 1.33 seconds; final network-enabled
  full repository suite: 2,077 passed with 4 deliberate adversarial Pydantic
  serialization warnings in 374.56 seconds;
- Ruff format/check and mypy passed over 124 source files; pre-commit passed;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required files,
  9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- both expected-contract paths and runtime `artifacts/` remained absent, official
  source files were read-only, and the final worktree was clean.

Checkpoint 6 implementation and review evidence on 2026-08-20:

- reviewed implementation/correction lineage: `56aa2c2` (`feat: add exact
  cross-source link artifacts`), `1895942` (`fix: close CP6 exact-link review
  findings`), and `28dd4e5` (`fix: verify reopened Gold evidence rows`), with
  compatibility commit `18673c1` and approved plan corrections through `14f5f9a`;
- the ignored execution report records 37 mandatory RED/GREEN entries and two derived
  acceptances; official acceptance verified 47 links, zero ETN links, 371 evidence
  rows, 1,222 canonical TSV bytes, raw/trimmed/emitted pair equality, and the frozen
  SHA;
- final reopened-Gold focused verification: 6 passed in 0.79 seconds; final CP6
  aggregate: 212 passed in 7.00 seconds; unchanged Task 1–4 regression: 553 passed;
- final network-enabled repository suite: 2,181 passed with four known adversarial
  serialization warnings in 1,639.23 seconds; Ruff format/check and mypy passed over
  130 files; pre-commit passed;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required files,
  9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- the first review returned Critical 0 / Important 6; its scoped re-review left one
  original Important, and final single-finding verification at `28dd4e5` returned
  Critical 0 / Important 0;
- both expected-contract paths and runtime `artifacts/` remained absent, official
  source files were read-only, and the final worktree was clean.

Checkpoint 7 implementation and review evidence on 2026-08-20:

- approved plan correction `79c5359`; implementation lineage `e1ca554` (`feat:
  verify self-contained artifact databases`), `553573f` (`feat: guard artifact
  publication and recovery`), and `f2a8726` (`feat: add verified artifact build
  command`); review corrections `c48588d` and `f793611`;
- final CP7A aggregate: 50 passed; CP7B aggregate: 43 passed; CP7C implementation
  aggregate: 86 passed; final single-item focused verification: 1 passed in 0.51
  seconds;
- final network-enabled repository suite: 2,308 passed with four known adversarial
  serialization warnings in 1,713.37 seconds; Ruff format/check and fresh plus
  standard mypy passed over 145 files; pre-commit passed;
- source audit: 145,393 rows at snapshot `2026-07-11`; handoff: 61 required files,
  9 official inputs, and 41,384,928 source bytes; schema catalog: 207 columns;
- the independent whole-CP7 review returned Critical 0 / Important 4; its scoped
  re-review left one original telemetry Important, and final single-item verification
  at `f793611` returned Critical 0 / Important 0;
- the ignored execution report SHA-256 is
  `d1198fc3cbd8a0cb45fb41f7f75a1068db5129ddb7f4b06c8921d5f045a13b89`;
- both expected-contract paths and runtime `artifacts/` remained absent, official
  source files were read-only, and the final worktree was clean.

Checkpoint 8 implementation and review evidence on 2026-08-21:

- approved plan/base corrections include `69566b1`; implementation lineage is
  `7ac04d9` (`feat: activate reviewed Phase 1 artifact contract`), `33f5579`
  (`fix: close Task 5 final review gaps`), and `cf32d55` (`fix: bind publication
  cleanup identity`), with stale CP2 compatibility isolated in `22f6242`;
- the fourteen mandatory lifecycle/public-surface observations were closed serially:
  provenance-bound private carrier; candidate discard branch; public manifest verify;
  substituted core rejection; exact receiver admission; copied/foreign/prefilled/
  throwing receiver rejection; indivisible custody transfer/source invalidation;
  expected-mismatch pre-rename cleanup; descriptor publication/precommit rollback;
  exact-once custody cleanup; official expected-accepted publication; reopened target
  recognition; typed postcommit CLI failure; and the closed public surface. The first
  thirteen missing behaviors produced focused REDs before GREEN; the already-preserved
  closed-surface selector was honestly first-run GREEN. The compact CLI success
  selector was the planned derived first-GREEN acceptance; no RED was manufactured;
- candidate A (`2026-08-14T00:00:00.000001Z`) and B
  (`2026-08-14T00:00:01.999999Z`) each completed in about 47/48 minutes and produced
  byte-identical canonical logical bytes, SHA-256
  `7281eae4f076985f00bea997469ed26b655229cfbfeecbb55de2006f081c155a`;
  independent candidate review returned Critical 0 / Important 0 / Minor 0;
- exact logical table counts/hashes are: `bronze_source_column` 207 /
  `d3df3c12fe0683d7e3615ff69ebe8be741b9d53115c992d305f20a921655b174`;
  `bronze_source_row` 145,393 /
  `cbb96cfcc7946fccf7b93b287afa6f5c0c1b74bafe4df000ae1453fe2e886949`;
  `bronze_source_cell` 6,401,851 /
  `91941c43ea590c4779968b5c9d0212b8c01a281a7e0f4ad112a8158d5f0760e5`;
  `silver_bond_instrument` 42,394 /
  `27af21fef2d39fdcc1373c7eb994b51e1aeca3b6bf664e2922bfd5863f0e774b`;
  `silver_domestic_listed_product` 1,733 /
  `ae453024c71c8b9535f4f41683b632778a1b8602296adae3d622d72ecca99e2c`;
  `silver_overseas_listed_product` 5,646 /
  `fc9114fbbca0ab5fa8217d77ad5c01f4cc780abdfb094b22c0b0dcb9abf24bc7`;
  `silver_fund_item` 11,138 /
  `36a643c6108aa8eda1550747dc7ce415d94631e837aef9f8beb9b5765dff6e37`;
  `silver_fund_item_attribute` 95,618 /
  `0f504ffd89067efcf3efc1f0df8d074aa8f345bead5eaeeb7a5594ddf3540afb`;
  `silver_quality_issue` 6,032 /
  `a65421c79c2c4528eb2dc637d19abf6825fb9988ef1f9ed8e3d4510d81548792`;
  `gold_exact_cross_source_link` 47 /
  `cbfde1f767a38352db2932868f801d15cbc2f0baff41a7151d25aa1c1be77aeb`;
  and `gold_exact_cross_source_link_evidence` 371 /
  `833ef0ff458cda3484a08288dcb73173fb2c9a8b8be708e368ee6fba8473fad1`;
- report semantic hashes are source audit
  `fea118bb59edc41bd3f51ab983f1837476809d2ff322de0de64d39f19788ccfe`
  and quality summary
  `3320305708ef24b868b60020ace9c37cf3d048a2fefa7a69a538145b778de975`;
  exact-pair SHA-256 is
  `8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962`,
  and overall logical SHA-256 is
  `a07abff8a0e4dd7e51288de24bc80a16fcf5ce3f9f3756e4ea1f62352faa4103`;
- candidate A's reviewed physical path/size/hash inventory was:
  `finproof.duckdb` 3,813,421,056 /
  `fc7c2abbcbfad6becd28e7fa8d3a9507c70bac50a546ddcab49a644b01ab9fa5`;
  Bronze cell 19,873,708 /
  `cb4576d3d60c99c8cb6023359d6ca843c235ebcf9bfbf14dde5a9520a9893ddf`,
  column 8,701 /
  `9c213dec0057c4168f0e3ed0054c59bf59ba7176bf97b97318984b3ee2ebb551`,
  row 20,759,935 /
  `310ce05d5f16de4e9cebbb8364185fc9599d060a260d7a850fc17c0b44936168`;
  Gold link 6,909 /
  `369061f3f75c919c77dc8f31c9b970a9be0bd2ff156775580942a63067b8595f`,
  evidence 9,933 /
  `d8f08c713b52c68d5b0bdb9e98d1d2d5cdc63f153511f966457f27c3029a6021`;
  Silver bond 9,400,752 /
  `91c33a11b6fcd9314a3b1cc5e610b9698d7745722e84293ba5e6ef7a47c5819c`,
  domestic 849,333 /
  `577de2d13ce7c707bb92998c9bb5842981b05ff876685737efb6ce83a159407a`,
  fund item 35,145,813 /
  `6311501fdb3020e88ccf41bfd7f6bf27b1bf139d904090f8deb7711902c0366e`,
  fund attribute 2,456,112 /
  `ecfe1bb4fb6812d21fedde05ec8a658bc3fd6d0f32ffaf5d51340515da961949`,
  overseas 4,853,077 /
  `8edbbb8ca35e9556df07a6da1197346c40deb423edac4f7874b08ced89337144`,
  quality 963,492 /
  `115941e14a714134e690f3e0a7e40f417fed3d4e82d6dd3d0af47a97afb2011a`;
  quality report 2,572 /
  `4c7b2dc240a98d3d5483603c69941fc71ce9d02501a202b8829417e34255ea10`;
  source report 2,216 /
  `daa07137da99d89efa93198095bfe7e26b81031b6a7ff9120c48a33da74c797c`.
  Timestamp-bearing DuckDB/Bronze-row/quality bytes
  intentionally differ in candidate B while timestamp-free logical identity remains
  exact;
- official expected-accepted publication completed in 9,080.34 seconds; its child
  build took 5,730.84 seconds and observed Darwin-normalized peak RSS
  10,531,536,896 bytes. The reused official source/performance aggregate passed in
  3,430.87 seconds with writer/verifier maxima 65,536, fund-group maximum 16, Bronze
  reconstruction maximum 73, linked parses 47 / 47, live keys 47 / 371, and both
  marker-owned workspaces at mode 0700, one thread, `1GiB`, cleanup complete;
- whole-branch review first returned Critical 0 / Important 2. The reachability/
  recovery correction at `33f5579` passed its full gate, then a narrow re-review found
  the shared exact-owned deletion TOCTOU remainder. Clean/recovery substitution REDs
  were closed at `cf32d55`; the final constrained review reran them (`2 passed in
  16.85s`) and returned Critical 0 / Important 0;
- final affected aggregate: 179 passed in 49.60 seconds. Final repository gate: Ruff
  format/check and mypy over 149 files passed; pytest `2339 passed, 4 warnings in
  5012.89s`; source audit 145,393 at `2026-07-11`; handoff 61 required files / 9
  official inputs / 41,384,928 bytes; catalog 207; pre-commit, wheel, diff/ignore,
  source-read-only, and clean-tree checks passed;
- ignored execution ledger SHA-256 is
  `65421ae097dd873dc3ba9bc2355741268a628fc93faa797e1b05e155edae4059`.

Residual evidence note: the four known adversarial Pydantic serializer warnings remain
expected test output, and absolute RSS is platform-observational rather than a frozen
portable cap. No unresolved Critical/Important finding or official-source question
blocks Phase 1 closure. Exact next task is Phase 2 Task 1; no Phase 2 implementation
was started here.

## Handoff validation record — not production implementation

Observed on 2026-08-07:

- `python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs.
- `python tools/audit_source_data.py --check` — PASS: 145,393 source rows, snapshot 2026-07-11.
- `python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `pytest -q` — PASS: 7 handoff contract tests.
- `python -m compileall -q src tools tests` — PASS.
- `python -m tools.verify_handoff` — PASS; handoff tools are importable as modules as well as executable scripts.
- JSON/YAML parse check — PASS: 8 schemas and 8 policy/config files.
- The original handoff did not include `uv.lock`. The first network-enabled macOS bootstrap generated it with uv on 2026-08-13; future installation must use `uv sync --frozen --all-groups`.
- Dependency metadata was cross-checked before handoff; notably the Polars lower bound was corrected to the published `1.43.0` release. Ruff and mypy were unavailable in the artifact environment; both were installed and their existing findings were cleared during the 2026-08-13 macOS bootstrap below.

See `docs/13_HANDOFF_VALIDATION_REPORT.md`. These checks validate the handoff package, not the production system.

## Work log

### 2026-08-13 — Windows-to-macOS handoff audit and workstation bootstrap

This was workstation and handoff work, not Phase 1 product implementation.

Changes:

- Installed native Apple Silicon `uv 0.12.3` and Python `3.12.13` with Homebrew.
- Generated `.python-version`, `.venv`, and resolver-produced `uv.lock` for all dependency groups.
- Added `.gitignore`, initialized `main`, and committed the verified handoff baseline.
- Removed four `.DS_Store` files, eleven CPython 3.14 bytecode files (including transferred Windows absolute paths), and empty pytest transfer directories. None were committed.
- Made the local `source_material/` tree read-only. Git does not preserve `0444`, so checksum gates and future read-only CI/container mounts remain required.
- Normalized the other transferred project files/directories from world-writable `0666`/`0777` to `0644`/`0755`; retained Apple quarantine/provenance extended attributes as non-blocking provenance metadata.
- Formatted and typed the existing handoff tools without changing official data, config, schemas, or product behavior; added `types-jsonschema` as a dev-only typing dependency.
- Corrected `START_HERE.md`, `HANDOFF_PACKAGE_MANIFEST.md`, and `Makefile` to use the checked-in lock with frozen sync, run source checks before dependency installation, and stop claiming that absent pre-commit/CI/environment templates exist.
- Added a regression contract for those bootstrap instructions and registered every audited contract conflict in `docs/10_DECISION_LOG.md` with its affected task boundary.
- Added the exhaustive audit report at `docs/implementation/2026-08-13_MACOS_HANDOFF_AUDIT.md`.

RED evidence observed before the quality-only repair:

- `uv run ruff format --check .` — FAIL: 6 files required formatting.
- `uv run ruff check .` — FAIL: 41 findings.
- `uv run mypy src tests tools` — FAIL: 14 findings.
- These findings were present in the transferred baseline when first checked in the resolved macOS environment; the original handoff report states Ruff and mypy were unavailable in its creation environment.

GREEN evidence observed after the repair:

- `uv run ruff format --check .` — PASS: 10 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 10 source files.
- `uv run pytest -q` — PASS: 7 tests.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot 2026-07-11.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs, 41,384,928 bytes; PyYAML parser active.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.

RED/GREEN evidence for the bootstrap-instruction regression:

- RED: the focused test first failed because `Makefile` used unfrozen sync; after that repair, its ordering assertion failed because the manifest synchronized dependencies before the pre-install source checks.
- An incidental first rerun was blocked before test collection when uv needed the isolated `hatchling` build dependency and the sandbox denied DNS. `uv sync --frozen --all-groups` was rerun with approved network access; the actual assertion RED failures above were then observed.
- GREEN: the focused test passed after all three active bootstrap entry points were corrected.

Final current-tree evidence after independent review:

- `uv sync --frozen --all-groups` — PASS: checked 67 packages.
- `uv run ruff format --check .` — PASS: 10 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 10 source files.
- `uv run pytest -q` — PASS: 8 tests.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot 2026-07-11.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs, 41,384,928 bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- permission gate — PASS: zero world-writable project paths outside local Git/venv state; source files locally read-only.
- `git diff --check` — PASS.

Intermediate commits created before this final audit record:

- `68bdd2e1686737eee652c91e8d3751a92e3555a8` — verified handoff and macOS bootstrap baseline.
- `97a79c3483086e0e25c073e1537181a4d8ea6f6d` — bootstrap Ruff/mypy repair.

Risks and unresolved decisions:

- The original handoff claimed CI/environment templates were included, but they were absent at migration time. Phase 1 Task 1 added `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, and `.env.example` as recorded below.
- The full audit found unresolved aggregate-plan, lineage, state, cache-key, partitioned top-k, and release-manifest contracts. They are registered in `docs/10_DECISION_LOG.md` and must be reconciled before each listed affected task, not before unrelated Phase 1 Task 1 work.
- All 13 golden seeds are AI-handoff seeds rather than human-reviewed evaluation cases.
- Docker is not installed; it is not needed for Phase 1 and becomes necessary for the Phase 3 container gate.
- The first Git commit was created after cleanup/bootstrap, so Git cannot independently reconstruct the pre-clean transfer inventory or prove chain of custody before that root commit. Current manifest/audit checks establish internal consistency only.

Exact next task:

**Phase 1, Task 1**, under strict TDD. First amend its planned file scope to include CI, `.pre-commit-config.yaml`, and `.env.example`; then add the failing settings/version/CLI/bootstrap tests specified by the plan. The other logged conflicts block only their listed affected tasks.

### 2026-08-13 — Phase 1 Task 1: typed core, CLI, and CI bootstrap

Scope implemented:

- Added environment-backed typed `Settings` with evaluation defaults, an evaluation-mode invariant that fixes the official snapshot at `2026-07-11`, typed paths, and bounded top-k validation.
- Added transport-independent `FinProofError`/`SourceContractError` and immutable `VersionBundle` defaults matching checked-in version `1.0.0` policies.
- Added `finproof` commands `show-versions`, `verify-handoff`, and `audit-source`. Source commands call the existing Python tools in-process only when the working directory is the checkout containing the installed editable FinProof package.
- Added `.env.example` with safe non-secret values, Ruff pre-commit hooks pinned to `v0.15.22`, and a read-only-permission GitHub Actions workflow on Python 3.12 with uv `0.12.3` frozen installation. Every third-party CI action is pinned to a full commit SHA.
- Installed the local pre-commit hook and amended the original Phase 1 Task 1 file/check scope to cover the previously missing automation files.

RED evidence observed before implementation:

- Settings test collection failed with `ModuleNotFoundError: No module named 'finproof.core'`.
- Version test collection failed with `ModuleNotFoundError: No module named 'finproof.core.versions'`.
- CLI test collection failed with `ModuleNotFoundError: No module named 'finproof.cli'`.
- The installed `finproof` entry point then failed all three commands because pytest exposed top-level `tools` while the real console did not. A parameterized console regression reproduced that boundary before repository-tool loading was corrected.
- Automation contract tests failed three times with missing `.env.example`, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml`.
- Independent review then produced three focused RED checks against the first implementation: evaluation mode accepted `2026-07-10`; a lookalike working directory executed its own `tools.verify_handoff`; and the CI action-reference assertion rejected the mutable `actions/checkout@v6` and `actions/setup-python@v6` tags. The minimal hardening change made the three focused checks and the 14-test related suite pass.

Incidental verification findings and resolution:

- Pydantic's runtime-only `_env_file` argument is absent from its static synthesized signature. Tests now isolate `.env` through `tmp_path`/working directory and use the public constructor.
- Strict mypy identified one unnecessary suppression comment, which was removed.
- The first pre-commit invocation could not write the sandboxed home cache and could not fetch GitHub over sandbox DNS. A task-specific `/private/tmp` cache and approved one-time network fetch were used; the pinned hook subsequently ran offline.
- The first full format gate reported one automation test file; it was mechanically formatted and the complete gate was rerun.

Final observed verification before this status update:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked.
- `uv run ruff format --check .` — PASS: 22 files already formatted.
- `uv run ruff check .` — PASS.
- `uv run mypy src tests tools` — PASS: no issues in 22 source files.
- `uv run pytest -q` — PASS: 24 tests.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs, 41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- All three `uv run finproof ...` commands — PASS with deterministic versions and the same handoff/source results.
- `uv run pre-commit run --all-files` — PASS: Ruff check and format hooks.
- `git diff --check` — PASS.

Implementation checkpoints:

- `7d2888f` — typed settings and errors.
- `3c339f8` — immutable version bundle.
- `20ea7c9` — deterministic CLI and installed-console regression.
- `d443feb` — environment, pre-commit, CI, and automation contracts.
- `a3af00b` — mechanical formatting required by the final hook gate.
- `1e12985` — Task 1 verification evidence, status, and exact next task.
- `a23fab3` — independent-review hardening for snapshot, repository-command, and CI supply-chain boundaries.

Remaining risks:

- The GitHub Actions YAML and every command it contains were validated locally, but no remote GitHub Actions run exists until this branch is pushed to a GitHub repository.
- `verify-handoff` and `audit-source` are repository bootstrap commands; when invoked anywhere other than the checkout that supplies the installed editable package they fail closed with a concise `FinProofError`.
- Phase 1 Task 2 must resolve A-002 before freezing `SourceRow`/evidence lineage fields. Other A-series decisions retain the task boundaries recorded in `docs/10_DECISION_LOG.md`.

Exact next task:

**Phase 1, Task 2.** First resolve A-002 so source checksum, dataset snapshot, and applicable-date lineage are present in the planned contracts. Then begin with the failing official-manifest checksum test; do not start normalization or artifact building in the same uncontrolled change.

### 2026-08-14 — Phase 1 Task 2: verified source manifest and streaming XLSX lineage

This is the first Phase 1 product-data implementation checkpoint. The prior Task 1
checkpoint made the workstation/repository automation ready; it did not implement
source ingestion. The Phase 1 gate remains open because normalization, quarantine,
quality reports, and reproducible Parquet/DuckDB artifacts are later tasks.

Scope implemented:

- Added safe structured source errors and immutable `SourceCell`/`SourceRow` raw-lineage
  contracts with checksum, snapshot, manifest-relative file, table, sheet, exact Excel
  row/column, raw payload/value, and explicit optional cell applicable date.
- Added strict immutable manifest/schema-catalog metadata models. Unknown fields,
  coercible numeric metadata, table/catalog drift, and injected catalog content fail
  closed.
- Added all-or-nothing file verification for containment, type/symlink, size, and
  chunked SHA-256 checks. Only a fully verified set exposes `VerifiedSourceFile` values.
- Added a bounded-memory hardened XLSX reader whose only public input is
  `VerifiedSourceFile`. It validates ZIP/OPC/XML structure, exact sheet/header/cell
  coordinates, formulas, row widths/order/counts, and emits exact unnormalised strings.
- Added official-source acceptance coverage that fully traverses all 145,393 rows,
  checks every row/cell lineage coordinate and state, and compares selected rows with
  the independent bootstrap reader.
- No normalization, quarantine, artifact building, query/API behavior, official input,
  or expected source-audit value changed.

Authoritative decisions and remaining boundary:

- A-002 is implemented under D-017: production ingestion accepts only a verified
  descriptor and preserves the complete frozen raw-lineage shape.
- D-018 assigns JSON structure/metadata validation to `SourceFileManifest.load` and
  manifest-relative containment/`PATH_ESCAPE` validation to `verify(base_dir)`.
- D-019 permits the official OPC package-absolute `/xl/...` worksheet target only after
  strict canonicalization to an internal ZIP member; traversal, external/URI targets,
  external relationship mode, and host-filesystem interpretation remain prohibited.
- A-011 remains open only for later quality/evidence schemas and metric entries. It no
  longer blocks the implemented Task 2 raw-lineage boundary.

Focused RED/GREEN evidence:

| Checkpoint | Observed RED before behavior | Observed GREEN |
|---|---|---|
| source errors / lineage (`c711623`) | error imports failed because `SourceErrorCode` was absent; lineage collection failed because `finproof.domain` was absent; the public error boundary then failed because `Path` context was accepted | error tests `3 passed`; initial combined lineage/error tests `12 passed`; hardened combined suite `13 passed` |
| strict metadata (`946f562`, `0aa3907`) | collection failed because `finproof.data` was absent; review regressions then showed injected `schema_catalog` accepted, two unsafe path forms accepted, and a numeric string coerced | initial metadata suite `14 passed`; hardened suite `18 passed` |
| verified descriptors (`5541d55`, `3941f3e`) | `10 failed, 16 passed`: nine cases lacked `verify`, and the boundary test exposed load-time rather than verify-time path handling; three injected OS-access cases then escaped as raw `PermissionError` | verification suite `26 passed`; fail-closed OS-error suite brought the file to `30 passed` |
| streaming reader (`ecbc6e2`) | collection failed because `finproof.data.xlsx_stream` was absent; first implementation was `19 passed, 1 failed` because an invalid shared-string index escaped as `IndexError`; after the authoritative OPC decision, three tests exposed rejection of the required package-absolute target and acceptance of external variants | initial reader suite `20 passed`; OPC-safe reader suite `23 passed` |
| reader hardening (`6ac3c5b`) | Excel bounds/row ordering: `4 failed, 1 passed`; negative shared-string index: `1 failed`; relationship type/base resolution: `2 failed`; duplicate/encrypted/unsupported ZIP members: `3 failed` | corresponding focused suites `5 passed`, `2 passed`, `3 passed`, and `3 passed`; complete reader suite `34 passed` |
| official acceptance (`05949b4`, `f4d49cc`) | no synthetic production RED was permitted for already-implemented acceptance behavior; one authoring-only pytest mark tuple error was corrected before the first executable acceptance run | official lineage/parity acceptance `3 passed`; exhaustive cell-coordinate/state amendment also passed immediately with no production change |

Implementation checkpoints:

- `c711623` — immutable source lineage contracts.
- `946f562` and `0aa3907` — strict official metadata plus validation hardening.
- `5541d55` and `3941f3e` — all-or-nothing verified descriptors plus fail-closed
  source-access handling.
- `ecbc6e2` and `6ac3c5b` — verified XLSX streaming plus structural hardening.
- `05949b4` and `f4d49cc` — official full-lineage/parity acceptance plus exhaustive
  cell-coordinate/state assertions.

Observed pre-review Task 6 gate before the first documentation checkpoint:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 7 ms. The first
  sandboxed attempt could not initialize `~/.cache/uv`; the exact command was rerun with
  approved access to the configured uv cache.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 104 tests in 100.07 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  64 deselected in 72.68 s; the official test fully traversed 145,393 production rows.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Independent review and fix round:

- Review found four Important gaps and no Critical finding: metadata versions were
  unconstrained; unresolved entities could silently become empty inline/shared-string
  values; rows outside the worksheet's single direct `sheetData` were accepted; and an
  intermediate manifest-path symlink was accepted.
- RED: unsupported manifest/catalog versions plus an intermediate symlink produced
  `3 failed, 30 deselected`; each missing guard accepted the invalid fixture.
- RED: inline entity plus missing/duplicate `sheetData` initially produced `3 failed,
  34 deselected`. The sheetData fixture was corrected and verified against the guardless
  implementation as `2 failed, 35 deselected`; nested `sheetData` separately failed once.
- RED: entity-bearing shared strings separately failed once because the reader returned
  an empty value rather than raising.
- GREEN: exact version literals, component-wise symlink rejection, inline/shared entity
  rejection, and direct/single `sheetData` validation produced `7 passed, 64 deselected`;
  the expanded entity/sheetData set produced `5 passed, 34 deselected`; and the related
  manifest/XLSX suite produced `72 passed` after formatting.
- Independent re-review approved the fix diff with no remaining Critical or Important
  finding. No Phase 1 Task 3 behavior was introduced.
- `27caba1` — close source-ingestion independent-review gaps.

Observed post-review implementation gate before this final documentation update:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 1 ms.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 112 tests in 103.09 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  72 deselected in 77.42 s with full 145,393-row production traversal.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Observed complete gate after the final documentation update:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 1 ms.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 112 tests in 103.24 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  72 deselected in 77.46 s with full 145,393-row production traversal.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Subsequent final-review correction wave:

- A later complete-branch review found four additional Important trusted-boundary gaps:
  mutable validated catalog mappings; DTD/entity use in XML attributes plus permissive
  metadata roots/descendants; raw `UnicodeDecodeError`/lexical path `ValueError`
  escapes; and post-percent-decoding OPC target bypasses.
- D-020 freezes the correction without changing D-018/D-019: catalog mappings are
  deeply immutable and predictably serializable; every parsed XML part rejects
  declarations before values/attributes and requires exact root/direct structure; raw
  and decoded targets must pass control/backslash/NUL/traversal/URI and canonical
  round-trip checks before ZIP access.
- RED for catalog immutability: `3 failed, 33 deselected`; table replacement, nested
  sample-map mutation, and serialized/reloaded catalog mutation all succeeded before
  the correction. GREEN: the complete manifest suite was `36 passed` at that
  checkpoint, with focused Ruff/mypy clean.
- RED for malformed metadata/path typing: `3 failed, 36 deselected`; invalid UTF-8
  escaped twice as `UnicodeDecodeError`, and a NUL-bearing manifest path escaped as
  `ValueError` with a local path. GREEN: manifest suite `39 passed`, with focused
  Ruff/mypy clean.
- RED for XML declarations/metadata structure: `15 failed, 2 passed, 39 deselected`;
  all four XML parts accepted unused DTDs, entity-backed metadata attributes and
  malformed roots/containers were consumed, and nested relationships were accepted.
  GREEN: `17 passed, 55 deselected`.
- RED for OPC post-decoding canonicalization: `15 failed, 1 passed, 56 deselected`;
  encoded backslash/NUL/controls, raw controls, non-round-trip encodings, XML attribute
  normalization, and attacker-named ZIP members bypassed validation. GREEN: `18 passed,
  54 deselected`, including canonical relative and `/xl/...` targets.
- Self-review added two more RED-first defenses: wrapper-root worksheet data could be
  yielded before exhaustion and a UTF-16 DTD bypassed the ASCII marker scan (`2 failed,
  72 deselected`). GREEN was `2 passed, 72 deselected`; complete XLSX suite `74 passed`
  with Ruff/mypy clean.
- Correction checkpoints: `5ecab8b` (immutable catalog), `c6899aa` (safe metadata/path
  errors), `efb0191` (XML/OPC hardening), `6610059` (design/plan/D-020), and `026860f`
  (pre-yield root plus multiencoding declaration scan).
- Official inputs, `tests/contracts/expected_source_audit.json`, normalization,
  quarantine, artifacts, and all Phase 1 Task 3 behavior remain untouched.
- Independent final review found no remaining Critical or Important implementation
  issue. Its corroborating runs observed the 113-test focused source-manifest/XLSX suite
  and the three official lineage/parity contracts green.

Observed complete correction-tree gate:

- `uv sync --frozen --all-groups` — PASS: 67 packages checked in 6 ms.
- `uv run ruff format --check .` — PASS: 37 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 37 source files.
- `uv run pytest -q` — PASS: 153 tests in 99.24 s.
- `uv run pytest tests/source_contract -q -m source_contract` — PASS: 3 passed,
  113 deselected in 76.09 s with full official traversal.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official inputs,
  41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` — PASS.

Residual risks:

- Full official lineage acceptance is intentionally expensive because it normally
  exhausts every production iterator; sampling cannot replace this count/lineage gate.
- The GitHub Actions workflow remains locally validated but has no remote run until the
  branch is pushed.
- A-011 must be resolved before its later quality/evidence producer or consumer; Task 2
  does not authorize guessing those schemas.

Exact next task:

**Phase 1 Task 3: normalize domestic bonds and domestic listed products.** Begin with
the failing bond date/source-fidelity tests in the Phase 1 plan. Keep Phase 1 Tasks 4–5
and the Phase 1 gate unchecked until their own evidence exists.

### 2026-08-14 — Phase 1 Task 3: domestic bond and domestic ETF/ETN normalization

Scope implemented:

- Added frozen strict source-cell locator, normalized/derived value, quality-issue,
  and normalization-result contracts. Locators come only from complete `SourceRow`
  cells and preserve raw values, verified checksum, snapshot, sheet, Excel row/column,
  and unchanged cell applicable dates.
- Added pure text, exact identifier, strict date/source-datetime, finite `Decimal`,
  and integral parsers. No parser performs filesystem, database, network, clock, or
  environment I/O.
- Added the strict immutable `1.0.0` rating registry. Missing/unrated and unmapped
  ratings are not comparable; official `C0` and `CC0` remain out of domain, and agency
  values never backfill the primary grade.
- Added pure domestic bond normalization with raw-versus-derived remaining days,
  strict-before-as-of maturity, quantity/maturity tri-state buyability, exact currency,
  rating disagreement, and deterministic nonquarantine warnings.
- Added pure domestic ETF/ETN normalization with distinct product types, exact D-007
  flags, false-before-unknown eligibility, primary/secondary AUM separation, explicit
  domestic currency mapping, independent update fields, and field-specific zero states.
- Added official full-source acceptance only after Tasks 1–5. No official input,
  expected source-audit value, artifact, overseas/public-fund, query, or API behavior
  changed.

Focused RED/GREEN and independent checkpoint review evidence:

| Checkpoint | Observed RED before behavior | Observed GREEN / review result |
|---|---|---|
| shared contracts (`a178438`, `2cad9ca`) | missing `finproof.domain.locators`, then missing normalization error/wrapper contracts; review regressions were `7 failed, 14 passed` because unsafe direct locators were accepted | initial contracts `14 passed`; final locator/source suite `30 passed`; review approved after the direct-lineage fix |
| pure parsers (`5eab49f`, `bb78c80`) | each text/temporal/numeric module was absent; review regressions were `2 failed, 17 passed` for raw string zero status and oversized integral expansion | parser suite `48 passed`; review approved after numeric-bound hardening |
| rating registry (`1a2afa5`, `a5f0481`, `a5dfa17`) | typed errors/registry were absent; first review regressions were `16 failed, 29 passed`; second were `6 failed, 45 passed` for duplicate YAML keys and categories | final registry suite `51 passed`; review approved after serialization/direct-construction and duplicate-key hardening |
| bonds (`e905edf`) | module absent; later behavior REDs were `1 failed, 19 passed`, `4 failed, 37 passed`, and `6 failed, 46 passed` for maturity warning, currency/quantity warnings, and ratings | bond file `52 passed`; combined gate `172 passed`; independent review approved with no Critical or Important finding |
| domestic listed (`7ab7a88`, `388fdd9`) | module absent; state RED was `16 failed, 18 passed`; currency/optional-warning RED was `4 failed, 53 passed` | domestic-listed file `57 passed`; combined gate `229 passed`; review approved, and its Minor combined-quarantine test passed immediately then committed test-only |

Task 6 acceptance evidence:

- The full acceptance contract was permitted to pass immediately because it introduced
  no new production behavior. Its first executable run was `1 passed in 14.16s`; no
  synthetic RED or production correction was introduced. After a type-only test local
  rename and Ruff formatting, the same acceptance was `1 passed in 14.10s`; the Step 4
  run was `1 passed in 14.04s`.
- The accepted assertions exhausted exactly 44,128 source rows without an unexpected
  exception: 42,394 bond rows produced 42,394 records and zero quarantines; 1,734
  domestic-listed rows produced 1,733 records and one quarantine.
- Source groups were exactly 1,202 ETF and 532 ETN before quarantine; produced groups
  were 1,201 ETF and 532 ETN. The only quarantined row was Excel row 1,155 with raw
  `pd_itm_no="KR"` and a blocker located at that exact cell.
- The acceptance assertions proved 42,394 unique bond IDs and 1,733 unique
  domestic-listed IDs. Every declared wrapped field matched its source row's exact raw
  value and full locator, and every derived value named the exact expected input-cell
  locators at as-of `2026-07-11`.

Observed pre-final-review repository gate on acceptance commit `f9d218d`:

- `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups` — PASS:
  67 packages checked in 1 ms.
- focused Task 3 unit command — PASS: 230 tests in 0.24 s.
- official domestic acceptance command — PASS: 1 test in 14.04 s.
- all source-contract tests with the marker — PASS: 4 tests, 113 deselected in
  93.13 s.
- `uv run ruff format --check .` — PASS: 64 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 64 source files.
- `uv run pytest -q` — PASS: 384 tests in 114.63 s.
- `uv run python tools/audit_source_data.py --check` — PASS: 145,393 rows; snapshot
  `2026-07-11`.
- `uv run python tools/verify_handoff.py` — PASS: 61 required files, 9 official
  inputs, 41,384,928 source bytes.
- `uv run python tools/extract_schema_catalog.py --check` — PASS: 207 columns.
- `PRE_COMMIT_HOME=/private/tmp/finproof-pre-commit-cache uv run pre-commit run --all-files`
  — PASS: Ruff check and Ruff format hooks.
- `git diff --check` and `git diff --cached --check` — PASS: no output.

Task 3 commits through the acceptance checkpoint:

- `e855d8a0375037febf3374a7c01424cc00cedc38` — approved domestic-normalization
  design.
- `f2a49136509b1fea9ad1191b992fc4cbd7394c96` and
  `c5d2434ca810e7724d1c4384e566bb56a355b926` — detailed implementation plan and
  plan-review hardening.
- `a1784384da6c90a21cebc341802c189a8adc0717` and
  `2cad9ca8c1f25895d3f0ff08975d340690ed293d` — shared contracts and direct-locator
  review fix.
- `5eab49fa6668d7ba9b800dc9d76cbb228d878d83` and
  `bb78c8075690e0a2eee11cf281b40d49035f5a68` — pure parsers and numeric-bound
  review fix.
- `1a2afa5f05679dad328cb5b078af9558206d6e17`,
  `a5f048174a3bf93aa7d0737c8cbe6fcd2f44a5c3`, and
  `a5dfa170300541f0bdc7f797ceb91a34aba8cd1a` — rating registry and its two review
  fixes.
- `e905edfe5ad3b8f973b2be9fc25c3302b1efaba4` — domestic bond normalization.
- `7ab7a88bdd877175d4b4879199cf3b9042ffa7f3` and
  `388fdd98d7bdaf545fedbae465006c733c597086` — domestic listed normalization and
  review-requested test-only composition coverage.
- `f9d218d4820cb4cf64dae73163a7af53841bfdcf` — official 44,128-row acceptance.
- The Task 3 verification-document commit is recorded in the subsequent
  final-review evidence update and the ignored Task 6 report, because a Git commit
  cannot embed its own final object hash.

Decision-log inspection and residual boundaries:

- No higher-priority conflict or new frozen product decision was discovered, so
  `docs/10_DECISION_LOG.md` was not changed.
- A-011 remains open for the later persisted quality/evidence artifact schema; Task 3
  keeps normalization issues deterministic and clock-free with
  `first_detected_at=None`.
- Q-003 remains open. Bond source quantity and deterministic snapshot-maturity
  validation remain separate rather than guessing the organizer's intended meaning
  of “buyable.”
- Independent whole-branch review of
  `f2a49136509b1fea9ad1191b992fc4cbd7394c96..1a9dc52be0c4d981ec89b008fe2c246e98784ce4`
  was approved with Critical 0, Important 0, and Minor 0. The reviewer independently
  observed 230 focused tests, the official 44,128-row acceptance, 384 full-suite tests,
  Ruff, mypy over 64 files, source audit 145,393, handoff 61/9/41,384,928, schema 207,
  strict serialization/no-I/O probes, clean scope diff, and a clean worktree.
- Final reviewed-tree gate on review-evidence commit `fbbcec4` — PASS: frozen sync
  checked 67 packages; 230 focused tests; official acceptance 1 test in 14.03 s;
  source-contract 4 tests/113 deselected in 91.85 s; Ruff format/check; mypy over 64
  files; 384 full-suite tests in 116.06 s; source audit 145,393; handoff
  61/9/41,384,928; schema 207; pre-commit; diff checks; and clean feature worktree.
- Phase 1 Tasks 4–5 and the Phase 1 gate remain unchecked.

Exact next development task:

**Phase 1 Task 4: normalize overseas listed products and public funds with
quarantine.** Resolve A-011 before its first persisted quality/evidence consumer and
start with the overseas zero/tie preservation RED. Do not start artifact building in
the same uncontrolled change.

### 2026-08-14 — Phase 1 Task 4: overseas listed and public-fund normalization

Scope implemented:

- Aligned the canonical quality-issue JSON schema to the frozen
  `DataQualityIssue.model_dump(mode="json")` contract, including all issue/locator
  fields, explicit Draft 2020-12 `FormatChecker` use, and UTC terminal-`Z` validation.
- Added complete 49-column overseas and 45-column public-fund synthetic rows, a shared
  exact ETF/ETN enum, exact unpadded overseas identity parsing, opt-in literal-`NULL`
  parsing, and strict `FundItemValue` repeated-locator invariants.
- Added a strict all-field `OverseasListedProduct` and pure normalizer. Product type
  comes only from `pd_grp_no`; trading currency comes only from `pd_trd_ccy`; source
  zero/date/timestamp/flag states remain field-specific; no eligibility, staleness, or
  dataset-level constant state is inferred.
- Added a strict all-field `FundAttributeRow` and pure normalizer. The exact input
  `SourceRow` instance is retained; Python accepts only exact `SourceRow` objects;
  canonical JSON is structurally prechecked before validation; every wrapper is
  cross-checked against its exact raw cell and locator.
- Added global public-fund collapse to `itm_no` grain with one sibling attribute per
  contributing source row, complete 44-field representative/equivalent-locator
  evidence, exact raw agreement, stable output, and fail-closed duplicate,
  normalized-collision, and disagreement rules.
- Added the verified official acceptance for 5,646 overseas rows and 95,619 public-
  fund rows. No official input, expected audit, persisted artifact, exact link,
  family, query, API, HCX, or eligibility behavior changed.

Focused RED/GREEN evidence:

| Checkpoint | Observed RED before behavior | Observed GREEN / review result |
|---|---|---|
| quality schema (`d8a6500`, `6f5c93f`) | legacy schema: `2 failed, 17 passed`; review regression: malformed terminal-`Z` values were accepted, `2 failed, 19 passed` | schema `21 passed`; combined contract gate `42 passed`; initial review 0 Critical/1 Important/0 Minor, then approved 0/0/0 after the dev-only RFC3339 checker correction |
| foundations (`8c60cad`) | exact helper import and `FundItemValue` module were absent; a guard-disabled later-source-order mutation failed to raise | fixture/parser cycle `88 passed`; value cycle `16 passed`; regression suite `130 passed`; independent review approved 0/0/0 |
| overseas (`23f02a5`) | missing module; then missing mapping/valid path; policy `6 failed, 14 passed`; model invariants `7 failed, 23 passed` | model scaffold `2 passed`; valid mapping `8 passed`; policy `20 passed`; final model file `30 passed`; regression `105 passed`; independent review approved 0/0/0 |
| fund row (`687a8a5`) | missing model/module; policy `7 failed, 13 passed`; Python/JSON/invariants `44 failed, 38 passed`; padded-currency self-review exposed two failures | scaffold `17 passed`; mapping `23 passed`; policy `20 passed`; invariant suite `82 passed`; final fund/overseas regression `137 passed`; independent review approved 0/0/0 |
| fund collapse (`b554b48`, `cc55153`) | missing models/callables; invariants `20 failed, 75 passed`; duplicate/collision `3 failed, 25 passed`; disagreement `44 failed, 28 passed`; mixed ordering one failure; malformed-key and short-row regressions failed at unsafe lookup; independent review added four duplicate-location failures | scaffold `3 passed`; valid/scale `7 passed`; invariant `95 passed`; producer suites `28` then `72 passed`; final corrected focused suite `190 passed`; initial review 0 Critical/1 Important/0 Minor, then approved 0/0/0 after duplicate source-location rejection |
| official acceptance (`ba2122d`) | no synthetic RED was manufactured because Tasks 1-5 already introduced the production behavior | first run `2 passed in 383.99s`; checkpoint review approved 0/0/0; no production correction was required |

Official acceptance evidence:

- Overseas: 5,646 source rows produced 5,646 unique records and zero quarantines;
  5,587 ETF and 59 ETN; all trading currencies were the source `pd_trd_ccy=USD`;
  363 fee zeroes and 5,283 positive fees; 5,388 recorded-zero and 258 blank one-day
  returns; 5,451 positive, 8 zero, and 187 blank AUM values; 5,638 nonblank values for
  each core text field; 2,360 replication methods; 8 listing-date zero sentinels; and
  10 blank sale plus 10 blank trade flags. Every one of the 49 wrappers retained the
  exact raw cell and complete locator.
- Public funds: 95,619 rows contained 11,139 raw IDs and produced 11,138 item records,
  95,618 attributes, and one malformed-item blocker at Excel row 84,563 for raw
  `itm_no='"'`. The source had 95,619 unique raw pairs, zero raw duplicates, 228 raw
  and 228 trimmed attribute codes, 1,670 padded rows, zero normalized collisions, and
  zero non-attribute disagreement groups.
- Item facts were 11,067 KRW and 71 USD items; 18,416 literal-`NULL` risk-code rows
  across 2,573 items; 5,436 type-`06` rows across 686 items; and exactly 20 below-minus-
  100 cells on five source rows for item `KR515303001M`. Maximum attribute cardinality
  was 16. Every item retained all contributing rows, the lowest-row representative,
  and every agreeing field locator; no family or name-based ETF conversion occurred.
- The selected 32 official multi-attribute rows produced byte-identical two-item,
  32-attribute results in canonical, reverse, even-then-odd, and odd-then-even orders.

Checkpoint reviews and commits:

- `c47e011463c55124f47cba17e048ff3a21857394` — approved Task 4 design.
- `500926afd02f8448916014f88c48e3d772d347ed` — approved detailed plan and frozen
  D-021/refined A-011 decision boundary.
- `d8a6500c96b87001a0b5f709a4560815288a62ee` and
  `6f5c93f601a3bbbea0a7a3077e61bd40c80f5fd6` — quality schema and review correction.
- `8c60cade794f0131e3a5ee68cde28096dd365fa5` — Task 4 foundations.
- `23f02a5ae7d595cd44f8b429655807777c758999` — overseas normalization.
- `687a8a502dafd2386963aa5e9cdc2e867d817bcb` — public-fund row normalization.
- `b554b48c71c1381c249c465ae9a47a89d5c7d0ee` and
  `cc55153c20bffa0fbed40eb50c589ba6d0d9324d` — fund collapse and review correction.
- `ba2122d73f51cc12db014aad8a1e0b538c74ec4d` — official acceptance.
- `70e017c95525969aadd90c9022eadbf5c93d78a7` — Task 4 verification evidence and
  plan/status checkpoint.
- `baf0c21dc83210057003bb545cc127c33882c495` — independent whole-branch review
  evidence; this is the exact reviewed HEAD used by the final gate below.

Observed pre-whole-branch repository gate on implementation HEAD `ba2122d`:

- `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups` — PASS:
  68 packages checked in 2 ms.
- focused quality/domain/normalization command — PASS: 442 tests in 1.97 s.
- bounded collapse scale command — PASS: 2 tests in 10.29 s; JUnit measured 98,240
  transient bytes at 256 rows, 223,424 at 512 rows, and peak live normalized rows 1.
- official Task 4 acceptance — PASS: 2 tests in 364.89 s; the fund normalization body
  measured 261.755902 s and peak RSS 4,963,942,400 before versus 7,303,561,216 bytes
  after (increase 2,339,618,816 bytes).
- all source-contract tests with the marker — PASS: 6 tests, 113 deselected in
  532.19 s.
- `uv run ruff format --check .` — PASS: 77 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 77 source files.
- `uv run pytest -q` — PASS: 642 tests in 575.03 s.
- source audit — PASS: 145,393 rows, snapshot `2026-07-11`.
- handoff — PASS: 61 required files, 9 official inputs, 41,384,928 source bytes.
- schema catalog — PASS: 207 columns.
- pre-commit — PASS: Ruff check and Ruff format hooks.
- both diff checks — PASS with no output; official writable-file count remained zero;
  the implementation HEAD worktree was clean before this documentation update.

Independent whole-branch review evidence:

- A fresh reviewer inspected commit `70e017c95525969aadd90c9022eadbf5c93d78a7`
  with exact tree `c29b6d4bb9c114b92b0236c15a8f7c3644f7f4e9` against the repository
  contract, frozen decisions, approved design/plan, Task 2/3 boundaries, RED/GREEN
  history, and every Task 4 official acceptance invariant.
- Review result: approved with Critical 0, Important 0, and Minor 0. No correction
  commit or new production behavior was required.
- Reviewer fresh evidence: frozen sync checked 68 packages; focused quality/domain/
  normalization tests were 442 passed in 2.18 s; bounded scale was 2 passed in
  10.41 s with 98,240/223,424 transient bytes and peak live normalized rows 1;
  official acceptance was 2 passed in 364.12 s, with fund normalization
  259.344823 s and peak RSS 5,014,470,656 before versus 7,627,603,968 bytes after
  (increase 2,613,133,312 bytes).
- Reviewer Ruff format/check and mypy over 77 source files were clean. Source audit
  remained 145,393 rows at `2026-07-11`; handoff remained 61 required files, 9
  official inputs, and 41,384,928 bytes; schema catalog remained 207 columns; and
  the reviewed tree/worktree was clean.
- This review-evidence commit is recorded in the subsequent final-gate update because
  a Git commit cannot embed its own final object hash.

Final reviewed-tree gate evidence on exact clean HEAD
`baf0c21dc83210057003bb545cc127c33882c495`:

- `UV_CACHE_DIR=/private/tmp/finproof-uv-cache uv sync --frozen --all-groups` — PASS:
  68 packages checked in 2 ms.
- focused quality/domain/normalization command — PASS: 442 tests in 2.03 s.
- bounded collapse scale command — PASS: 2 tests in 10.26 s; JUnit suite time
  10.194 s, 98,240 transient bytes at 256 rows, 223,424 at 512 rows, and peak live
  normalized rows 1.
- official Task 4 acceptance — PASS: 2 tests in 375.23 s; JUnit suite time
  375.122 s and fund-test time 367.262 s. The fund normalization body measured
  270.740757 s; peak RSS was 5,015,289,856 before versus 7,035,207,680 bytes after,
  an increase of 2,019,917,824 bytes.
- all source-contract tests with the marker — PASS: 6 tests, 113 deselected in
  533.72 s.
- `uv run ruff format --check .` — PASS: 77 files already formatted.
- `uv run ruff check .` — PASS: all checks passed.
- `uv run mypy src tests tools` — PASS: no issues in 77 source files.
- `uv run pytest -q` — PASS: 642 tests in 591.54 s.
- source audit — PASS: 145,393 rows, snapshot `2026-07-11`.
- handoff — PASS: 61 required files, 9 official inputs, 41,384,928 source bytes.
- schema catalog — PASS: 207 columns.
- pre-commit — PASS: Ruff check and Ruff format hooks.
- both diff checks — PASS with no output; `git status --short --branch` showed only
  the feature-branch header, the porcelain emptiness assertion passed, and the
  official writable-file search returned zero paths before this documentation update.

Decision boundaries and remaining procedures:

- D-021 is implemented: pure issues keep `first_detected_at=None`; Task 5 injects a
  timezone-aware UTC persistence time whose JSON form ends in `Z`, outside logical
  reproducibility hashes.
- A-003 remains open; Task 4 derives no overseas/public-fund eligibility.
- A-011 remains open only for later evidence, golden-case, and metric contracts.
- Independent whole-branch review, the final reviewed-tree gate, and the authorized
  local fast-forward are complete. Task 5 Checkpoints 1–3 are now implemented and
  independently approved; Checkpoints 4–8 remain.
- Phase 1 Task 5 and the Phase 1 gate remain unchecked.

Exact next development task:

**Phase 1 Task 5 Checkpoint 4: complete generic Bronze streaming and bounded external
staging, ordering, spill, and cleanup behavior from the approved dedicated plan.** Do
not mark Task 5 or the Phase 1 gate complete before official reproduction and review
evidence exists.

## Phase 2 closure — deterministic query engine

Phase 2 was implemented and reviewed on 2026-08-22. The implementation lineage is
`fb9796a`, `d9b1219`, `2fd5bbd`, `ae1f13c`, `a00937b`, `b84b0f2`, `2c0d8b0`,
`438c04c`, `3f5266f`, `c1e1a7e`, `61a9feb`, `b11c19a`, and `08cab98`.

Required-versus-derived selector accounting from the RED/GREEN ledger:

- Task 1: 19 focused RED selectors and 2 derived first-GREEN acceptances; aggregate
  40 passed.
- Task 2: 10 focused RED selectors and 2 derived first-GREEN acceptances; aggregate
  12 passed.
- Task 3: 12 focused RED selectors and 6 derived first-GREEN acceptances; aggregate
  18 passed.
- Task 4: 5 focused RED selectors and 7 derived first-GREEN acceptances; aggregate
  15 passed.
- Task 5: 16 planned focused RED selectors, 2 derived first-GREEN acceptances, and
  16 direct-contract correction REDs; local aggregate 35 passed, expanded aggregate
  55 passed before the final focused field-sort correction, whose three-selector
  predecessor family passed.
- Task 6: all 17 mandatory plan selectors closed with recorded focused RED/GREEN or
  aggregate acceptance; its task aggregate was 41 passed. Review corrections each
  retained separate focused RED evidence; the final affected aggregate was 64 passed
  in 3.31 seconds.

Final unchanged-candidate gate after the last direct D-029 correction:

- `uv run ruff format --check .` — PASS: 229 files already formatted.
- `uv run ruff check .` — PASS.
- fresh non-incremental and standard `uv run mypy src tests tools` — PASS: no issues
  in 229 source files.
- `uv run pytest -q` — PASS: 2,495 tests and 4 expected serialization warnings in
  7,092.78 seconds (1:58:12).
- source audit — PASS: 145,393 rows at snapshot `2026-07-11`.
- handoff verification — PASS: 61 required files, 9 official inputs, and 41,384,928
  source bytes.

Independent review of `438c04c..c1e1a7e` began at Critical 0 / Important 4. Bounded
focused corrections closed rank/aggregate projection, native/partition identity,
candidate identity, and the valid `top_k=50` boundary. The final scope-only review of
`08cab98` verified wrong and omitted aggregate scope rejection plus normal renderer
claims (`3 passed in 0.24 s`) and returned Critical 0 / Important 0.

No official question was guessed. Q-001–Q-010 retain their recorded safe defaults;
Phase 3 is directly constrained by Q-004–Q-007 and Q-010. Open internal items A-004,
A-007, A-012, and A-014 remain fail-closed/deferred exactly as recorded in
`docs/10_DECISION_LOG.md`. Adjacent hardening ideas from review—stricter execution
trace version-map shape and deeper immutability of frozen mapping fields—remain
backlog and did not block Phase 2.

Exact next development task:

**Phase 3 Task 1: implement the typed CLOVA Studio transport and recorded HCX
contract fixtures.** Stop here; Phase 3 has not started.

## Phase 3 closure — HCX planner and evaluation API

Phase 3 was implemented, gated, and reviewed on 2026-08-24. The Phase 2 closure base
was `f7ff0b8`. Phase 3 lineage through the final correction is:

- plan and Tasks 1–2: `b220f81`, `5f94366`, `a8894ee`, `683a880`, `902e45c`,
  `8c386a1`;
- Task 3: `d1ad1d2`, `ac6a2b9`, `af77675`, `4066eff`;
- Task 4: `40088f3`, `8c236fa`;
- Task 5 and its candidate closure: `f5140c6`, `550ec3d`, `1fbc596`, `c159421`;
- final-gate/provider-boundary correction `0dd238b` and whole-Phase review correction
  `46c9001` (`fix: close phase 3 final review findings`).

Required-versus-derived accounting is recorded without inferring missing counts:

- Task 1 has no standalone task report with numerical selector accounting. The ledger
  records implementation commit `5f94366` and an independently closed review.
- Task 2 has no standalone task report with numerical selector accounting. The ledger
  records `a8894ee..683a880` and Critical 0 / Important 0.
- Task 3's report records required response-model RED → 13 passed, evidence-limit RED
  plus a 10,433-byte derived compaction check, endpoint RED → 14 passed, and a
  trailing-slash RED → 9 passed. Subsequent direct corrections record resource fallback
  2 RED → 2 passed, failure-correlation 1 RED → 1 passed, pre-orchestrator correlation
  1 RED → 2 passed, and coverage-only endpoint selectors as first-run GREEN. The final
  Task 3 aggregate was 44 passed with one upstream warning.
- Task 4's report records the required orchestration collection RED, two AnswerService
  timing failures, and logging collection RED; initial GREEN groups were 4 and 1
  passed. Review corrections record permit ownership 2 RED → 2 passed and truthful
  timing/categories 4 RED → 4 passed. Five existing real-planner integrations and one
  API-correlation integration were explicitly first-GREEN. The final Task 4 aggregate
  was 16 passed and the API regression was 24 passed with one upstream warning.
- Task 5's report records separate application-graph, container inventory/CI, load,
  short-soak, Docker permission/Linux/readiness/bounded-row, CI-timeout, and portable
  temporary-directory groups. Load and soak began as plan-authorized acceptances but
  retained focused RED evidence for defects they exposed. The final task aggregate was
  4 passed with 3 expected dynamic-Docker skips; the portability correction was 1 RED
  → 1 passed.
- Task 6's provider-boundary correction was 1 RED → 1 passed. Whole-Phase review
  corrections were: Q-005 byte boundary 1 RED → 1 passed; fallback partial-condition
  handling 3 RED → 3 passed; fallback metric misbinding 1 RED → 1 passed; and detached
  worker drain 1 RED → 1 passed. Recorded affected aggregates were planner 63 passed /
  1 live-HCX skip, fallback 17 passed, service/API 55 passed, and Task 5 file/API 4
  passed / 3 explicit Docker skips.

The corrected final gate on the exact tree committed as `46c9001` produced:

- `uv run ruff format --check .` — 274 files already formatted;
- `uv run ruff check .` — all checks passed;
- `uv run mypy src tests tools` — no issues in 274 source files;
- `uv run pytest -q` — 2,630 passed, 6 skipped, 5 warnings in 7,391.67 seconds
  (`2:03:11`);
- source audit — 145,393 rows at snapshot `2026-07-11`;
- handoff verification — 61 required files, 9 official inputs, 41,384,928 source
  bytes;
- API/E2E aggregate — 25 passed and 1 warning in 1.37 seconds;
- eight-request load — 1 passed in 4.07 seconds;
- 300-second short soak — 1 passed in 313.88 seconds;
- Docker build — manifest-list digest
  `sha256:d2ee40a0bc92a13221d898863c70aae15230e159c717d4e110155e7d5a17add5`;
- outside-container success plus missing/tampered fail-closed smoke — 3 passed in
  3,236.26 seconds (`0:53:56`).

The first whole-Phase review of `f7ff0b8..0dd238b` returned Critical 0 / Important 3:
the Q-005 byte constant, fallback partial interpretation, and detached worker shutdown.
The single correction wave closed all three, including the related metric-misbinding
case. The scoped re-review at `46c9001` returned Critical 0 / Important 0, so review
stopped and closure documentation was authorized.

Operational evidence: an earlier corrected full-suite process lost its agent transport
and exited 143 at 30%. A later cold official-cache process was SIGKILLed and left one
`.artifacts.finproof-stage-*` fixture directory and marker. Those paths were moved,
not deleted, to `/private/tmp/finproof-phase3-orphan.PaDZkC`; the exact official
resolution selector then passed and the later complete gate above was green. This was
an interrupted-run fixture remnant, not a repository-code defect.

The optional live-HCX selector was skipped because `FINPROOF_HCX_API_KEY` credentials
were unavailable. No secret was printed. Q-005, Q-006, and Q-010 remain
`OPEN_OFFICIAL`: temporary API bounds remain fail-closed; Structured Outputs remains
hard-disabled in runtime; and request-validation failures retain bounded standard 422
behavior. Relevant internal items remain open: A-004 (no result cache), A-005 (release
manifest ordering), A-007 (no public operational routes), A-009 (AI seeds are not
reviewed goldens), A-012 (HCX-only provider compliance), and A-014 (strict TDD ordering
in remaining plan steps).

Phase 4 backlog and release prerequisites:

- prove admission independently beyond exactly eight permit requests;
- supplement `tracemalloc`, which excludes native DuckDB/Arrow allocations;
- retain the measured fresh-container estimate of about 176 minutes and the CI
  container timeout of 240 minutes;
- run the required 24-hour soak before release;
- measure whether provider retry needs a minimum remaining-time reserve;
- consider `httpx` `trust_env=False` transport hardening without changing the fixed
  HCX origin.

Exact next development task:

**Phase 4 Task 1: build the canonical golden dataset schema, authoring checks, scorer,
runner, and reviewed canonical set.** Start with the failing `GoldenCase` schema tests
from `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`; do not promote
the 13 `AI-handoff-seed` cases without human review.
