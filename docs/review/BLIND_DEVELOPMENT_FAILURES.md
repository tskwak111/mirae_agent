# Blind Development Live Failure Ledger

## Candidate and report

- Candidate commit: `1970402734654380fc1fa2dcb47d13eebbb606ad`
- Image: `sha256:4f0b378d2fda5ca6c09ed8e587c22ade5c6fc1154e15a1faae037342e192d1d8`
- Artifact logical hash: `977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8`
- Live report: `artifacts/evaluation/blind-development-live.json`
- Report SHA-256: `1ce83f3e1a18044ae3b659dccbdedc7997051ebe26e6751418b9e8e15a8b3c1b`
- Execution: `2026-09-04T15:18:01Z` to `2026-09-04T15:35:46Z`, HCX-007,
  `phase4-planner-v19`, end-to-end evaluation mode

## Observed result

| Class | Count | Severity | Current disposition |
|---|---:|---|---|
| Exact case acceptance | 7 | — | Retain as the pre-correction baseline |
| Planner terminal safe failure (`observed plan is missing`) | 111 | Critical | Stop HTTP load; diagnose redacted provider/validation category before changing behavior |
| Executed plan/result differs from reviewed expectation | 26 | Important | Group by shared owner; correct only evidence-backed common causes |
| Total cases with one or more failed axes | 137 | Critical | Candidate is not eligible for holdout or release |

The 33 executable observations recorded no runtime failure and had mean latency
`12062.788 ms` and p95 `40605 ms`. These 33 observations are not a 144-request
acceptance result and must not be presented as one.

## Failure concentration

The 111 terminal failures span all executable and terminal intents:

| Expected intent | Terminal failures |
|---|---:|
| unsupported | 52 |
| lookup | 16 |
| clarify | 14 |
| screen | 13 |
| compare | 6 |
| screen_rank | 6 |
| aggregate | 4 |

The checked-in planner prompt exposes a flat field-name list but not the issued
field registry's product applicability, value type, operators, sortability, or
aggregation operations. It also does not tell HCX that the current official artifact
has zero admitted holding rows. The bounded diagnostic below confirmed that the two
sampled terminal-reference questions were instead emitted as executable intents with an
empty product-type set.

Among the 33 executable observations, the recurrent differences are terminal `top_k`
and reason canonicalization, `metric_targets`, `top_k_scope`, filter shape, and
cross-product routing. The current report checker also hardcodes
`mode=deterministic-core`, so its replay-identity error is a report-tooling defect for
this planned end-to-end artifact; it is not a runtime replay mismatch.

## Bounded planner diagnostic and correction

- Diagnostic report: `artifacts/evaluation/task6-planner-diagnostic-7.json`
- Report SHA-256: `2359abd88775c15d17b58120f67f7e481519e3bc7ebd1ab40b2285fc568b265c`
- HCX calls consumed: 9 of the approved maximum 14
- Five executable representatives produced valid plans on their first regenerated
  attempt: `CQ-012-003`, `CQ-012-005`, `CQ-012-014`, `CQ-012-017`, and `CQ-012-020`.
- Both terminal representatives, `CQ-013-017` and `CQ-016-017`, failed initial and repair
  parsing at `canonical_schema`; there were no semantic or transport failures.

A focused local RED tested an empty provider-owned terminal reason hypothesis. The
minimal adapter correction passed the focused test and the related `55`-test planner
aggregate, but both live cases still failed initial and repair parsing at
`canonical_schema` (`4` HCX calls total). The hypothesis was therefore rejected and the
code/test change was reverted instead of being promoted. The corrected live report is
`artifacts/evaluation/task6-planner-diagnostic-terminal-fix1.json`, SHA-256
`523f2fd7b7ceb5062fbbae54dbae24b49af0c4241e7efebec94d79b8f1c79c5f`.

The follow-up one-call-per-case diagnostic recorded the same allowlisted failure for both
cases: `canonical_schema`, substage `schema`, path `/product_types`, keyword `minItems`.
Its report is `artifacts/evaluation/task6-planner-canonical-meta-2.json`, SHA-256
`adcfe1987795cc00afb6f18dc1adae22f25068f5cc5543d35ae02150a47f14a8`.
No provider content was retained. This directly identifies an invalid combination of an
executable intent and `product_types=[]`, not a field-registry or provider-transport
failure.

Focused RED required the planner prompt to fail closed for the current artifact's absent
holding/sector-composition relationships, unresolved product aliases, and every empty
product-type plan. The correction adds those rules, repeats the empty-type invariant at
the end of both system and user prompts, and advances the planner identity to
`phase4-planner-v20`. The focused test failed on the missing rules before implementation;
the related prompt/schema/planner aggregate passed `66` tests afterward. Redacted
canonical substage/path/keyword logging was separately added under a focused failing test
and is limited to local schema metadata.

The bounded v20 live retry still failed both cases after one repair each: the first case
reported `/aggregation` `oneOf` twice, while the second reported `/product_types`
`minItems` and then `/aggregation` `oneOf`. Its report is
`artifacts/evaluation/task6-planner-v20-terminal-live-2.json`, SHA-256
`523f2fd7b7ceb5062fbbae54dbae24b49af0c4241e7efebec94d79b8f1c79c5f`.
The repair request previously received only invalid JSON plus generic instructions,
despite the adapter already having safe local failure metadata. A new focused RED now
requires repairs to receive `validation_stage`, `canonical_path`, and
`canonical_keyword`; the implementation forwards only those allowlisted values. The
focused test, the `66`-test planner aggregate, scoped mypy, and scoped Ruff pass.

The diagnostic-aware repair retry still failed both cases. `CQ-013-017` remained a
schema failure (`/product_types|minItems`, then `/aggregation|oneOf`), while
`CQ-016-017` advanced from `/product_types|minItems` to the semantic failure
`entity_resolution_not_unique`. The report is
`artifacts/evaluation/task6-planner-v20-repairmeta-live-2.json`, SHA-256
`018cba791363cce89a6656303a037073ba1cfeb8cc5c913fdc5f60370c7102a1`.

Under the bounded-review rule, this is a direct frozen-contract violation rather than a
reason to continue prompt retries: absent relationship evidence must fail closed, and an
unresolved entity may not execute. The shared adapter now converts only the otherwise
invalid combination of an executable provider intent plus `product_types=[]` into the
registered local terminal policy: unavailable holding/sector relationships become
`unsupported`; all other empty-type plans become `clarify`. HCX still performs intent
analysis, while deterministic code enforces evidence availability and ambiguity safety.
The focused RED failed for both observed shapes before implementation; it is GREEN after
the correction. The related planner aggregate passes `68` tests, with scoped mypy and
Ruff also passing.

## Corrected terminal live acceptance and bounded review closure

- Corrected report:
  `artifacts/evaluation/task6-planner-v20-corrected-terminal-live-2.json`
- Report SHA-256:
  `c2608c83025d7b619b797e9240d272c5201869f4230618c3f962ebd54ba97335`
- HCX calls consumed: `3` of the approved maximum `4`
- `CQ-013-017`: `observed`, terminal `unsupported`, latency `3,475 ms`
- `CQ-016-017`: `observed`, terminal `clarify`, latency `6,519 ms`
- Both cases preserved empty executable fields, full filter-slot agreement, and
  `top_k_scope` agreement. Their exact terminal `top_k` default and Korean reason text
  differed from the internal reviewed reference, producing `0.8` plan-field scores.
  Those differences do not change terminal intent, evidence availability, execution, or
  user-visible safety semantics and are classified Minor/non-blocking rather than a
  reason to overfit the runtime to benchmark prose.

The first independent correction review returned Critical `0` / Important `1`: a
nonempty product-type plan could bypass the absent-relationship guard. Focused RED/GREEN
closed that owner-level gap. The single permitted re-review returned Critical `0` /
Important `1`: relationship wording such as `보유한` could still bypass the filter-based
guard. Under the bounded-review rule, root adjudication classified that finding and the
subsequently observed pre-canonical native-grain and non-unique-entity paths as direct
frozen-contract violations, then corrected them with focused RED/GREEN tests. No third
review loop was opened. The corrected live acceptance above leaves zero unresolved
Critical or Important findings; only the two documented Minor reference-exactness
differences remain.

Fresh post-format local evidence: the two planner test files pass `70` tests in
`2.72 s`; scoped Ruff format/check passes for all eight changed source/test files; scoped
mypy reports no issues in those eight files; and the local/remote corrected-report hashes
match. The corrected candidate container exited `0` without OOM, while the existing
production container remained running and was not modified.

## Guardrails and next action

- No holdout case was opened or transmitted.
- Do not weaken schema, semantic validation, evidence checks, or reviewed expectations.
- Do not interpret five regenerated successes as broad correctness acceptance; the
  pre-correction 144-case report remains failed.
- The planned 144-case HTTP load was not started because Step 8 requires only the
  affected-case rerun after correction; repeating the full failed development run solely
  to prove the correction is prohibited.
- Exact next task: stage and commit the Task 6 correction/evidence, then freeze and attest
  the Task 7 candidate before any private holdout case is revealed or transmitted.
