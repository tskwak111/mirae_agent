# Blind Evaluation and Submission Hardening Design

**Status:** Approved by the user on 2026-09-03

**Scope:** Add a 192-case latest-data evaluation program, preserve a genuinely unseen
48-case holdout through the only allowed correction, close the official ontology and
proposal deliverables, and submit the resulting exact runtime candidate without
weakening any frozen FinProof contract.

**Preserved architecture:** HCX-007 performs the two organizer-mandated generative
stages. Validated plans, deterministic retrieval and calculation, Source Fidelity,
evidence construction, claim verification, and the exact five-string `GET /answer`
surface remain unchanged unless an observed development-case failure proves a bounded
defect.

## 1. Authority and objective

The 2026-08-24 organizer notice and Q&A supersede the July PDF only where they differ:
the active distribution is 2026-08-24, the evaluation shape is 35 questions including
5 unanswerable questions, HCX is mandatory for intent and final wording, and the
physical no-response boundary is 300 seconds. The PDF remains authoritative for the
20/40/40 weighting, required repository and ontology deliverables, technical-proposal
content, API shape, organizer-private-repository submission, deadline, and continuous
evaluation operation.

The objective is not to tune to the organizer-shaped 35 cases. It is to expose failures
on a broader latest-data development corpus, make at most one evidence-driven
correction, and then measure the untouched candidate on a separately custodied
holdout. The holdout result is evidence, not another tuning input.

## 2. Chosen corpus shape

Reuse the existing 24-case batch workflow. Add eight batches, `012` through `019`:

| Partition | Batches | Cases | Visibility |
|---|---|---:|---|
| development | `012`-`017` | 144 | revealed after authoring; eligible for diagnosis |
| holdout | `018`-`019` | 48 | hidden from the root implementer until final freeze |
| total | `012`-`019` | 192 | within the approved 120-200 range |

The target mix is weighted toward the organizer's stated hard areas rather than evenly
duplicating the existing 265 canonical cases:

| Behavior family | Development | Holdout |
|---|---:|---:|
| cross-product, metric-period, currency, and top-k scope | 42 | 14 |
| constituent/sector to product and product to constituent | 36 | 12 |
| missing, zero, invalid code, state, and unavailable period | 24 | 8 |
| unanswerable, unsupported, and clarification | 24 | 8 |
| typo, synonym, ticker, ISIN, and official-name variants | 18 | 6 |
| total | 144 | 48 |

Every case uses the 2026-08-24 artifact and its actual registered fields. Questions are
deduplicated against the 265 canonical cases and the approved organizer 35 by both
normalized text and declared behavior signature. Cross-product cases select at least
two native product types. The unsupported/clarification family is slightly
over-weighted relative to the organizer's 5-of-35 shape so a false-positive answer is
exercised more often.

## 3. Question and reference construction

The existing HCX-only candidate-authoring boundary is reused. Generation starts from
a bounded behavior blueprint containing only registered product types, fields,
metrics, operators, periods, state semantics, and exact source-backed entities. HCX
may phrase the Korean question and draft a plan; it does not invent expected numeric
values or source facts.

References are admitted only after all of the following agree:

1. the question and expected plan express the same requested behavior;
2. every plan field and metric is in the runtime registry;
3. an independent deterministic/reference query confirms product set, order, values,
   exclusions, and applicable-date semantics;
4. material answer claims map to expected evidence requirements;
5. an independent reviewer approves answerability and expected limitation behavior.

Known unsupported facts are not manufactured merely to make a case answerable. A
constituent or external-information case is answerable only when a previously admitted
sealed source satisfies the existing provenance, licensing, exact-link, cutoff, and
coverage rules. Otherwise it becomes an explicit unsupported/partial-coverage case.
Official values always win over supplemental values, and runtime performs no live
external-data retrieval.

Before any authoring or live execution, record the exact HCX transfer content and a
hard call ceiling and obtain one bounded user approval. Secrets, unrestricted rows,
and unregistered internal meanings are never sent.

## 4. Holdout custody

A holdout curator is separate from the root implementer and the later code reviewer.
The curator creates and validates batches `018`-`019` in a private NCP temporary
location, records their suite SHA-256, count, distribution, reference-review identity,
artifact hash, and generation versions, and returns only that manifest to the root.
Plaintext questions, plans, expected results, and per-case outcomes are not copied into
the root worktree during development or correction.

The holdout runner accepts only the sealed suite checksum and the frozen candidate
identity. It emits aggregate metrics and operational counts to the root. The curator
retains the detailed report until the candidate is declared final and no further
behavior correction will be made. After that point the detail may be disclosed for
audit, but disclosure does not authorize another correction; doing so would invalidate
the holdout claim and require a newly authored holdout.

This is procedural isolation with recorded custody and hashes, not a new encryption or
secret-management subsystem.

## 5. Development execution and the single correction

Run the 144 development cases once through the deployed NCP `GET /answer` endpoint.
Bind the report to the exact code commit, image digest, artifact logical hash, registry
versions, planner/answer prompt versions, HCX model, case checksum, and environment.

Measure:

- plan and semantic-validation accuracy;
- product-set F1 and order accuracy;
- numeric exact match;
- evidence and material-claim coverage;
- answer semantic and limitation accuracy;
- response failure rate, mean, p95, and maximum latency;
- public safe-failure category and redacted stage latency.

Only observed Critical/Important failure clusters enter correction. Each changed
behavior follows focused RED -> minimal GREEN using the recorded provider response or
the smallest synthetic equivalent. Run only affected live cases after the correction;
do not repeat the complete 144-case execution. Minor wording preferences, speculative
hardening, unavailable unlicensed data, and out-of-scope adjacent features remain
backlog items.

There is one correction checkpoint and one independent re-review. A required change to
public API, data ownership, security boundary, Source Fidelity, or another frozen
behavior stops execution for a decision-log update and independent plan review.

## 6. Final holdout and acceptance

After correction and focused verification, freeze a candidate and run the 48 holdout
cases exactly once. The target and hard boundaries are:

| Metric | Target | Hard boundary |
|---|---:|---:|
| request failures | 0 | 0 |
| numeric exact match on supported claims | 1.00 | no unsupported numeric claim |
| evidence coverage on material claims | 1.00 | no uncovered material claim |
| limitation accuracy | 1.00 | no answer fabricated for an unanswerable case |
| plan/product/order and answer semantics | >= 0.95 | report actual score without tuning |
| p95 latency | < 15 seconds | every response < 300 seconds |

A miss below the performance target is reported honestly and does not trigger holdout
tuning. A security, data-integrity, unsupported-claim, or API-contract failure blocks
release because it violates an existing contract rather than merely missing a score
target.

## 7. Ablation and existing performance evidence

Only after holdout measurement, run the A-E ablation on the approved organizer 35-case
suite with two repeats and identical HCX/artifact/configuration identity. Do not promote
the existing interrupted 265-case July-bound ablation files. Write the new raw variants
and aggregate report to distinct latest-data paths.

Reuse the accepted Task 10 v22 35-request load and 20-cycle soak reports only when the
single correction makes no runtime/data/prompt/policy/image change. Do not rerun them
merely to restate already sealed evidence. If runtime behavior changes, build a new
exact candidate and rerun the organizer-shaped final load and bounded soak required by
the current phase plan; old-commit reports cannot attest the new candidate.

## 8. Official submission closure

The final repository must add and validate the five mandatory Turtle files:

```text
ontology/common.ttl
ontology/bond_kr.ttl
ontology/etf_kr.ttl
ontology/etf_gl.ttl
ontology/fund_pub.ttl
```

They describe the implemented product identities, native grains, metric/state/evidence
relationships, and provenance model. They do not create a second runtime ontology or
claim unsupported external knowledge. Use the simplest available Turtle parser for one
syntax/import/reference check; add no new dependency if an installed parser suffices.

Generate the technical-proposal PDF after final measurements so every quantitative
claim points to a sealed report. It covers the required architecture, specialized data
and ontology engineering, retrieval design and rationale, pipeline and feature flows,
user scenarios, expected impact, extensibility, and reproduction appendix. It must
distinguish deterministic-core latency, live HCX endpoint latency, bounded soak duration,
and holdout results without inflating any claim.

Before 2026-09-06 23:59 KST:

1. run the mandatory full repository gate once on the final code candidate;
2. build and verify the exact image/artifact/release manifest;
3. deploy that exact image to NCP and smoke-test the five-string `GET /answer` contract;
4. push source, proposal, API specification, README, and ontology files to the
   organizer-provided private repository;
5. record the endpoint and keep it continuously available from 2026-09-07 through
   2026-09-20;
6. tag and freeze code, data, prompts, policies, image, and deployment configuration.

The personal `tskwak111/mirae_agent` repository is a backup/mirror, not the official
submission channel.

## 9. Verification and review discipline

- Focused tests only during authoring, runner, custody, ontology, and observed-failure
  behaviors.
- Related aggregate evaluation tests only when each bundle closes.
- One final full Ruff, mypy, pytest, source-audit, and handoff gate for the final
  candidate; repeat it only if code changes afterward.
- Exact staging; existing user-owned ablation edits, review drafts, and PDFs remain
  untouched unless explicitly incorporated.
- Implementation and independent code review use separate agents/worktrees. Review is
  limited to the approved contract and diff; only Critical/Important findings block.
- Closure documentation is updated once after implementation commit and 0C/0I review.

## 10. Stop conditions

Stop without widening the experiment when a source checksum changes, a reference
cannot be independently supported, holdout plaintext reaches the root before freeze,
the HCX call ceiling would be exceeded, the endpoint/image/artifact identity differs,
an unexplained test or live failure occurs, or an official instruction conflicts with
this design. Record any resolved official conflict in the decision log before resuming.
