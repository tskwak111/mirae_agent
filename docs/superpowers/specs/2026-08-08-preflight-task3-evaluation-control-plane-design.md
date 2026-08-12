# Preflight Task 3 — Evaluation Control-Plane Design

**Status:** FROZEN — owner-approved written specification; implementation not started

**Scope:** Preflight Task 3 only — establish typed evaluation contracts, complete official-column
coverage accounting, aggregate-proof structure, and machine-validatable repository contracts for
open/locked/sealed governance. This task does not build the production query engine, create locked
or sealed truth, enforce out-of-band custody or ACLs, run a release evaluation, or claim release
readiness. Operational enforcement remains a Phase 4 responsibility.

**Decision owner:** repository owner

## 1. Problem and approved direction

The existing handoff has three evaluation weaknesses that would make later quality claims
unreliable:

1. `schemas/golden_case.schema.json` accepts `expected_plan`, `expected_result`, and
   `expected_answer` as arbitrary objects. The 13 visible AI-authored seeds are partial semantic
   notes, not canonical QueryPlans or typed truth.
2. The repository has 207 official source columns but no exact, machine-readable disposition for
   every `(table_id, column_name)` pair and no proof that planner aliases resolve to supported or
   explicitly blocked concepts. The known `risk_grade` alias is not registered as a field or
   metric.
3. Open, locked, and sealed evaluation lanes exist only in prose. There is no suite commitment,
   release-candidate fingerprint, lifecycle validation, one-use consumption rule, denominator
   contract, or repository control that prevents visible seeds from being relabeled as independent
   truth.

The original Preflight Task 3 plan is internally impossible as written: it requires all current
seeds to validate against a canonical QueryPlan and also requires removing `filters` to fail, while
12 of 13 current seeds already omit `filters`; it does not authorize editing the seed file. It also
requires enforceable lane separation but authorizes only prose documentation for governance.

The owner approved these repairs on 2026-08-08:

- add `tests/golden/seed_cases.jsonl` and affected downstream governance/phase documents to Task 3
  scope;
- migrate all 13 seeds to strict typed contracts without creating new product IDs, results, or
  human-review claims;
- create machine-validatable suite, freeze, lifecycle, and report contracts now while leaving the
  secure store and runner to Phase 4;
- treat the atomic truth-release commit, which occurs before decryption, as one-time consumption,
  regardless of later success, failure, timeout, runtime error, or custodian crash;
- permit at most one retried case invocation across the entire suite/version, and only when an
  attested infrastructure failure happens before the truth-release commit and the failed transport
  is durably fenced with zero accepted response bytes;
- use an available independent human as the future curator/reviewer/custodian; and
- reconcile the governing remediation design's newly sealed corrected-candidate requirement with one
  owner-policy-bounded internal conditional child: at most two candidate cycles per authenticated
  organizer opportunity, child contents frozen before parent output, no third/reset/replacement, and
  immediate stop if a higher-priority official rule forbids that internal remediation path; and
- select the enforceable preflight control-plane approach rather than a prose-only patch or an
  early Phase 4 evaluator implementation.

**Owner decision resolved.** On 2026-08-09 the repository owner directed this current written design
to freeze and become the implementation basis, thereby selecting delayed historical Phase-4 replay:
the named Phase-2/Phase-3 checkpoints pin candidate bytes and provenance, but expose no locked result;
Phase-2 results neither guide nor gate Phase 3. Phase 4 replays both pinned candidates in policy order
and records their reports as historical evidence before release readiness. `docs/10_DECISION_LOG.md`
records this as `D-017 FROZEN`; the governing remediation design and Phase-4 gate/plan use the same
semantics. A later official instruction still overrides and stops any conflicting execution.

Frozen design base:

- commit: `2cdf70bbeb55ee7b7175ca48fe9637c027d7e61f`
- branch: `codex/preflight-safety`
- worktree:
  `C:\Users\ss020\바탕 화면\mirae_agent\.worktrees\preflight-safety`

## 2. Approaches considered

### A. Minimal schema patch

Tighten the three golden objects, add the 207-column report, and describe evaluation lanes in
Markdown.

Rejected because static prose cannot make truth leakage, suite reuse, fingerprint drift, or
denominator manipulation detectable by repository contracts. It would not satisfy the approved
requirement for a machine-validatable lane boundary.

### B. Enforceable preflight control plane — selected

Create closed typed schemas, a deterministic coverage generator, schema-backed deterministic cross-
object governance validation, strict visible-seed migration, and adversarial contract tests. Freeze the
interfaces that Phase 4 must implement while keeping all locked/sealed payloads outside the
repository.

Selected because it closes the repository-contract gaps and freezes the Phase 4 enforcement
interface without prematurely building secure storage, scoring, or the one-time evaluator. It does
not claim to close operational custody or out-of-band disclosure risks by itself.

### C. Implement the complete evaluator early

Build encrypted storage, ACLs, a reference executor, a one-time runner, and scoring before the
production engine exists.

Rejected because it duplicates Phase 4, introduces operational dependencies before their
consumers exist, and expands the preflight task beyond contract enforcement.

## 3. Architectural boundary

Task 3 creates four independent control-plane units:

1. **Typed evaluation contracts** — canonical QueryPlan, expected result, expected answer, golden
   case, aggregate evidence, and a closed local schema registry.
2. **Coverage control** — exact disposition of all 207 official column pairs plus product-scoped
   question concepts and planner-alias bindings.
3. **Evaluation governance** — suite manifest, release-candidate fingerprint, lifecycle event,
   report schemas, versioned policy, and cross-object validation.
4. **Handoff enforcement** — required-file registration, local-reference checks, visible-seed lane
   checks, forbidden truth-path/content checks, and stable diagnostics that continue to work with
   `python -S`.

These units exchange versioned JSON/YAML-shaped values. They do not import production domain
modules, execute financial queries, call an LLM, access external storage, or create evaluation
truth.

Phase 4 consumes these interfaces to build:

- the independent reference-query and human-curation workflow;
- secure external locked/sealed storage, ACLs, audit logs, and recovery controls;
- the immutable global history-genesis dossier, atomic registry-head store, and append-only
  claim, transport-fence, truth-release-commit, and post-outcome history;
- atomic pre-decryption truth-release consumption and one-time evaluation execution;
- release-candidate fingerprint capture and matching;
- scoring, disclosure, threshold, and final-report execution; and
- actual locked and sealed suite versions.

Task 3 may include example values only inside tests. Test fixtures use synthetic hashes, product
identifiers, and claims and may not be presented as competition truth.

## 4. Closed JSON Schema registry

Use JSON Schema Draft 2020-12. Every Task 3 schema has:

- an absolute `$id` under `https://finproof.local/schemas/`;
- `additionalProperties: false` at every object boundary unless a property-name map is explicitly
  part of the contract;
- explicit required fields;
- bounded arrays and strings where unbounded content would weaken runtime safety; and
- local, allowlisted `$ref` targets only.

Create `schemas/evaluation_common.schema.json` as the single definition source for stable codes,
lowercase SHA-256 values, exact-decimal strings, typed product references, segment references,
versioned ID/reference shapes, the private archive record descriptor, and the exact evidence-package,
case-set-entry, case-set-index commitment, reference-executor/derivation/disjointness records,
evaluation-scope terminal schedule, deterministic-core request/result wire, and candidate-
isolation-profile/resolved-state and candidate-cycle-identity projections. Other Task 3 schemas
reference these definitions instead of copying
them. The commitment shapes freeze record identity/ordinal/schema-ref/length/SHA fields, never private
values.

Common bounds are fixed: stable internal IDs are 1–128 ASCII characters matching
`^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`; codes use the stricter uppercase pattern defined below;
human questions are 1–4,000 Unicode characters; general provenance/source strings are 1–4,096
characters; counts are integers from 0 through 9,223,372,036,854,775,807; per-case reference/fact
arrays contain at most 1,000 items; and suite/report breakdown arrays contain at most 10,000 items.
Native product IDs are non-empty source identifiers up to 256 characters and are not forced into
the ASCII internal-ID pattern.

`$defs/candidate_cycle_identity` is a closed sealed-only object with exactly
`organizer_opportunity_id`, candidate-specific `release_cycle_id`, `candidate_cycle_id`,
`candidate_cycle_ordinal` (`0` or `1`), `global_budget_slot_id`, nullable
`parent_release_cycle_id`, nullable `parent_candidate_cycle_id`, and nullable
`parent_global_budget_slot_id`. Ordinal 0 requires all three parent fields null. Ordinal 1 requires the
same `organizer_opportunity_id` as ordinal 0 and requires its three parent fields equal ordinal 0's
release-cycle, candidate-cycle and slot IDs byte-for-byte. The two identities require distinct
`release_cycle_id`, `candidate_cycle_id`, and `global_budget_slot_id` values, and the exact ordered two
complete `candidate_cycle_identity` objects are the organizer-evidence value; no second/resulting-slot
alias exists. Neither
release-cycle ID is equal to or implicitly derived from a slot ID. Each candidate-specific release
cycle admits at most one result-bearing original sealed disclosure; its sole authenticated zero-budget
correction remains a revision of that original, never a second result-bearing release cycle.
Locked/open objects forbid the whole projection. Every sealed manifest, reserve, claim, lifecycle,
fingerprint, run/runtime, attempt/set, truth, outcome, report/history, and cumulative object reproduces
this projection byte-for-byte rather than inferring it from an opaque slot label. In every later exact
field list, the shorthand `release cycle` includes this complete conditional projection for a sealed
branch but never makes `release_cycle_id` a slot key; omission, duplication, partial copying, or
inference from a slot ID is schema-invalid.

The append-only `release_cycle` index value is the immutable one-to-one mapping
`{release_cycle_id, organizer_opportunity_id, candidate_cycle_id, candidate_cycle_ordinal,
global_budget_slot_id}`. Exactly one candidate-cycle-state leaf reproduces that mapping; no other
candidate or opportunity may name the release-cycle ID. The candidate-cycle state is therefore the
only lifecycle state for that candidate-specific release cycle: ordinal 1 begins dormant, owner
activation advances that same bound state without creating a new release-cycle leaf or budget, and the
single `active -> reported_* | burned` edge makes a second result-bearing original impossible.

`$defs/deterministic_core_request` is the closed candidate-boundary request object with exactly
`question_id` as a 1–256-character string and `question` as a 1–4,000-character string, both under the
canonical Unicode-scalar/no-lone-surrogate overlay and with no additional pattern normalization.
`$defs/deterministic_core_result` has exactly `verified: true`, bounded
string `retrieved_context`, bounded string `think_trace`, and bounded string `answer`; each result
string has `minLength: 0` and `maxLength: 1048576`. The result wire deliberately permits an empty
`answer` so the common candidate-response layer can apply its deterministic `MISSING_RESULT`
precedence; only `FINPROOF_CANDIDATE_RESPONSE_V1` requires a non-whitespace answer for completion. The
complete invocation input is the closed object
`{request: deterministic_core_request, plan: <schema-valid canonical QueryPlan>}`. The isolated image's
code/fingerprint-bound adapter converts its internal `AnswerResult` before the process boundary:
`verified` must be true, `retrieved_context` is copied, `execution_trace.to_compact_string()` becomes
`think_trace`, and `text` becomes `answer`. No raw `AnswerRequest`, `AnswerResult`, or
`ExecutionTrace` object crosses that boundary. The adapter adds the committed request echoes and
strictly emits `FINPROOF_CANDIDATE_RESPONSE_V1` under the 1,048,576-byte pre-parse cap. The execution-
contract lock binds the absolute fragment refs and canonical fragment SHA-256 values for these two
`$defs`, the canonical QueryPlan root schema ID/content hash, and the adapter artifact/version; it
never hashes an undefined future Python-class schema.

`$defs/candidate_isolation_profile` is a closed, candidate-build-independent execution-kind `oneOf`.
Both branches contain profile ID/version, immutable candidate UID/security-context policy, required
read-only-root semantics, exact candidate-visible artifact/mount roles, exact environment-name and
secret-purpose roles, immutable resource-attestation requirements, exact IPC endpoint roles,
process/namespace/no-new-privileges policy, and a deny list that
includes every custodian archive, private-history/private-control/case-set/truth/session/scoring store,
KMS/audit/custodian credential, host/container control socket, cloud metadata credential, and
unlisted filesystem or IPC resource. The common allowlist may expose only candidate code/config,
registered schema/metric artifacts, and the official read-only source snapshot. `deterministic_core`
adds only the closed request/plan input and response-buffer IPC roles and permits no secret or network
credential. `end_to_end_api` adds only the closed request/response-buffer roles plus the registered
HCX credential purpose and deny-by-default egress-proxy IPC role; it never exposes a QueryPlan or
custodian resource. Paths, environment values, credential values, hidden record IDs, and private
store metadata never enter a public projection. Phase 4 continuously attests the resolved mount,
environment-name, secret-purpose, UID/security-context, namespace, and IPC sets from the candidate
runtime rather than trusting a caller-supplied profile label. The static profile deliberately excludes
candidate-specific root-image/code/config/resource and credential-resource attestation hashes so P2
to P3 tuning and an authorized remediation build do not rewrite a pre-output suite reservation. The
profile projection does not contain
its own digest; `candidate_isolation_profile_sha256` is SHA-256 over its complete schema-valid
Canonical JSON v1 bytes and is carried only by the registry wrapper and downstream bindings.

`$defs/candidate_build_resource_manifest` is a closed candidate-specific projection with exactly
manifest version, execution kind, selected isolation-profile ID/version/SHA-256, root-image digest,
ordered candidate-visible artifact/mount-role entries with immutable resource/content-attestation
SHA-256 values, ordered environment names, ordered secret-purpose/credential-resource-attestation
SHA-256 pairs, UID/security-context/capability/namespace values, ordered IPC endpoint roles, resolved
network mode/destination roles, and the candidate code/config/production-schema/artifact/dependency
identities that the freeze fingerprint already requires. It contains no filesystem path, environment
or secret value, private record ID, result, current/future head, or its own digest. It appears complete
inside the freeze fingerprint; `candidate_build_resource_manifest_sha256` is its external Canonical
JSON v1 SHA-256 and is the only form copied into manifest, claim, runtime, attempt, outcome, and report
bindings. The manifest must satisfy the selected static profile's roles and denial rules field-for-
field. Evaluation, GoldenCase, common-response, scoring-rule, disclosure, and governance schemas are
not candidate-build components and cannot be changed by this projection.

The separate strict `$defs/evaluation_control_plane_resource_manifest` identifies the current
Phase-4 runner/controller that replays a candidate artifact. It contains exactly manifest version,
native Git object format/commit/tree OIDs, code/config/schema/dependency-lock hashes, controller/
runner image and artifact content identities, an ordinal-ordered exact four-entry array of strict
`$defs/evaluation_control_plane_public_role_attestation`, and the complete deployment-trust-anchor-
manifest digest. Each role-attestation entry contains exactly version, one distinct literal role from
`isolation_controller | deny_egress | kms_policy_verifier | private_store_reader`, public-safe service/
artifact class, immutable content-attestation SHA-256 and deployment-trust role; it contains no resource
locator or access-enabling value. The complete manifest is intentionally repository-public-safe and
non-secret because the fingerprint embeds it. It forbids candidate code/prompt/model fields, case/
truth/output, current/future heads, filesystem/object-store paths, URL/host/socket endpoint, tenant/
account/project/namespace ID, ACL principal or policy bytes, private resource/store/key ID, credential/
token/certificate material, environment value, image-registry credential and secret metadata. Its
complete-object external SHA-256 is never a member, and neither that SHA nor a role-attestation digest
is a hiding commitment. A deployment that cannot classify every permitted field as public-safe must
refreeze a distinct authenticated public projection before use rather than copying the private value.
Every fingerprint and runtime observation binds both this current control-plane manifest and the
separate candidate-build manifest. For a delayed locked replay, candidate source/build identities
must equal the old phase-gate checkpoint subject while control-plane identities must equal the current
deployment-pinned Phase-4 controller; substituting either side or collapsing them to one Git identity
is invalid.

`$defs/resolved_candidate_isolation_state` is an inline, custodian-private runtime projection—not a
separate content-addressed record—with exactly profile ID/version/SHA-256,
`candidate_build_resource_manifest_sha256`, runtime lease/process-
instance identity, candidate UID/security-context/no-new-privileges/capability and namespace values,
sorted actual resource-role/access-mode entries with immutable resource/content attestation SHA-256
(at most 64), sorted environment names (at most 128), sorted secret-purpose/credential-resource-
attestation SHA-256 pairs (at most 8), sorted IPC endpoint roles (at most 32), resolved network mode/
destination roles, and authoritative observed tick. It forbids filesystem paths, environment or secret
values, hidden record IDs, and caller-supplied opaque extras. Every applicable private runtime
attestation contains this complete projection under its existing HMAC; validation compares it field-
for-field with both the selected static profile and the complete build-resource manifest in the
supplied fingerprint, then with the preceding observation. Public objects carry only the aggregate
runtime HMAC/observation-chain bindings, never this projection or a plain low-entropy digest.
An opaque role, path alias, or credential-purpose label without the pinned immutable resource
attestation is insufficient and is rejected as a substituted mount/credential.

`$defs/evidence_package_commitment_projection` has exactly projection version, suite ID/version,
custodian-private stable case ID, schema/producer versions, and one private archive record descriptor
whose schema ref is the canonical evidence-package schema. It expressly forbids a reference-truth-
derivation receipt descriptor/hash: the evidence-package HMAC is computed first and the later
derivation receipt may bind that complete HMAC reference, never the reverse. The package descriptor binds the complete package
by ID/length/SHA-256 without copying it into the HMAC message. A validator streams that one record,
strictly validates it, and recomputes its canonical length/SHA before accepting the projection. Its
sealed branch additionally requires the exact complete `candidate_cycle_identity`; locked/open
branches forbid it.

The common schema's strict `$defs/hmac_metadata` contains exactly registered `domain`,
`scheme: HMAC-SHA256`, registered projection `version`, and opaque `key_id`. The cross-object
`$defs/hmac_reference` is that same flat shape plus exactly `value` (the lowercase 64-hex HMAC-SHA256
result). Every reference from one object to a foreign HMAC domain uses this exact five-field object,
including manifests, case-set indexes/entries, comparability projections, storage/fingerprint/run/
outcome/lifecycle/history objects and reports. Only the object that computes its own domain may use the
domain-specific owning-field layout frozen by its strict schema and formula below. A bounded collection
may carry `$defs/hmac_metadata` without one value only to pin the profile reproduced by every member
reference. No shorthand scalar, prefixed alias field, missing metadata, ad hoc subset or extra member is
legal. The generated registry below and each formula in Section 8.5 fix the exact domain/version;
validators compare every reference byte-for-byte and secret-verify with the deployment-bound registered
key resource. Neither shape contains key bytes.

This is also a normative type rule for every older narrative property name ending in `_commitment`:
outside the object that owns/computes that HMAC domain, the property's value is the complete
`$defs/hmac_reference`, never a 64-hex scalar. Formula left-hand-side names below denote the owning
domain's computed `.value`; a foreign object obtains that value only inside the five-field reference.
The one explicitly named `expected_private_report_commitment_value` validator argument is an external-
only scalar comparison input, not an artifact field. Any prose that lists a foreign commitment plus
separate scheme/version/key fields is superseded by and normalized to the single reference object;
strict schemas forbid those parallel aliases.

One `$defs/case_set_entry_projection` record has exactly case ordinal/private stable ID, immutable
private-case fingerprint, GoldenCase record descriptor, evidence-package record descriptor and
complete evidence-package `$defs/hmac_reference`, the non-open reference-truth-derivation receipt
descriptor/hash (forbidden for open), plus `eligibility_state` (`eligible` or
`preapproved_excluded`) and a conditionally required
private exclusion reason code. `$defs/case_set_index_projection` has exactly projection version,
suite/version/release-cycle/lane/checkpoint/governance-policy identities, the lane-conditional complete
`candidate_cycle_identity`, selection-policy ID/version, a closed `selection_quota_projection`,
authored/excluded/eligible
counts, the complete exclusion `$defs/hmac_reference`, an ordinal-ordered array of at most 10,000 case-set-entry record
descriptors, `entry_descriptor_list_sha256` over that exact closed descriptor array, and for non-open
lanes exactly one suite-wide `reference_executor_manifest` descriptor/hash reproduced by every
entry's derivation receipt; open forbids it. Each entry
and the one index are private-history bootstrap record kinds at most 16,777,216 bytes, resolved only
through the bootstrap/archive reader and counted inside the fixed 100,000-record/4,294,967,296-byte
initial witness; they are not private-control-bundle record kinds. No complete case, truth, evidence
package, or outcome array is inlined.

`selection_quota_projection` has exactly version and an ordered array of at most 256 closed rules.
Each rule contains a registered quota-rule ID/version, registered selection-partition ID, deterministic
applicability-predicate ID/version/content SHA-256, `count_basis` (`authored` or `eligible`), and
nonnegative minimum, maximum, and selected counts with `minimum <= selected <= maximum`. It forbids case/truth/evidence IDs,
questions, results, people, scope/store metadata, and current/future heads. It is not a separate public
commitment or HMAC domain: it is authenticated only as an exact private field of the existing
`case_set_index_projection` under `K_case_set`.

`config/evaluation_governance.yaml` and its canonical lock contain the closed
`selection_quota_rule_registry`. Each entry fixes exactly the IDs/versions above, a deterministic
predicate-artifact content hash, its complete closed declarative predicate AST, allowed GoldenCase
metadata input fields, count basis, and the minimum/maximum bounds; no free-form predicate, arbitrary
callable, or caller-supplied partition is legal. The AST is an AND-only ordered array of at most 32
clauses, each exactly `{field_id, operator: eq|in, canonical_value}`; `field_id` must be in the rule's
allowlist, `eq` takes one finite canonical scalar, and `in` takes a sorted unique array of at most 64
such scalars. The exact hash projection is the closed object
`{predicate_ast_version: "1", clauses: <that complete ordered array>}`; the digest is external and
absent from the projection and equals
`SHA256(b"FinProof/SelectionQuotaPredicate/v1\x00" || canonical_bytes(projection))`.
Case-set validation streams every referenced GoldenCase and interprets that registered non-generative AST,
recomputes each selected count under the rule's count basis, and compares the complete ordered quota
projection before verifying `case_set_commitment`. Missing rule/artifact, hash drift, self-asserted
count, or a predicate that reads truth/result/output fields fails closed.

The case-set HMAC covers this bounded index projection. Verification streams every entry and its
referenced GoldenCase/evidence-package records, checks unique contiguous ordinals/IDs, recomputes all
descriptors and evidence-package commitments, reconciles counts/exclusions, and then recomputes the
index descriptor-list hash and case-set HMAC. Plain content/descriptor hashes remain custodian-private;
only the secret-backed case-set/evidence-package commitments cross the public boundary. This makes the
10,000-case/1,073,741,824-byte maximum a bounded streaming verification, not one giant
`canonical_bytes` materialization.

Exact schema IDs are:

| File | `$id` |
|---|---|
| `evaluation_common.schema.json` | `https://finproof.local/schemas/evaluation_common.schema.json` |
| `golden_case.schema.json` | `https://finproof.local/schemas/golden_case.schema.json` |
| `golden_expected_result.schema.json` | `https://finproof.local/schemas/golden_expected_result.schema.json` |
| `golden_expected_answer.schema.json` | `https://finproof.local/schemas/golden_expected_answer.schema.json` |
| `evidence_record.schema.json` | `https://finproof.local/schemas/evidence_record.schema.json` |
| `aggregate_evidence.schema.json` | `https://finproof.local/schemas/aggregate_evidence.schema.json` |
| `evidence_package.schema.json` | `https://finproof.local/schemas/evidence_package.schema.json` |
| `evaluation_suite_manifest.schema.json` | `https://finproof.local/schemas/evaluation_suite_manifest.schema.json` |
| `evaluation_suite_history_attestation.schema.json` | `https://finproof.local/schemas/evaluation_suite_history_attestation.schema.json` |
| `evaluation_disposition_policy.schema.json` | `https://finproof.local/schemas/evaluation_disposition_policy.schema.json` |
| `evaluation_freeze_fingerprint.schema.json` | `https://finproof.local/schemas/evaluation_freeze_fingerprint.schema.json` |
| `evaluation_runtime_attestation.schema.json` | `https://finproof.local/schemas/evaluation_runtime_attestation.schema.json` |
| `evaluation_lifecycle_event.schema.json` | `https://finproof.local/schemas/evaluation_lifecycle_event.schema.json` |
| `evaluation_private_control_bundle.schema.json` | `https://finproof.local/schemas/evaluation_private_control_bundle.schema.json` |
| `evaluation_report.schema.json` | `https://finproof.local/schemas/evaluation_report.schema.json` |

The registry contains exactly the repository-owned canonical schemas required by a test or
governance object. Contract tests construct an offline `referencing.Registry`, call
`Draft202012Validator.check_schema`, and validate formats. A reference fails closed when it is:

- relative but unresolved;
- absolute but not registered;
- remote HTTP(S) content that would require fetching;
- a duplicate `$id`;
- a reference cycle that cannot produce a finite validation result; or
- a schema whose declared draft or identifier differs from the registered contract.

`evaluation_private_control_bundle.schema.json` freezes shapes, never private values. Its closed root
is one immutable content-addressed manifest snapshot in an append-only per-run snapshot chain, not one
materialized giant object. It has `bundle_version`, zero-based `snapshot_sequence`, nullable
`previous_snapshot_sha256`, `bundle_stage` (`claimed`, `candidate_sealed`, `truth_committed`,
`terminalized`, `outcome_recorded`, `report_candidate`, `published`, `withdrawn`, `corrected`, or
`burned`), suite/run/registry identity, exact `lifecycle_current_head_sha256`, exact cumulative
`private_control_used_record_count`,
`private_control_remaining_record_count`, `private_control_used_bytes`,
`private_control_remaining_bytes`; exact descriptor IDs/lengths/SHA-256 values for the slot-
preparation receipt, private-control plan/receipt, and private-history plan/suite-archive receipt; a
nullable strict `postfreeze_incomplete_scope_fence_ref` that is null until the one same-stage fence
snapshot and immutable/non-null thereafter; the
recomputed exact secret-backed `evaluation_storage_reservation_commitment` value plus exact HMAC
metadata; and ordered `record_descriptor_delta` and `binary_blob_descriptor_delta` arrays whose
combined item count is at most sixteen. A record descriptor has exactly ordinal, opaque record ID,
closed record kind, canonical absolute schema `$ref`, byte length, and lowercase SHA-256. A binary
descriptor has exactly ordinal, opaque blob ID, kind (`candidate_response`,
`public_report_outbox`, `recovery_record_ciphertext`, or `truth_session_ciphertext`), byte length,
and lowercase SHA-256.

`complete_bundle_snapshot_sha256` is SHA-256 over the complete Canonical JSON v1 snapshot bytes and
is never stored inside the snapshot it hashes. Sequence zero has null predecessor and a nonempty
descriptor delta. Every later snapshot has sequence `prior + 1`, names the exact prior complete
snapshot SHA-256, and derives cumulative ordinals/counters/bytes from that predecessor plus only its
new deltas. IDs and ordinals are unique and contiguous over the complete chain; unknown,
unreferenced, duplicate, or multiply referenced descriptors fail closed. A same-stage successor is
legal only when it adds at least one new descriptor in the deterministic prefix permitted for that
stage. A descriptor-free successor must traverse one expressly allowed stage edge. Each durable
control record/blob creation, reservation decrement, one or more snapshots needed for its bounded
descriptor batch, and the authoritative current-snapshot-pointer CAS are one all-or-none store
transaction. No API may leave an unreferenced durable object. A byte-identical crash replay is
idempotent only when the trusted current pointer already equals the same final snapshot hash. A losing
post-claim CAS creates no durable object, decrement, or snapshot. Tombstone/reaper semantics exist
only for the expressly separated preclaim prepared-allocation exception below.
That snapshot transaction rule applies to every post-claim run record/blob. The exact five preclaim
reservation objects are the sole exception because they necessarily exist before a run current
pointer. They are already descriptor-bound by the slot-preparation/reserve private history and
unified storage HMAC; sequence zero must import all five unchanged, or a losing prepared allocation
must keep them unreachable until its bounded tombstone/reclamation transition. No sixth preclaim
private-control reservation record/blob may exist and no later substitution is permitted. The
separately receipted private-history bootstrap/staging records below are governed by their prepared
allocation and are never imported into this private-control five-record set.
The winning claim transaction additionally creates the exact one-through-eleven-event pre-run
lifecycle chain from draft initialization through consuming. Sequence zero contains exactly the five
reservation descriptors followed by those lifecycle-event descriptors in chain order, no binary
descriptor, and no run-binding, runtime-observation, attempt, dispatch, ingress or later lifecycle
record; the combined delta remains at most sixteen. Its
`lifecycle_current_head_sha256` equals the final consuming event. The claim transaction creates and
attests that deterministic generation-zero/sequence-zero pointer state and persists every lifecycle
event in the same CAS, so none can be durable outside the current snapshot lineage. Only afterward
does the controller compute the initial `run_start` observation and
`run_binding_attestation` against that predecessor; one all-or-none generation-zero-to-one pointer
CAS stores those records in sequence one (or the bounded same-transaction continuation needed for its
descriptor count) before any dispatch. Thus the run-binding HMAC never contributes bytes to the
snapshot hash/pointer attestation that it binds. Sequence zero alone is a legal deterministic
`claimed` crash prefix and recovery must resume this exact next transaction.
The five reservation objects and lifecycle events are never inlined in a snapshot or copied into
another record. Exactly
one descriptor of each required kind must occur in the complete snapshot chain, and every snapshot's
five stable references must point to those same records. Validators obtain the exact authoritative
current pointer from the custodian store, hash the supplied current snapshot, stream every predecessor
to sequence zero, rebuild the descriptor order/counters, stream all five reservation records plus the
exact claim-time lifecycle chain, recompute their canonical bytes/hashes/unified HMAC/event hashes,
and reconcile the current cumulative counters to the two
private-control plan dimensions. Private-history record/byte used/remaining counters are absent from
every private-control snapshot because private-history successors may advance independently. They
come only from the authenticated `PrivateHistoryAllowanceStateModel` in the history witness and must
reconcile to the private-history plan/receipt there. A caller-selected valid ancestor is never an
acceptable current bundle.
Snapshot hashes, sequences, deltas, current-pointer metadata, and cumulative private counters remain
custodian-private. Public history/fingerprint/report objects bind only the already specified secret-
backed storage/private-registry commitments and may not expose a plain snapshot hash or chain length.

Governance pins exactly one private-control current-pointer resource to each activated
`(private_control_store_id, allocation_id, suite_id, run_attempt_id)`. Its resource ID, genesis
SHA-256, and initial generation-zero/sequence-zero/snapshot-hash/attestation-digest state are fixed in
the run binding. Genesis is
`SHA256(b"FinProof/PrivateControlPointerGenesis/v1\x00" || canonical_bytes({pointer_resource_id,
private_control_store_id, allocation_id, suite_id, run_attempt_id, pointer_version: "1"}))`. The
closed `PrivateControlCurrentPointerModel` has exactly those identities plus genesis SHA-256,
zero-based `cas_generation`, current `snapshot_sequence`, current snapshot SHA-256, the exact
`lifecycle_current_head_sha256` reproduced from that snapshot,
`current_state_attestation_sha256`, literal attestation scheme
`ED25519_STORE_ATTESTATION_V1`, and opaque attestation key ID.
The strict validation-only `$defs/private_control_pointer_attestation` is at most 16,384 canonical
bytes and has exactly `attestation_version: "1"`, one closed `signed_projection`, and bounded canonical
base64 `attestation_value`. The signed projection has exactly pointer resource/genesis, store/
allocation/suite/run identities, CAS generation, snapshot sequence/hash, the exact snapshot
`lifecycle_current_head_sha256`,
`prior_pointer_attestation_sha256`, immutable `store_monotonic_epoch_id`,
`store_monotonic_version`, attestation scheme, and opaque key ID. The prior digest is null only at
generation zero; otherwise it equals SHA-256 of the complete immediately preceding attestation.
`store_monotonic_version == cas_generation`, and epoch/scheme/key are byte-identical for the run.
The pointer and signed projection lifecycle head must equal the hash-verified referenced snapshot;
non-lifecycle successors carry it unchanged and a lifecycle append computes event, snapshot, then
pointer attestation in that order.
The signed projection excludes `attestation_value`; the complete-object SHA-256 is
`current_state_attestation_sha256` and is not a field inside the object.
`attestation_value` is exactly the canonical base64 encoding of the 64-byte Ed25519 signature over
`b"FinProof/PrivateControlPointerAttestation/v1\x00" || canonical_bytes(signed_projection)`. The
registered key ID resolves to the externally pinned store public key/fingerprint in governance
policy. This asymmetric store attestation is expressly not an HMAC and is outside the exact Section
8.5 HMAC registry; no implementation may silently substitute an unregistered pointer-HMAC domain.
Initial creation compare-and-swaps an absent pointer to generation
zero/sequence zero. Every later pointer CAS supplies the exact expected resource/genesis/store/
allocation/suite/run/generation/sequence/hash tuple, creates one or more snapshots whose first
predecessor is that expected snapshot, and changes the pointer only to generation `expected + 1` and
the final contiguous snapshot in that same all-or-none transaction. Reset, deletion, rollback to an
ancestor, fork selection, generation skip/replay, or any pointer write outside that transaction is
invalid. A losing CAS writes no object, snapshot, decrement, or pointer state.

`PrivateControlCurrentResourceReader` obtains the actual current pointer, complete attestation bytes,
and current-store read receipt by the pinned pointer resource/genesis IDs; it cannot resolve a caller-
selected historical descriptor. `private_control_pointer_transition_errors` receives that reader,
strictly loads the independently read expected/candidate attestations, checks their complete hashes and
signed projections, verifies prior-attestation chaining, and streams the new snapshot suffix back to
the observed pointer. Initial creation requires the independently read resource to be absent under the
pinned genesis and streams to sequence zero. A read-only validation requires its supplied pointer and
attestation bytes to be byte-identical to the independent current read. A writer additionally holds
that observed CAS generation through its complete transaction; the candidate pointer is accepted only
as the contiguous successor of that exact observation. Phase 4 verifies the registered asymmetric key
and real current-store read/CAS. Every candidate-seal, truth, terminal, outcome, report, correction,
withdrawal, or burn successor that cites the pointer uses this guard. The successor's HMAC-protected
private append binds the exact observed resource/genesis/generation/sequence/snapshot hash but never
publishes it. A caller-supplied ancestor, sequential/resettable adapter, or read released before the
authorized read/action/CAS fails closed.
Any pointer transition that creates a candidate-attempt, burn snapshot or ingress terminal receipt
requires the ingress witness/reader arguments and validates the exact dual-CAS construction; every
other pointer transition requires them null. Thus a private-control successor cannot silently consume
a different or historical ingress prefix.

The authoritative `$defs/suite_preclaim_basis` is the only shared, head-related input shape accepted
by either storage-reservation planner, apart from policy and the private-history planner's staging-
only `bootstrap_descriptor_manifest`. It contains exactly registry/genesis, suite ID/
version/lane/checkpoint/release-cycle, reserve-batch ID/ordinal and head-independent
`reserve_batch_subject_sha256`, governance-policy version, selected execution kind/contract ID/
version/content SHA-256, common response-contract SHA-256, and candidate-isolation-profile ID/version/
content SHA-256 for the static candidate-independent security template,
disposition-policy ID/version/commitment and HMAC metadata, case-set commitment, disclosure class,
curator/reviewer/custodian role IDs, private stable-human-principal attestation SHA-256 and curation-
scope record SHA-256, the byte-identical selected
`evaluation_scope_terminal_schedule_ref`, authored/excluded/eligible counts, and the lane-conditional complete candidate-
cycle identity. An ordinal-1 basis also binds the head-independent conditional-child base SHA-256 and
its ordinal-0 parent identity, but no parent result/auth/fingerprint. It permits that subject digest but forbids the resulting
`reserve_batch` public attestation and `reserve_batch_attestation_sha256`, suite commitment, suite-
reservation or eligibility head, fingerprint, either storage plan/receipt/commitment, claim/run head,
every candidate-build resource manifest/hash or exact code/config/artifact/image identity, raw schedule
bytes/ticks, and every future tick or result. Thus a planner cannot read the later build or manifest it
helps make possible.

Its closed `$defs` cover the exact eight-key private-history append plus variant payload; private-
control current-pointer state/local transition/current-resource read; candidate-ingress current state,
attestation, witness, shared terminal-payload ref, terminal subject/receipt and transition; run binding;
dispatch-prepared subject;
slot-preparation receipt, private-control and private-history reservation plans/receipts plus their
unified HMAC projection;
case-attempt binding; case-dispatch receipt; deterministic-core local-invocation and adapter-receipt
subprojections;
infrastructure and transport-close projections; burn-response-buffer snapshot; candidate-attempt
projection; ordered candidate-
attempt-set graph; retired-token-ledger projection; AEAD nonce-registry state/witness/proofs and claim
receipt; recovery-record
projection; terminal receipt; truth-payload projection; truth-session record; one scoring-work-ledger
entry; one immutable outcome-entry record; ordered
original/corrected outcome-index records; canonical outcome-set-content projection; scoring-
finalization receipt; original and corrected outcome-set root projections; correction-derivation
record; correction-disclosure-delta record; corrected-report-subject record; content-free late-output
receipt and sink-ledger projections; private-report record append; disclosure-outbox record; the
strict private `postfreeze_incomplete_scope_fence`; and the custodian-private verified-published-report receipt. The outbox record binds record ID, the exact pre-CAS predecessor head
(`post_outcome` for an original or `post_adjudication` for a correction), complete public-report
SHA-256, literal `canonical_json_v1_utf8`, exact outbox binary-blob ID/length/SHA-256, and durable-
write timestamp. It never contains its future `report_recorded`/`corrected_report_recorded` head.
Every definition has `additionalProperties: false`, explicit bounds, and discriminator-dependent
required/forbidden fields.

Actual control records are separate Canonical JSON v1 byte objects that must match their descriptor's
kind/schema/length/hash. Closed record kinds include the referenced runtime-attestation and lifecycle-
event schemas and at most two `verified_published_report_receipt` records (one original and the sole
allowed correction); those objects are read through the same descriptor/reader path and are never supplied
again as materialized lists. Actual binary blobs are separate byte streams that must match their
descriptor. Each accepted candidate response appears exactly once and is referenced by exactly one
attempt or burn-buffer snapshot. A typed no-response failure marker forbids a response blob; a typed
failure after positive accepted bytes requires the exact referenced prefix blob. Public-report
outbox bytes likewise appear once and must equal the independently reconstructed canonical report
bytes. Each recovery/session ciphertext appears once, is referenced by exactly one matching encrypted
record, and is never inlined. No raw payload is base64-duplicated inside the manifest or another
record.

`$defs/dispatch_prepared_projection` is a strict private-control record containing exactly record/
projection version, suite/run/case/invocation/attempt/candidate-invocation IDs, selected execution-
contract/response-contract/static-isolation-profile identities,
`candidate_build_resource_manifest_sha256`, the lane-conditional complete `candidate_cycle_identity`,
case-attempt-binding commitment, output-
channel token hash/fence epoch, global slot/active-owner/expected-claim-head/runtime-lease identities,
dispatch sequence, exact branch input descriptor/hash, prepared-at tick, and branch-specific local-
process/IPC or transport-request/origin/TLS fields. It forbids any runtime-observation hash, dispatch-
receipt commitment, invocation/send/result/response field, future state/head, or its own digest.
`dispatch_prepared_subject_sha256` is
`SHA256(b"FinProof/DispatchPrepared/v1\x00" || canonical_bytes(dispatch_prepared_projection))`. Its
record descriptor is appended to the authoritative private-control snapshot before invocation; the
pre-dispatch observation and resulting dispatch-receipt HMAC bind that exact digest/descriptor. A
stale/losing commit cannot substitute or reuse it for another owner/head/fence/input.

`$defs/local_invocation_receipt` is a deterministic-core-only closed subprojection shared by the
candidate-attempt and burn projections. It has exactly receipt version, suite/run/case/invocation/
attempt/candidate-invocation IDs, dispatch-prepared subject SHA-256, dispatch-receipt commitment,
runtime-lease ID and `at_local_invoke` observation hash, local invocation/process IDs,
`call_count: 1`, invocation ordinal, exact input SHA-256, start/end ticks, terminal output-buffer count/
hash/close/tombstone state, and the closed exit class/reason mapping below. It carries no candidate
payload and has no own/future digest. End-to-end objects forbid it.

`$defs/deterministic_core_adapter_receipt` is a core-only closed subprojection inside
`candidate_attempt_projection`, not a payload copy or separate record. It has exactly receipt/mapping
version, callable and adapter artifact ID/version/SHA-256, deterministic request/result fragment and
QueryPlan schema hashes, local invocation/process IDs, `call_count: 1`, exact request-plan input SHA-
256, `verified: true`, canonical deterministic-result byte length/SHA-256, common response-contract
SHA-256, and the exact derived response-blob descriptor ID/length/SHA-256. The canonical result-wire
bytes are deterministically reconstructed from that response by dropping the two request echoes,
copying `retrieved_context`/`think_trace`/`answer`, and adding literal `verified: true`; the pure
validator recomputes their length/SHA and byte-identical mapping without storing a duplicate payload.
The code/fingerprint-bound trusted adapter/controller computes and attests the receipt at the actual
process boundary; only that Phase 4 boundary attestation proves that the internal `AnswerResult`
actually had `verified is True`. The candidate-attempt HMAC authenticates the receipt. End-to-end
attempts and every non-`returned/NONE` core exit branch forbid it; the `returned/NONE` branch requires
exactly one. Phase 4 adapter-parity tests prove the same conversion against the real callable.

`$defs/truth_payload_projection` is one private-control record of at most 16,777,216 canonical bytes.
It has exactly projection version, registry/genesis, suite/version/lane/checkpoint/release-cycle/slot/
run identity, candidate-attempt-set event/commitment and eligible count, case-set commitment, the
case-set-index record descriptor, the ordered eligible case-set-entry descriptor array, and the SHA-
256 of that exact descriptor array. It is derived only by streaming the precommitted case-set index
and entries in eligible invocation order. For every entry, validation streams the referenced
GoldenCase and evidence-package records, recomputes their descriptors, private case/truth/evidence
commitments, and exact eligibility, and rejects an omitted, extra, reordered, duplicate, cross-suite,
or newly supplied expected value. The session plaintext is exactly the canonical bytes of this
record. The scorer accepts truth only by decrypting those bytes, matching their record descriptor,
then resolving and revalidating the referenced precommitted records; it never accepts an independent
caller-supplied expected answer or truth hash.

`compute_private_control_reservation(policy, suite_preclaim_basis)` deterministically returns a closed
reservation plan containing formula version, total bytes, and the ordered per-record-kind
`max_canonical_record_bytes`, `max_occurrences`, and subtotal values for every record/blob that the
one suite can still legally need through burn or truth terminalization, scoring failure/completion,
original report, one correction, sink checkpoints, and outbox closure. The governance lock records
the exact formula/version and constants. Before the
atomic reservation/claim pair, the custodian store must durably reserve that amount. The complete
plan/receipt bytes, their IDs/SHAs, store/allocation metadata, enforcement state, timestamps, and
actual staged/used/remaining usage remain custodian-private and are bound in the private registry
append, run binding, authoritative current-snapshot lineage, outcome, and private report. The maximum
logical allowance and per-kind table are intentionally public-derivable, non-sensitive policy facts
because the lock, formula version, and eligible count are public; the HMAC is not claimed to conceal
that deterministic maximum.
Public
`reserve_batch`, suite-reservation, fingerprint, claim, truth-commit, and repository-report
projections bind only the formula versions and
the secret-backed `evaluation_storage_reservation_commitment` plus the exact HMAC metadata defined in
Section 8.5. Each
append atomically consumes reserved bytes; it cannot exceed the reservation. If storage cannot reserve
the full amount, no claim occurs. Therefore a valid post-truth terminal/scoring/report record can never
be rejected merely because earlier legal records used the budget.

For formula version 1, let `N` be the immutable eligible count. The lock contains a closed table for
every record kind with `max_canonical_record_bytes` and an integer `max_occurrences(N)` expression
derived from the state-machine caps. The size column is an independently generated upper bound over
the complete canonical JSON record schema, including every maximum-length string and maximum-cardinality
array; the generator also constructs a max-shaped witness and rejects a bound below its actual byte
length. Every accepted record kind must be at most 134,217,728 bytes at its schema maximum. Every
schema string/array/object contributing to those maxima is finite; an unbounded definition, unknown
record kind, record whose schema maximum exceeds the per-record cap, or table/schema drift invalidates
the lock before any claim. Reservation bytes equal
the fixed `manifest_snapshot_reservation_bytes` + 67,108,864 candidate-response bytes +
33,554,432 outbox bytes + 48 recovery-record-ciphertext bytes + 16,777,232 truth-session-ciphertext
bytes + the exact
integer sum of `max_canonical_record_bytes * max_occurrences(N)` across the closed table. There is no
compression, deduplication, probabilistic average, or caller-chosen margin in this logical-byte
formula. Contract tests enumerate all record kinds and recompute the same value independently.
They also require the summed maximum record occurrence count to be at most 200,002 and binary-
descriptor count to be at most 10,004 for every legal N. A snapshot consumes one fixed 65,536-byte
reserved slot even when its canonical bytes are shorter. With at most 210,006 cumulative descriptors
and eight possible descriptor-free stage edges on the longest path,
`manifest_snapshot_reservation_bytes` is exactly `210014 * 65536 = 13763477504`; it is not actual-
length accounting inside the object that would make its own counters self-referential. The generated
max-shaped snapshot witness, including sixteen maximum descriptors, must fit 65,536 canonical bytes,
and the generator rejects schema drift above that cap. The occurrence table includes the simultaneous maximum of
30,004 runtime observations for end-to-end or 10,004 for deterministic core, 10,001 attempt bindings,
10,000 dispatch-prepared records, 10,000 dispatch receipts, 10,001 candidate-ingress terminal subjects,
the one-through-eleven claim-time lifecycle events, 10,001 candidate-ingress terminal receipts,
10,000 final candidate attempts (whose
core schema maximum includes the embedded adapter receipt), 10,000 scoring entries, 10,000 original
outcomes, 10,000 corrected outcomes, one truth-payload record, at most two AEAD nonce-claim receipts,
the two encrypted blobs, at most two verified-published-report receipts, the mutually exclusive one
postfreeze incomplete-scope fence safety record when that stop branch replaces later result records,
plus every constant root,
receipt, session, report, correction, and outbox
record. The generated table and maximum schedule explicitly price the terminal subject/receipt schemas,
their two-snapshot-per-terminal suffix and the 10,001-entry receipt accumulator. Late-output receipts,
accumulator steps, and sink checkpoints remain solely in the separately
reserved private-history archive and do not create another bundle snapshot. A generated maximum-
schedule witness for each execution branch must prove its exact runtime/provider occurrences, record
sizes (including the inline resolved-isolation state), descriptor counts, and total before the lock is
accepted. A core witness with any provider record or an end-to-end witness using core-only records is
invalid; the reservation uses the larger legal branch maximum and cannot be caller-lowered.

The preclaim store allocation emits a private `storage_reservation_receipt` with exact receipt ID,
store ID, allocation ID, `slot_preparation_id`, slot-preparation receipt ID/SHA-256, literal
`allocation_kind: private_control`, suite ID/version, formula
version, complete reservation-plan SHA-256, computed byte amount, zero-based
`preparation_generation`, allocation timestamp, head-independent `reserve_batch_subject_sha256`, and
`expected_registry_predecessor_attestation_sha256`. It contains no future
reservation head, claim head, private-append hash, or value derived from those heads. The winning
`reserve_batch` CAS privately binds and activates both complete receipt IDs/hashes/amounts and
produces its new head. Its HMAC-protected private-history append binds the two receipt record
descriptors/SHAs, and validators stream the complete acyclic receipts. Every later private
manifest reproduces its ID/hash/amount. Public history from `reserve_batch` forward carries only the
independently recomputed `evaluation_storage_reservation_commitment` and exact HMAC metadata. A post-
CAS allocation confirmation, if a store requires
one, is a
separate successor record and cannot be an input to either head. Pure validation recomputes the plan
and cross-bindings; Phase 4 additionally verifies the allocation against the real store before
activation.

Both stores use one provisional-allocation state machine keyed exactly by registry ID, global slot ID,
reserve-batch ID, suite ID/version, and allocation kind. Initial staging creates `prepared`; the atomic
`scope_and_slot_prepare_commit` alone changes every winning scope member to `prepared_scoped` while
binding its immutable scope/preparation identities. An ordinary or candidate-cycle-0 winning
`reserve_batch` CAS changes `prepared_scoped -> activated`; the fixed candidate-cycle-1 branch changes
`prepared_scoped -> activated_unclaimed_conditional`. Only a provisional `prepared` allocation whose
combined scope transaction did not win may change `prepared -> abort_tombstoned -> reclaimed` after
the store proves nonmembership of its scope/preparation transaction. A `prepared_scoped` allocation is
never reaped merely because its later reserve does not yet exist. `activated_unclaimed_conditional -> activated` is legal only inside the
unique owner-remediation activate transaction that also creates its reservation/claim. The same state
may instead close only inside parent-pass, parent-pretruth-burn, parent-withdrawal-only, or owner-
decline or `owner_resolution_expired_nonpass` resolution after
proving no reservation, claim, dispatch, run, token, ingress, truth, or result exists. The private-
control allocation changes to irreversible `terminal_unused_tombstone`; the same transition from
`prepared_scoped`, `activated`, or `activated_unclaimed_conditional` is additionally legal only inside the
exact guarded `authority_conflict_preclaim_close` all-or-none suffix after proving no claim/dispatch/
run/token/ingress/truth/result exists, or inside the distinct deterministic
`scope_schedule_deadline_expired` preclaim suffix with the same nonmembership proofs and exact matching
schedule-entry/clock witness. Authority and schedule causes are disjoint closed variants and cannot be
caller-selected. A later physical
`terminal_unused_tombstone -> reclaimed` confirmation is non-authorizing and cannot be hashed into the
earlier resolution. The paired private-history allocation first changes to
`terminal_close_pending_audit`, which permits exactly one direct, branch-exact zero-channel audit-
closure append and no other record. That immediate audit successor alone changes it to
`terminal_archive_sealed`: every existing case/evidence/reuse/audit byte and descriptor then remains
immutable/readable, no later append is legal, and only unused reserved capacity may be released by a
later non-input confirmation. The
control-side `reclaimed` state likewise releases only unused capacity: it retains, or atomically
archives before release, every already written descriptor-bound preclaim object needed to stream and
recompute the slot-preparation receipt, both plans/receipts, unified storage HMAC, reserve transition,
and tombstone for the full audit-retention period. Reclamation never means deleting verification
bytes. No other
activated allocation can be reclaimed. At most one prepared-or-prepared-scoped-or-activated-or-terminal allocation per
key is legal. Generation starts
at zero. A crash or unrelated global append may stale the expected
predecessor. Recovery keeps the same stable allocation key, subject/basis, plans, allocation IDs,
fixed byte allowances, and immutable case/evidence payloads, increments generation by exactly one,
tombstones the old predecessor-dependent proof chunks/actual-archive candidate while retaining the
unchanged staging manifest, and rebuilds the registration ordinals, Sparse-Merkle proofs, archive
predecessor/actual manifest, both receipts/SHAs, unified
storage HMAC, private append, and public-attestation candidate against the new head. A content record
whose bytes are predecessor-independent may be reused by its descriptor; no old proof, manifest,
receipt, HMAC, or candidate remains usable. It never allocates again. A winning CAS makes both
allocations the same branch-appropriate state or neither; a losing scope CAS leaves no public successor
and the bounded reaper must release or refresh only its provisional `prepared` allocation before
another try. A winning scope CAS protects `prepared_scoped` capacity until reserve or an exact terminal
closure.
Activated allocations are never reclaimed while the reserved suite can still produce a required
terminal/history/report successor; the closed unused-child, authority-conflict-preclaim-close and
scope-schedule-deadline-preclaim-close exceptions above are the only post-activation reclamation
paths, and each requires its disjoint typed cause/proofs and permanent no-channel terminal state.

Before the scope-and-preparation transaction, governance pins one private slot-preparation-registry ID/
genesis/current-head lineage. Genesis alone has sequence zero/null prior; reset, fork, deletion, or
alternate genesis is invalid. That transaction atomically inserts one permanent row per scope entry,
each keyed only by `(history_registry_id, global_budget_slot_id)` after proving nonmembership. Its
immutable value binds `slot_preparation_id`, reserve-batch ID, suite ID/version, case-set commitment,
`reserve_batch_subject_sha256`, private stable-human-principal attestation SHA-256, matching curation-
scope record SHA-256 and one complete head-independent `slot_preparation_source` descriptor. Insertion
requires scope membership in the one candidate human-governance scope root and output-exposure
nonmembership in its predecessor root. Same-subject stale-head generations reuse that occupied row. A
different batch, suite, case set, or subject for the slot is rejected forever, including after semantic
invalidation or storage reclamation.

The private schema closes `$defs/slot_preparation_source`, `$defs/slot_preparation_registry_state` and
`$defs/slot_preparation_row`. The source contains exactly source/version/kind, registry/genesis and
the no-op guarded basis-global history head/generation, observed slot-preparation/allocation predecessor
identities, human predecessor identity, complete scope descriptor/hash, exact `scope_batch_id`, the
byte-identical selected `evaluation_scope_terminal_schedule_ref`, ordered
scope ordinal, lane/checkpoint, exact slot/candidate-cycle identity, preparation/batch/suite/case-set/
complete preclaim-basis identity, distinct private-control/private-history reservation-plan SHA-256
values and exact typed store/allocation identities, stable-principal attestation SHA-256 and the complete byte-
identical `irreversible_action_authority_binding`. It forbids row/root/count/proof/receipt, candidate or
resulting slot-preparation state/head/pointer/attestation, resulting human head, its own descriptor/hash
and every future reserve/claim/result. Its complete content-addressed descriptor is computed after the
source bytes; no descriptor field exists inside those bytes. State has exactly registry/genesis, sequence, occupied-row count and one
Sparse-Merkle Map v1 row root; it forbids its current/resulting receipt head. The row key is the
Canonical JSON v1 pair above and the immutable value is exactly the fields listed above plus row
version/source descriptor/length/SHA-256, never a root, resulting receipt/head or current-
pointer value. Insertion supplies the exact 256-sibling nonmembership proof, recomputes the occupied
leaf/new root/count, and later membership/rebase checks recompute the same row bytes. A receipt also
binds old/new row roots/counts and proof-bundle descriptor/hash.

The ordinal-ordered source list is a strict array of
`{scope_entry_ordinal, source_descriptor, source_length, source_sha256}` objects, where each descriptor
tuple exactly names the already serialized source record. Its root is exactly
`slot_preparation_source_list_sha256 = SHA256(b"FinProof/SlotPreparationSourceList/v1\x00" ||
canonical_bytes(exact_ordinal_ordered_source_tuple_array))`. Reordering, flattening, omitting length or
using a source's inner fields instead of its external descriptor tuple is invalid.

The closed private `$defs/slot_preparation_receipt` contains receipt version, registry ID/genesis,
contiguous sequence, prior head, history-registry/slot IDs, slot-preparation ID, reserve-batch and
suite ID/version, case-set commitment, subject SHA-256, principal/scope SHA-256 values, slot/scope/
approval/exposure proof commitments, the byte-identical selected
`evaluation_scope_terminal_schedule_ref`, the exact source descriptor, private human-governance registry ID/
genesis, exact expected predecessor head and the already computed candidate scope head, creation
clock/tick, old/new row roots/counts, proof-bundle descriptor/hash, and resulting head. The receipt
contains no duplicate authority binding; the validator resolves the source descriptor and requires its
complete embedded binding use action kind `scope_and_slot_prepare_commit`. The receipt projection
excludes only the resulting head; that head is
`SHA256(b"FinProof/SlotPreparation/v1\x00" || canonical_bytes(entry_projection))`. Both store
receipts carry the same slot-preparation receipt ID/SHA, preparation ID, and subject digest; the
unified storage HMAC streams/binds the complete receipt. The `scope_and_slot_prepare_commit`
transaction order is exact. After holding the clock/authority/global/human/slot/allocation predecessor
tuples, it builds the head-independent schedule bytes. Those bytes forbid their own descriptor/hash,
the scope descriptor/hash and every candidate/resulting human/slot/storage/future head. It then
content-addresses the schedule, builds and content-addresses the scope record containing that exact
schedule ref, and finalizes each complete
preclaim basis with that scope SHA; computes both reservation plans/hashes and obtains only the
provisional allocation IDs (not final store receipts); builds the combined basis, typed subject/state/
guard/binding and every ordered head-independent slot source; then builds the human transition from the old human head with the
schedule and scope descriptors in its ordered record list, the complete authority binding and the exact
`slot_preparation_source_list_sha256`,
never a slot row/root/receipt/head/pointer. That produces the candidate human scope head first. Starting
from the one observed slot-preparation root/state/receipt head, it processes scope ordinals in ascending
order: source `i`; nonmembership proof against root `i`; row `i`; root/count `i+1`; then receipt `i`
with contiguous sequence and prior receipt head. It next makes each store emit the final reservation
receipt bound to that slot receipt and computes the unified storage HMAC. A proof for every row against the same old root,
permuted/duplicate sources, a skipped receipt sequence, a store receipt emitted before its slot receipt,
or an HMAC computed before both store receipts is invalid. Only after the last receipt/store-HMAC set does it
derive one final candidate slot-preparation state/current-pointer attestation. One multi-store CAS
read-locks `expected_global_head == observed_global_head` unchanged, advances the exact predecessor
human head to the candidate scope head, the observed slot-preparation pointer to that final pointer,
and every provisional allocation to `prepared_scoped`. A concurrent global history successor,
exposure, slot insertion or allocation transition makes the whole transaction fail. The row's source
descriptor/hash authenticates the binding; omission or substitution changes the row root. Every later allocation/rebase/validation independently reads that current pointer and proves the
permanent row still equals this receipt. Phase 4 verifies both real store
transitions before allocation. Thus a publicly still-free slot cannot be used to curate a replacement
after its first private choice.

Rebase is permitted only if every overlap, derivation, disclosure-ancestor, slot, policy, and authority
admission fact remains true. If the intervening append creates an occupied uniqueness key or disclosed
ancestor, the store abort-tombstones/reclaims this prepared suite and stops; it may not substitute
another suite or batch. A continuity append that transfers custody or changes policy/authority after
slot preparation is a semantic conflict, not an ordinary refresh. The immutable row itself remains
permanently occupied as the slot's tombstone; the transaction changes only its paired prepared
allocations to `abort_tombstoned -> reclaimed` and permanently stops that slot without recustody or a
replacement subject. Such continuity is
performed before preparation when the slot is still intended for use.

Each manifest snapshot is at most 65,536 bytes and is rejected before parsing when larger. The
complete chain has at most 200,002 record descriptors, 10,004 binary-blob descriptors, and 210,014
snapshots; a snapshot delta has at most sixteen combined descriptors. One control record is at most
134,217,728 bytes and is validated one at a time. Candidate-response blobs total at most 67,108,864
bytes; original plus corrected public-report
outbox blobs total at most 33,554,432 bytes; the recovery ciphertext is exactly 48 bytes; and the one
truth-session ciphertext is at most 16,777,232 bytes. The reader hashes/counts each stream incrementally and
never materializes the full run. These caps and the reservation formula are schema/config invariants,
not caller declarations. Generated max-shaped original and corrected public-report witnesses exercise
every schema-maximal fixed K10/K5 disclosure field and must each fit 16,777,216 canonical bytes; a
schema/policy change that exceeds that cap invalidates the lock before claim rather than failing after
truth consumption.

The stage-edge graph is exactly `claimed -> candidate_sealed -> truth_committed -> terminalized ->
outcome_recorded -> report_candidate -> published -> corrected -> withdrawn`, with the alternative
`published -> withdrawn` edge and the terminal edge from any allowed pre-truth active stage to
`burned`. Same-stage snapshots are not stage re-entry: they form only the deterministic immutable
descriptor prefix for the current stage. A `published` or `corrected` same-stage successor may add
exactly the one corresponding verified-published-report receipt after the history/outbox closure; no
other transition may add that kind, and its absence means the outbox remains embargoed. In `claimed`, that prefix follows run/case-attempt ordinal
and transport order; in `truth_committed`, capability-terminal order; in `terminalized`, scoring-
ledger ordinal; and in later nonterminal stages, the closed report/adjudication construction order.
`burned` and `withdrawn` forbid another same-stage descriptor append. `corrected` permits only the
deterministic prefix for its at-most-one later withdrawal and otherwise is terminal. A compound
transition that needs more than sixteen new descriptors writes a
bounded sequence of intermediate snapshots and one final current pointer in the same all-or-none
transaction; the generated transaction-shape witness proves that every required atomic operation can
do so within the fixed cap.

The trusted private store, not the caller, supplies the current pointer. Crash recovery streams from
that exact pointer, resumes only the deterministic next descriptor/ordinal, and reuses a content hash
only for byte-identical idempotence. Candidate sealing, truth commit, outcome, report, correction, and
withdrawal bind the exact current snapshot head before advancing stages. Prior snapshots remain
immutable audit inputs. Snapshot bytes are prepaid in fixed slots and excluded from the snapshot's
private-control usage counters; those counters cover only control records and binary blobs.

The sole mutable ingress buffer for a run is a separately preallocated, signed no-reset resource. Its
genesis is
`SHA256(b"FinProof/CandidateIngressGenesis/v1\x00" || canonical_bytes({resource_id, store_id,
allocation_id, suite_id, run_attempt_id, version: "1"}))`. The claim transaction is the sole absent-to-
generation-zero creator and atomically creates it with the private-control generation-zero pointer,
empty `idle` state, zero counters/next ordinal, empty receipt accumulator, pinned store epoch/key and
complete initial attestation. A losing claim creates neither resource. The later run-binding HMAC binds
this complete resource/genesis/store/allocation/generation-zero state/attestation tuple alongside the
private-control generation-zero tuple before dispatch. Delayed creation, a second resource/genesis or
an ingress lineage not named by the run binding is invalid.

Its
strict `$defs/candidate_ingress_current_state` has exactly resource/genesis/store, suite/run and active-
allocation identities; zero-based state sequence; run accepted-byte count; next case-attempt ordinal;
and state `idle`, `receiving`, `pending_burn`, or `terminal_consumed`. `idle` requires no active attempt
and zero active counts; the common receipt accumulator below is the sole prior-terminal reference.
`receiving` requires the exact case/attempt/dispatch/local-or-transport invocation/token/fence
identities, staging-blob ID, next byte offset, active accepted-byte/chunk counts, and streaming prefix
SHA-256. `pending_burn` preserves all those fields plus exact reason
`candidate_response_run_budget_exceeded`, rejected-chunk length without bytes/hash, and token tombstone.
`terminal_consumed` binds the exact complete `candidate_ingress_terminal_payload_ref`. It also binds
the exact candidate-attempt or burn-snapshot source descriptor/
hash and private-control pointer generation/snapshot hash that consumed it. Required/forbidden/null
fields are branch-exact. A new attempt may
start only by the atomic `terminal_consumed -> idle -> receiving` transition whose first step preserves
the prior receipt and increments the next ordinal; no bytes or counters reset or disappear.

Every state branch also carries the immutable `terminal_receipt_chain_head` and
`terminal_receipt_count`; later attempts preserve them. At genesis the count is zero and the head is
exactly `SHA256(b"FinProof/CandidateIngressTerminalReceiptEmpty/v1\x00" || canonical_bytes({
chain_version: "1", ingress_resource_id, ingress_genesis_sha256, suite_id, run_attempt_id}))`; that
closed projection contains no head/digest. The strict
`$defs/candidate_ingress_current_attestation` contains that state's resource/genesis/store/
suite/run identities, CAS generation, state sequence and complete state SHA-256, store-monotonic epoch/
version, prior complete attestation SHA-256, literal `ED25519_STORE_ATTESTATION_V1`, pinned key resource/
key ID and canonical base64 64-byte signature. It signs exactly
`b"FinProof/CandidateIngressCurrent/v1\x00" || canonical_bytes(signed_projection)`; only the signature
is removed and the complete-object SHA-256 is external. `$defs/candidate_ingress_current_witness`
contains the independently read state/attestation bytes and one current-store receipt, plus a candidate
state/attestation only for a guarded transition. It also carries an ordered descriptor manifest for the
zero through 10,001 immutable terminal receipts whose final head/count must equal the current state.
`CandidateIngressCurrentResourceReader` reads by the pinned resource/genesis IDs, never by a historical
descriptor, and streams those receipt bytes by descriptor/hash. Before parsing, the state/attestation/
individual-receipt caps, 8,388,608-byte manifest cap, 16,777,216-byte complete-witness cap and
163,856,384-byte cumulative receipt-stream cap are enforced; a max-shaped 10,001-receipt fixture must
fit and one extra descriptor/byte fails.
`candidate_ingress_transition_errors` permits a null observed witness only for the claim transaction,
requires the independent reader to prove that exact pinned resource absent, and accepts only the
generation-zero empty state above. Every later call requires a non-null witness equal to the independent
current read and the exact contiguous prior-attestation/state successor.

The shared strict `$defs/candidate_ingress_terminal_payload_ref` is a two-branch `oneOf`.
`response_or_prefix_blob` requires positive accepted count plus exact blob ID/kind/length/SHA-256.
`zero_prefix_no_blob` requires count zero, the literal typed no-response marker and forbids every blob
field. Subject, candidate-attempt/burn source, terminal receipt and terminal state reproduce this exact
subobject byte-for-byte; a branch swap is invalid.

The strict predecessor-independent `$defs/candidate_ingress_terminal_subject` contains exactly its
version; ingress resource/genesis and suite/run/case/attempt identities; observed ingress state sequence,
complete-state and complete-attestation SHA-256 values; dispatch/token/fence and local-or-transport
invocation identities; terminal kind/reason/framing; accepted count/prefix SHA-256/staging ID; and the
same complete `candidate_ingress_terminal_payload_ref`. It forbids the candidate-attempt/burn record,
private-control resulting pointer, resulting ingress state/attestation, terminal receipt/head and its
own digest. Exactly one subject is descriptor-bound for every dispatched terminal attempt and counted
by the generated private-control reservation.

`$defs/candidate_ingress_terminal_receipt` is a private-control record with exactly receipt version,
prior terminal-receipt-chain head/count copied from the observed state, complete terminal-subject
descriptor/hash, candidate-attempt or burn source-record descriptor/hash, terminal kind, the same
complete terminal-payload ref, exact observed predecessor private-control pointer tuple/
attestation digest, and deterministic transaction-local intermediate snapshot sequence/hash after the
source record/blob but before this receipt. It expressly forbids an intermediate pointer/attestation,
the transaction's final private-control pointer, resulting ingress state/attestation, public/history
head and own resulting head. Its resulting chain head is
`SHA256(b"FinProof/CandidateIngressTerminalReceipt/v1\x00" || canonical_bytes(receipt_projection))`.
The same transaction's final private-control snapshot imports that receipt descriptor; the later
`terminal_consumed` state binds its descriptor/hash/resulting head/count plus that already fixed final
private-control pointer. A next-attempt state preserves the accumulator, so candidate-
set and burn validation can stream every historical terminal receipt rather than trusting only the
latest mutable fields.

Every accepted chunk atomically updates the staging bytes, state counters/prefix digest and signed
current attestation before acknowledgement. Terminal seal, per-attempt overflow, or run-budget burn
read-locks the independently obtained ingress current generation and private-control pointer. Its exact
acyclic order is: observed ingress state/attestation plus terminal subject and immutable blob; then the
candidate-attempt or burn control source/record, which binds only that observed ingress predecessor and
forbids every resulting pointer/ingress state; then a deterministic intermediate private-control
snapshot sequence/hash with no pointer write; then the terminal receipt binding the observed pointer
and that intermediate snapshot; then the final private-control snapshot and sole resulting pointer at
CAS generation `observed + 1` that imports the receipt; then `terminal_consumed` ingress state/attestation
last, which may bind only that already fixed final pointer and receipt/source/blob descriptors. One all-
or-none dual CAS exposes only the final pointers, persists the full suffix and tombstones the channel.
The immutable private-control record and ingress
terminal state thereby cross-bind the same predecessor/source/blob identities without a fixed point.
A supplied zero-buffer ancestor, conflicting stream, current-state omission, partial dual-resource
commit or pending-burn state without its sole legal burn successor is invalid. Post-terminal
sink records advance only private-history state and are supplied through the history reader; they
create no private-control descriptor or snapshot.

Later stages require all applicable predecessor descriptors/records; earlier stages forbid future
ones. `claimed` admits only the exact partial attempt graph reconstructed from the authoritative
snapshot chain and, if present, the separately authenticated current ingress buffer;
`candidate_sealed` and
every later result-bearing stage require complete eligible-count attempt coverage and recomputation of
the candidate-set message/event binding. `burned` requires the burn private-history append plus the
current retired-token/sink and applicable close/late-receipt evidence, forbids truth/session/outcome/
report records, and remains the stage after later sink checkpoints. If a dispatched burn follows any
durably accepted but unsealed bytes, `burned` also requires one `burn_response_buffer_snapshot` that
  binds attempt/dispatch/token/fence, terminal burn reason, pre-burn suite byte counter, exact accepted-
  prefix blob descriptor/length/SHA-256, rejected-chunk length without content/hash when applicable,
  the terminal tombstone, and the same complete `candidate_ingress_terminal_subject` descriptor/hash
  used by the terminal ingress receipt. Every dispatched deterministic-core burn private append binds the exact
  `$defs/local_invocation_receipt`; a run-budget burn requires
  `protocol_violation/RUN_RESPONSE_BUDGET_EXCEEDED` and forbids an adapter receipt or candidate-attempt
  seal. A positive-prefix snapshot repeats that receipt. A zero-byte burn forbids the snapshot/blob
  but still binds the receipt in the private append. `withdrawn` requires the exact
`post_adjudication(correction_expected=false)` event/private append and current target report. When it
targets the original revision it forbids corrected outcome/report/outbox records; when it targets the
one corrected revision it preserves the already durable corrected records and forbids only a new
correction or outbox. Open-regression validation forbids this bundle.

The schema is repository-visible because it contains contract shapes only. Instances containing
private history, truth, candidate bytes, scoring entries, or reports remain in the custodian store and
must never be committed. A commitment string without its schema-valid private projection cannot
satisfy a recomputation claim.

The bundle schema's named `$defs` are the single canonical definitions for every private control
record listed above. Runtime-attestation, lifecycle, suite-history, and report schemas use absolute
`$ref` fragments into those definitions whenever they carry the same object; they may not copy or
restate an inline variant. Contract tests enumerate those fields, require the exact absolute refs, and
reject inline duplicate definitions or a ref target whose resolved schema differs.

`tools/verify_handoff.py` must not import `jsonschema`, `referencing`, PyYAML, or another external
dependency because bootstrap verification runs with `python -S`. It performs a dependency-free
structural/reference audit. Contract tests prove that its stable policy decisions agree with the
full registry for every registered rejection class.

`evaluation_suite_manifest.schema.json` also exposes closed `$defs/open_evaluation_record_manifest`
and `$defs/open_evaluation_record_descriptor`. They are legal only for `open_regression` and contain
content-addressed descriptors for the exact repository-visible GoldenCase/evidence records and the
actual open-run execution/outcome records needed to recompute an `OPEN_FULL` report. One record is at
most 16,777,216 bytes; one manifest is at most 67,108,864 bytes and 50,000 descriptors; total streamed
record bytes are at most 1,073,741,824. Descriptors bind ordinal, kind, absolute schema `$ref`, byte
length, and SHA-256. The manifest's case IDs/count exactly equal the suite manifest, every case/truth/
evidence record resolves once, and no locked/sealed/private-history field is legal. Open validation
streams these public records and never trusts a self-consistent report as its own truth source.

## 5. Golden-case contract

### 5.1 GoldenCase root

`schemas/golden_case.schema.json` resolves absolute references to the canonical QueryPlan,
expected-result, and expected-answer schemas. A case requires:

- `schema_version`;
- `case_id`;
- `category`;
- `question`;
- `evaluation_lane`;
- `expected_plan`;
- `expected_result`;
- `expected_answer`;
- `review`; and
- `provenance`.

The current 13 seeds use `evaluation_lane: open_regression`. A repository-visible golden case may
not declare `locked_validation` or `sealed_holdout`.

`review` is a strict lane-discriminated `oneOf`. `open_regression` requires exactly the AI-scaffold
branch below. A private `locked_validation` or `sealed_holdout` case requires exactly
`review_status: human_reviewed_private`, pseudonymous `reviewer_role_id`, timezone-aware `reviewed_at`,
`source: official_snapshot_reference_derivation`, and `human_review_required: false`; it forbids
`reviewer_id: AI-handoff-seed`, migration source notes and every release-approval claim. This case-
local block is descriptive and creates no approval by itself: the later private human-governance
approval receipt must match its role/date/case digest under the guarded scope transaction.

`provenance` is the matching strict `oneOf`. The open branch is the migration block below. A private
locked/sealed case requires exactly `origin: official_snapshot_reference_derivation`, official snapshot
date `2026-07-11`, official dataset/source-locator identities, evidence-package descriptor plus complete
HMAC reference, one strict `reference_executor_manifest` descriptor/hash, and one strict
`reference_truth_derivation_receipt` descriptor/hash; it forbids every migration-only field.

The one suite-wide private validation-only `$defs/reference_executor_manifest` contains exactly manifest/executor/
protocol IDs and versions; literal policy `deterministic_non_generative_reference_v1`; content-addressed executable artifact, complete build-resource manifest,
dependency-lock and canonical execution-request schema descriptors/lengths/SHA-256; the official
snapshot/source-reader contract; the fixed output schema; the static no-network/isolation profile; an
ordered code/dependency/resource closure of at most 4,096 entries; and a governance-pinned forbidden production-
component-role policy plus finite allowlist of common read-only data/schema-decoding dependencies. It
contains no expected case values and no current or future candidate-build descriptor. At each suite
claim, after that suite's candidate build is immutable, a strict
`$defs/reference_executor_disjointness_receipt` of at most 4,194,304 canonical bytes binds this
manifest descriptor/hash, the deployment-pinned `evaluation_scorer_resource_manifest` descriptor/
hash, the exact candidate-build resource-manifest descriptor/hash, all three sorted closure-set hashes
and two mechanically derived empty forbidden-overlap sets: reference-executor versus candidate and
evaluation-scorer versus candidate. The only permitted intersections are the finite governance-locked
inert official-data, schema, serialization and decoding dependencies reproduced in the receipt;
candidate planner/compiler/executor/renderer/claim-verifier code is forbidden from both independent
closures. Before serializing that private receipt, the custodian creates one suite/candidate-cycle-
scoped `disjointness_receipt_public_handle` as exactly 32 uniformly random bytes encoded by 64
lowercase hex characters and stores it inside the receipt. The public fingerprint carries only that
fixed-length handle and expressly forbids the private receipt's record descriptor, kind, schema ref,
byte length, record ID and SHA-256. The same winning fingerprint/claim transaction's private
`history_transition_source` carries the complete receipt descriptor/hash plus that handle under the
existing `private_registry_commitment` and atomically inserts the handle's previously absent
`disjointness_public_handle` index value; validation resolves the receipt, nonmembership/membership
proofs and byte-compares all copies. Handle reuse across suites/candidate cycles, caller selection, substitution, omission or a
receipt descriptor/hash on any public artifact is invalid. Claim, run binding and later private
history bind the complete fingerprint SHA-256 rather than copying the receipt. An ordinal-1 child
computes the private receipt and a fresh handle only after its corrected build exists, without reopening its
pre-output truth. The receipt is a head-independent private-history record, not a bootstrap or private-
control record. Exactly one occurrence is reserved in the generated later-history allowance and the
winning reservation/fingerprint/claim CAS persists its descriptor/bytes and private-history append
before making the fingerprint/claim current; a crash leaves all or none. The Task-3 governance lock
freezes only the closed non-generative reference policy: permitted role/kind/media-type combinations
are deterministic query-AST interpreter, operator/calculation library, official-source reader, schema/
serialization validator or inert official data/config resource. It does not predict a Phase-4 code or
dependency hash. Before any truth creation, Phase 4 builds the complete concrete executor/closure,
validates every entry against that policy, and places the manifest descriptor/hash in the immutable
owner-pinned deployment trust-anchor manifest. Every non-open suite/witness must reproduce that one
deployment-pinned descriptor/hash. Model weights/checkpoints/adapters, tokenizer, prompt/template, generative
runtime, inference server/provider/client, decoding/sampling configuration, model credential and every
LLM or other generative artifact—including a local fixed-seed/offline bundle and HyperCLOVA X—are
forbidden. The complete build/dependency/resource closure must equal the concrete deployment-pinned
manifest and satisfy the Task-3 role policy; an unpinned manifest, novel role or executable hidden in
an allowed data role is invalid. `HistoryRecordReader` and
`ReferenceTruthArtifactReader` resolve that same descriptor/hash. Validation resolves the concrete
deployment-pinned scorer manifest, recomputes both closure comparisons and rejects any overlap outside
the allowlist; an intentionally shared component must be a named inert allowlist member and can never
perform planning, execution, rendering, scoring or claim verification. A caller boolean or a label
containing the word `independent` is not evidence of independence.

The private validation-only `$defs/reference_truth_derivation_receipt` contains exactly receipt/case/
suite versions and identities; the complete reference-executor-manifest descriptor/hash; official
snapshot/dataset/source-locator descriptors; the exact canonical reference-execution request/input
descriptor/length/SHA-256; the already-computed evidence-package descriptor and complete HMAC
reference; deterministic rule ID/version; content-addressed reference output descriptor/length/SHA-
256; canonical human-reviewed expected-plan hash; independently executed result/answer hashes;
and execution tick/controller role. It forbids a caller-supplied equality verdict, candidate/model
output, runtime report/result heads, manual replacement values, and every own/future digest.
The strict `$defs/reference_truth_execution_request` contains exactly request version, case/suite/
snapshot identities, the complete human-reviewed QueryPlan (or its exact content-addressed descriptor/
length/SHA-256), sorted official dataset/source-locator inputs and the deterministic reference rule/
output-schema IDs. It forbids expected result/answer bytes or hashes, equality fields, candidate output
and a free-form query/callable. The strict `$defs/reference_truth_execution_result` contains only the
derived canonical expected-result/answer objects, evidence/source reads and their hashes plus the exact
request/manifest digests; it contains no caller expected-value echo. This second mechanism independently
executes the supplied human-reviewed plan; it does not claim to derive Korean-language intent or the
plan itself.
`ReferenceTruthExecutor.execute(manifest, request_bytes, source_reader)` returns a strict
`ReferenceTruthExecutionResultModel` derived from the pinned official source bytes, not caller hashes.
The controller enforces the 60,000-ms per-case and 86,400,000-ms aggregate suite deadlines,
2,147,483,648-byte memory limit and 86,400,000 CPU-ms suite budget, cancels the subprocess/readers on
any limit, and returns a deterministic non-approval diagnostic; timeout/over-budget can never be treated
as a match.
`reference_truth_derivation_errors` length-checks and streams the receipt, manifest, request, source,
evidence and output records, invokes that executor, recomputes all descriptors/hashes/equalities, and
requires the case provenance and case-set entry/private fingerprint to bind the same receipt
descriptor/hash. The suite wrapper then proves membership in the witness and the separately supplied
human approval's binding to that witness. The evidence-package HMAC is necessarily its predecessor and forbids this
receipt. The unique construction order is evidence package/HMAC -> per-case reference execution and
derivation receipts -> case-set entries/index/HMAC -> complete suite-witness bytes/hash -> separate
human approval -> scope/registration. Phase 4 must implement and independently execute
this frozen interface before any non-open claim; Task 3 does not pretend schema linkage or a stored
`recomputed` hash alone proves truth.

The strict validation-only `$defs/reference_truth_suite_witness` contains suite/case-set identity,
the one suite-wide executor-manifest descriptor/hash, authored/excluded/eligible counts, and an
ordinal-ordered array of exactly one closed entry for every authored case-set-index entry (at most
10,000), including preapproved exclusions. Each entry contains the exact case-set-entry descriptor,
eligibility state/reason, GoldenCase, evidence-package, execution-request, execution-result,
and derivation-receipt descriptors/lengths/SHA-256 plus the complete evidence-package
HMAC reference and private case fingerprint. It reproduces the case-set index descriptor-list digest,
has its own descriptor-list digest and authenticated aggregate byte count, and reconciles all three
counts; omitting an excluded case is invalid. The reader prechecks count and cumulative bytes before
the first record read. Every non-open suite-history registration, control, publication and readiness
validation routes this witness through the same per-case validator; open branches require it and the
reference readers/executor null.
The witness expressly forbids the later human-approval descriptor/hash. Its complete hash is computed
first; the separate suite-level human approval then binds that witness descriptor/hash, and governance
validation supplies/resolves the approval independently. Neither object may contain the other's
resulting digest.
The complete witness is an immutable preclaim validation artifact, not caller-owned transient input.
It is written to the prepared private-history archive under its exact kind/schema/length/SHA-256
descriptor before the human approval and `reserve_batch`; the bootstrap descriptor manifest, suite-
archive receipt, human approval, suite manifest and later registration append all reproduce that same
descriptor. This one named artifact has the dedicated 268,435,456-byte cap below and is the sole
exception to the ordinary 16,777,216-byte private-history-record cap. It counts as one bootstrap
record and remains within the fixed 100,000-record/4,294,967,296-byte reservation.
`ReferenceTruthSuiteWitnessReader.read_witness(descriptor)` independently resolves those bounded
canonical bytes from the prepared/archive store. Every facade accepts both the parsed model and that
reader, byte-compares the resolved canonical object to the approval/suite-bound descriptor before
validation, and never treats a caller-only copy as durable evidence. A crash or loss of the caller
copy after claim cannot remove the archived witness.
The governance-lock generator constructs the exact 10,000-entry schema-max witness (including every
maximum descriptor/schema-ref/ID, HMAC reference and fingerprint), records its canonical byte length,
and rejects schema drift unless it remains at or below 268,435,456 bytes; adapters enforce that cap
before parse, and an otherwise valid one-byte-over witness is a required negative vector.

The migrated seed review block has exactly these fields:

- `review_status: ai_scaffold`;
- `reviewer_id: AI-handoff-seed`;
- `human_review_required: true`;
- the original review date and source note; and
- no human-reviewed, locked, sealed, benchmark-eligible, or release-approved claim.

The fields are `review_status`, `reviewer_id`, `reviewed_at`, `source`, and
`human_review_required`. The provenance block has `origin: visible_ai_handoff_seed`,
`original_line_sha256`, `migration_contract_version`, `migration_manifest_case_id`,
`preserved_fact_ids`, and `preserved_assertion_ids`. `original_line_sha256` is computed over the
original UTF-8 JSONL line without its line terminator. The migration-manifest reference makes every
legacy primitive leaf accountable under Section 5.5. The block does not recast an AI-authored
statement as independent truth.

### 5.2 Canonical expected plan

Every `expected_plan` resolves directly to `schemas/query_plan.schema.json`. All 12 canonical fields
are present, including empty collections and an empty clarification reason when applicable:

- `intent`;
- `product_types`;
- `entities`;
- `as_of_date`;
- `result_grain`;
- `filters`;
- `metrics`;
- `sort`;
- `top_k`;
- `top_k_scope`;
- `needs_clarification`; and
- `clarification_reason`.

The migration adds only canonical empty values that were implicit in the legacy seed. It does not
invent a filter, metric, sort, entity, or clarification. Removing `filters` from any migrated seed
must fail registry validation.

This supersedes the downstream Phase 3 wording that calls seed plans “partial semantic
expectations.” Provider output remains separate, but expected plans are full canonical semantic
contracts.

### 5.3 GoldenExpectedResult

Create `schemas/golden_expected_result.schema.json`. It requires:

- `result_kind`;
- `result_state`;
- `segments`;
- `products`;
- `rank_groups`;
- `integer_facts`;
- `decimal_facts`;
- `warning_codes`;
- `exclusion_counts`;
- `assertion_codes`; and
- one or more `evidence_requirements`.

`result_kind` is one of `lookup`, `screen`, `rank`, `compare`, `aggregate`,
`cross_product`, `clarification`, `unsupported`, or `quality`. `result_state` is one of
`expected_result`, `clarification_required`, `limitation_required`,
`blocked_official_semantics`, or `unsupported_scope`. Conditional schema rules reject
combinations that claim ranked products for clarification or unsupported outcomes. At the
GoldenCase layer, a human-reviewed rank case in `expected_result` state requires at least one
rank group; an AI scaffold may retain an empty group instead of fabricating IDs.

A typed product reference requires:

```text
product_type
native_grain
product_id
```

`fund_attribute` references additionally require `attribute_code`; other grains forbid it. The
schema and semantic contract reject incompatible product/grain pairs and duplicate product
references. `rank_groups` contain a positive integer competition rank and one or more typed product
references. More than one product in a group represents a tie. An empty product/rank collection is
valid for aggregate, clarification, distribution-only, unsupported, and current seed cases that do
not contain reviewed product IDs.

Allowed product/grain pairs are frozen: domestic bonds use `instrument`; domestic and overseas
ETF/ETN products use `listed_product`; public funds use `fund_item`, `fund_attribute`, or
`fund_family_candidate` only where the canonical plan allows that grain. `product` is a response
envelope, not a native product-reference grain.

An integer fact records `fact_id`, non-negative `value`, `unit_code`, result grain/scope, and
applicable as-of date. A decimal fact records the same identity/scope fields plus its exact-string
value and applicable currency and period. An exclusion count records segment ID, result grain,
reason code, non-negative count, and governing policy reference. Segment expectations record
segment ID, product type, native grain, compatibility partition, and top-k scope.

Integer counts remain non-negative JSON integers. Decimal financial values are JSON strings that
match:

```regex
^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$
```

Exponent notation, leading plus signs, leading zeroes, `.5`, `5.`, `NaN`, and infinity are
invalid. Trailing zeroes are preserved. A decimal fact also records its unit and applicable period,
currency, and as-of date when those dimensions apply.

Codes match `^[A-Z][A-Z0-9_]{2,63}$` and are not free-form Korean prose. Each evidence requirement
has an ID, a kind, and target fact/claim IDs. Initial evidence kinds are:

- `source_cell`;
- `aggregate_evidence`;
- `policy_rule`;
- `execution_trace`; and
- `calculation_inputs`.

Financial warning, assertion, and limitation vocabularies are not invented in preflight. The
schemas accept versioned non-empty stable codes; the relevant domain phase must register their
meaning before release.

Migration-only codes are mechanically scoped to the case and legacy assertion position; they do
not claim to be reusable financial-policy vocabulary.

### 5.4 GoldenExpectedAnswer

Create `schemas/golden_expected_answer.schema.json`. It requires structured `required_claims` and
`forbidden_claims`. A required claim records:

- `claim_id`;
- `claim_type`;
- stable `claim_code`;
- referenced fact IDs; and
- referenced evidence-requirement IDs.

The shared `claim_type` enum is exactly `identity`, `numeric`, `count`, `comparison`, `rank`,
`exclusion`, `calculation`, `warning`, `limitation`, `clarification`, or `date_assumption` and is
defined once in `evaluation_common.schema.json`. There is no separate `policy` or `data_date` claim
type. A forbidden claim records `claim_code`, `reason_code`, and any related fact IDs. No Korean
sentence, tone, or copy style is part of factual truth. Renderer style is evaluated separately in
its later phase.

Create `tools/evaluation_models.py` with frozen Pydantic v2 boundary models and
`tools/evaluation_contracts.py` with:

```python
golden_case_policy_errors(case: GoldenCaseModel) -> tuple[EvaluationDiagnostic, ...]
aggregate_evidence_policy_errors(evidence: AggregateEvidenceModel) -> tuple[EvaluationDiagnostic, ...]
evidence_package_policy_errors(package: EvidencePackageModel) -> tuple[EvaluationDiagnostic, ...]
```

JSON Schema owns portable shape. These pure functions own cross-reference and sequence invariants:
unique IDs, fact/claim/evidence target resolution, product/grain pairing, human-reviewed rank
non-emptiness, stage-count relations, result-commitment exclusivity, and source-evidence coverage.
Every model uses `ConfigDict(frozen=True, extra="forbid", strict=True)`, maps one exact canonical
schema root or named `$def`, and round-trips through `model_dump(mode="json")` back to that schema
without widening or coercing types. Container fields use tuples and an immutable typed `FrozenMap`,
never mutable lists/dicts; the validated JSON value is recursively deep-frozen before any hash/HMAC or
cross-module handoff. The generic unique-key loader rejects malformed UTF-8, duplicate members,
non-finite constants, and trailing data but may accept finite floats, surrogate-bearing strings, and
insignificant JSON whitespace. The canonical-domain overlay separately rejects unsupported runtime/
parsed values and returns an immutable `CanonicalJsonValue`. Hash/HMAC-bound content-addressed records and outbox
bytes additionally require exact Canonical JSON v1 byte equality before model construction.
External I/O adapters may accept bytes; no public or cross-module domain function accepts or returns a
raw `dict`, `object`, or `list[dict]`.
`aggregate_evidence_policy_errors` checks invariants internal to one aggregate object.
`evidence_package_policy_errors` receives the typed package containing material claims, aggregate
objects, and schema-valid source `EvidenceRecord` objects; it resolves every forward and reverse
reference and proves that aggregate evidence is never the sole evidence for a material
source-derived claim. The functions return sorted structured diagnostics and perform no I/O.

Stable diagnostic IDs begin with `EVC001_UNRESOLVED_REFERENCE`,
`EVC002_DUPLICATE_IDENTIFIER`, `EVC003_PRODUCT_GRAIN_MISMATCH`,
`EVC004_HUMAN_RANK_EMPTY`, `EVC005_STAGE_COUNT_INVALID`,
`EVC006_RESULT_COMMITMENT_AMBIGUOUS`, and `EVC007_SOURCE_EVIDENCE_MISSING`.

### 5.5 Seed migration

Migrate all 13 lines of `tests/golden/seed_cases.jsonl` in place:

- add all missing canonical QueryPlan fields with meaning-preserving empty values;
- convert existing counts to typed integer facts;
- convert existing decimal metric values such as recorded zeroes to exact decimal strings;
- convert legacy assertions and required/forbidden semantics to stable codes and structured claims;
- create evidence requirements that describe what later proof must support;
- preserve every existing source count and explicit policy meaning;
- preserve `AI-handoff-seed` and the human-review warning; and
- do not add product IDs, ranks, source cells, answer facts, or human approvals that are absent
  today.

The `risk_grade` seed preserves its known source/fund-item observations but declares
`blocked_official_semantics`. Migration must not imply that the dangling planner alias is a
supported cross-product concept.

Before changing a seed byte, create
`tests/golden/legacy_seed_migration_manifest.json` from the exact LF-normalized Git blob at frozen
base commit `2cdf70bbeb55ee7b7175ca48fe9637c027d7e61f`, then commit it as an independently reviewable
checkpoint. Ambient checkout bytes are not an authority because Git-for-Windows EOL conversion may
produce CRLF. The authoritative base blob has 12,221 bytes, 13 LF bytes, zero CR bytes, and SHA-256
`afbc2f3148a3a9508a4eff4e3f87d1594a06b6e539f79ef1d4caa6dc863c61c3`. The manifest contains a
`legacy_inventory` object with exact root keys `schema_version: "1.0.0"`,
`source_path: "tests/golden/seed_cases.jsonl"`, `source_file_sha256`, and `cases`. The 13
line-ordered case objects have exact keys `case_id`,
`line_number`, `original_line_sha256`, and `leaves`. Each leaf object has exact keys
`json_pointer` and `canonical_value_sha256`. It inventories every primitive JSON leaf as an RFC
6901 pointer plus the Canonical JSON v1 SHA-256 of its value. Object keys traverse in
Unicode-code-point order, arrays in index order, and only the legacy null, boolean, integer, and
string leaves are permitted.

That exact inventory has 13 cases and 302 primitive leaves. Its Canonical JSON v1 SHA-256 is
`ab4902c3aa6824450a3ecd4206326a0cdad9800c8eee067da97cefcbd9e51e21`. A dependency-free
`tools/build_seed_migration_manifest.py` exposes a pure bytes-to-inventory function; its CLI reads
the exact base blob through Git, refuses any other blob/hash/EOL form, generates the frozen
inventory before migration, and later checks rather than regenerates it. The migrated JSONL is
written and committed with LF under `.gitattributes`.

The complete manifest root has exactly `schema_version`, `legacy_inventory`,
`legacy_inventory_sha256`, `transformation_registry_version`,
`transformation_registry_sha256`, `structural_default_registry_version`,
`structural_default_registry_sha256`, `mappings`, `migrated_semantic_inventory`,
`migrated_semantic_inventory_sha256`, and `migration_semantics_review`. It contains exactly
one migration mapping for each inventory tuple
`(case_id, legacy_json_pointer, canonical_value_sha256)`. The manifest freezes
`transformation_registry_version: "1.0.0"` and the canonical hash of a closed registry containing
only `COPY_EXACT_V1`, `MOVE_EXACT_V1`, `INTEGER_TO_EXACT_DECIMAL_V1`,
`WRAP_INTEGER_FACT_V1`, `WRAP_REQUIRED_CLAIM_V1`, `WRAP_FORBIDDEN_CLAIM_V1`,
`WRAP_ASSERTION_V1`, and `MOVE_REVIEW_METADATA_V1`. Each code has a closed parameter schema and a
deterministic verifier implementation in the migration tool; unknown codes/parameters fail closed.

Every mapping object has exactly `case_id`, `legacy_json_pointer`,
`canonical_value_sha256`, `transform_code`, `target_pointers`, `target_ids`,
`legacy_text_sha256`, and `parameters`.
Copy, move, decimal, and review-metadata codes require `parameters: {}` and exactly one target
pointer. `WRAP_INTEGER_FACT_V1` parameters have exactly `unit_code`, `scope_code`, and
`as_of_date`; claim/assertion wrap parameters have exactly `claim_type` and optional
`reason_code`, with optionality fixed by the selected code. Target IDs are non-empty only for wrap
codes and must equal the derived migration ID below. No per-mapping unknown property is permitted.

Exact copy/move requires one target with the same canonical value hash. Integer-to-decimal accepts
only a legacy integer and recomputes the non-exponent exact-decimal target string. Integer-fact
wrapping recomputes the target `value`, unit/scope requirements, and a migration ID derived as
`MIG_` plus the first 16 uppercase hexadecimal characters of SHA-256 over UTF-8
`case_id + "\x00" + legacy_json_pointer + "\x00" + canonical_value_sha256`. Claim/assertion
wrapping uses the same ID rule, requires the mapping's `legacy_text_sha256` to be a lowercase
digest, and recomputes that hash from the legacy string. Other codes require that field to be null.
Review-metadata movement requires exact value equality. No code can drop a leaf or create a human
approval, locked/sealed status, product ID, rank, source cell, or answer fact absent from the legacy
line.

After migration, the tool builds `migrated_semantic_inventory` from every terminal semantic node
under each case's `question`, `expected_plan`, `expected_result`, `expected_answer`, and evaluation-
provenance roots. A terminal node is a primitive JSON leaf or an empty array/object; its record has
exactly case ID, RFC 6901 pointer, node kind, and Canonical JSON v1 subtree SHA-256. This catches extra
filters, sorts, facts, claims, empty semantic containers, and other invented values without treating
nonempty parent containers as independent facts. The manifest freezes a closed
`structural_default_registry` version/hash whose only outputs are explicitly enumerated schema-
required boilerplate constants or empty containers that carry no financial/question meaning.

Every migrated semantic-inventory tuple must be produced exactly once by either one closed transform's
resolved target output or one exact structural-default output, and every transform/default output must
resolve to exactly one inventory tuple. No glob, prefix, parent-container, or catch-all rule is legal.
The tool rejects an unaccounted migrated node, an output with no node, two producers for one node, or a
default outside the frozen allowlist. This is a bijection over the migrated terminal semantic
inventory, not merely a one-way check of the 302 legacy leaves.

The deterministic registry proves value/accountability transformations, but it cannot prove that a
new structured claim type faithfully expresses Korean legacy prose. Every non-exact semantic wrap
therefore requires a separate `migration_semantics_review`. That strict review object has exactly
`reviewer_role_id`, `reviewed_at`, `disposition: "faithful_migration_only"`, and
`reviewed_migration_projection_sha256`. The reviewed projection is an exact root object containing
only `schema_version`, `legacy_inventory`, `legacy_inventory_sha256`,
`transformation_registry_version`, `transformation_registry_sha256`,
`structural_default_registry_version`, `structural_default_registry_sha256`, `mappings`,
`migrated_semantic_inventory`, and `migrated_semantic_inventory_sha256`; it is the
complete manifest with the root `migration_semantics_review` member omitted. Canonical JSON v1 and
SHA-256 over that projection produce `reviewed_migration_projection_sha256`. No nested field is
otherwise removed, and the review object and its digest are never included in the projection. This
acyclic digest is computed only after all mappings are complete. The four review fields are
digest-bound review metadata, not authentication of the reviewer, their independence or real-world
approval. Task 3 therefore requires a separately observed manual acceptance item from the designated
independent reviewer that names this exact digest; it records that evidence in the handoff/status but
does not claim the JSON fields cryptographically prove it.

That review attests only that no legacy meaning was invented, dropped, or reversed; it does not
approve the underlying seed as truth, change `ai_scaffold`, or remove `human_review_required`.

Contract tests and the independent verifier compare the committed inventory projection with the
frozen hash, require all 302 tuples exactly once, resolve every target against the migrated cases,
recompute every closed transformation, and reject a missing, duplicate, hash-changed, unresolved,
unknown-code, non-recomputable, or forbidden mapping. It independently regenerates the inventory
from the base Git blob and recomputes the exact review projection and digest-bound metadata. Actual
independent-human approval is a separately evidenced manual acceptance gate for non-exact semantic
wraps, not an output of this verifier. It also regenerates the migrated semantic
inventory, verifies its hash and exact transform/default bijection, and rejects an extra/unaccounted
filter, sort, fact, claim, assertion, or empty semantic node. Mutation tests change every included root
member in turn and prove the digest changes; they also prove that adding the completed review object
does not alter the reviewed projection while omitting or broadening the stated exclusion fails.
Acceptance claims complete leaf accountability plus a separately observed independent-review gate,
not machine-authenticated reviewer identity, automatic semantic proof or human-reviewed evaluation
truth.

## 6. AggregateEvidence contract

Add the canonical absolute `$id` above to `schemas/evidence_record.schema.json`, then create
`schemas/aggregate_evidence.schema.json`. Aggregate evidence complements source-cell
`EvidenceRecord` objects; it never replaces them. Task 3 may add that `$id` and register the schema,
but may not otherwise change the existing EvidenceRecord fields or semantics.

Required root fields are:

- `schema_version`;
- `aggregate_evidence_id`;
- `claim_ids`;
- `source_manifest_sha256`;
- `artifact_manifest_sha256`;
- `execution_plan_sha256`;
- `segment`;
- `compatibility_partition`;
- ordered `predicate_refs`;
- ordered `policy_refs`;
- ordered `candidate_stages`;
- `result_commitment`;
- `rank_policy`;
- `calculation_inputs`;
- `exclusion_reason_counts`;
- `source_evidence_ids`; and
- `logical_proof_sha256`.

All SHA-256 values are lowercase 64-character hexadecimal strings. The segment records its ID,
product type, native grain, and top-k scope. Predicate and policy references include stable IDs and
versions or hashes.

Candidate stages use unique stage IDs and non-negative counts in execution order. Each stage
declares `cardinality_relation: non_increasing` or `expansion_authorized`. An expansion requires a
non-empty `expansion_policy_id` and source-evidence references; other stages forbid that field.
Counts for a single filtered/grouped segment must otherwise be non-increasing. Silent count
expansion is invalid.

`result_commitment` contains exactly one of:

- ordered typed product references; or
- a canonical result-content SHA-256 plus canonicalization version.

Calculations record formula/policy ID, exact-string inputs, unit, applicable currency, period,
as-of date, and source-evidence references. Exclusions record stage, stable reason code, count, and
governing policy. Every material aggregate claim references source evidence.

The logical-proof projection is exact: make a deep copy of the schema-valid aggregate object,
remove the root `logical_proof_sha256` member, serialize the remaining object with Canonical JSON
v1, and SHA-256 those bytes. The aggregate schema permits no operational timestamp, run-local ID,
producer metadata, or attestation field, so there is no additional implicit exclusion. The stored
`logical_proof_sha256` must equal that lowercase digest.

Reject at minimum:

- a missing or malformed source, artifact, plan, or logical-proof hash;
- negative counts;
- duplicate stage, product, claim, or evidence IDs;
- a JSON number in an exact-decimal field;
- both or neither result-reference alternatives;
- an ambiguous or duplicate rank/tie assignment;
- a calculation missing a required dimension or source reference;
- an exclusion without a policy/reason reference; and
- an aggregate whose stored logical-proof hash differs from its exact projection.

Create `schemas/evidence_package.schema.json` for external linkage. Its strict root contains
`schema_version`, `material_claims`, `source_evidence_records`, and
`aggregate_evidence_records`. A material-claim entry has `claim_id`, `claim_type`,
`claim_basis`, `source_evidence_ids`, `aggregate_evidence_ids`, and an optional
`governing_policy_ref`. The two evidence arrays use absolute references to the canonical
`EvidenceRecord` and `AggregateEvidence` schemas.

After schema validation, `evidence_package_policy_errors` indexes all three arrays and rejects an
unresolved or duplicate claim/evidence ID, a forward/reverse reference mismatch, an aggregate
claim not listed by its aggregate object, a source evidence record whose `claim_id` does not match,
or a material source-derived claim with no resolved source-cell `EvidenceRecord`. A claim that uses
aggregate evidence must resolve at least one aggregate and at least one source-cell record; the
package therefore proves that aggregate evidence is not the sole evidence rather than merely
checking non-empty ID strings. RED cases remove referenced claim and EvidenceRecord objects and
mutate both directions independently. `claim_basis` is exactly `source_data` or `policy_only`.
Identity, numeric, count, comparison, rank, exclusion, calculation, and `date_assumption` require
`source_data`. Warning and limitation may use either basis. Clarification may use `policy_only` or
`source_data`; `policy_only` is valid only for warning, limitation, or clarification, requires a
resolved governing-policy reference, and forbids source/aggregate evidence IDs. Every
`source_data` claim requires resolved source evidence, so callers cannot escape grounding with a
boolean toggle.

## 7. Complete 207-column coverage

### 7.1 Two-layer model

`config/question_coverage.yaml` separates physical column disposition from question capability.

`column_classifications` contains exactly one explicit record for every official
`(table_id, column_name)` pair:

| Table | Required columns |
|---|---:|
| `PRBD01N001` | 40 |
| `PREF01N001` | 73 |
| `PREF02N001` | 49 |
| `PRFD01N001` | 45 |
| **Total** | **207** |

Each record has the exact table and case-sensitive column name, one approved status, a stable
reason code, and zero or more concept references. Lists, rather than nested maps, preserve the
ability to diagnose duplicate pairs.

`concepts` are product-scoped and record:

- canonical concept ID;
- applicable product types;
- status and reason/limitation codes;
- field/metric/planner registry references;
- authorized source mappings, or separately labeled candidate mappings;
- definition and unit when applicable;
- missing and zero semantics;
- filtering, ordering, ranking, aggregation, and tie semantics when applicable; and
- evidence rule.

Coverage configuration is an audit/control artifact. It does not silently become a production
field or metric registry. A concept can be `supported` only by referencing an authorized existing
registry contract. Candidate mappings remain blocked until the owning domain phase updates its
runtime registry and tests.

### 7.2 Status semantics

The only statuses are:

- `supported` — an authorized mapping and every applicable semantic/evidence contract are
  complete;
- `intentionally_unsupported` — deliberately outside the approved product scope, with a stable
  reason and limitation;
- `blocked_official_semantics` — a source candidate exists but one or more material semantics or
  policies are unresolved; and
- `source_unavailable` — no official source exists for that product-scoped concept.

`source_unavailable` is valid only for a product-scoped concept with no official source mapping.
It is invalid for `column_classifications`, because every classified pair is an existing official
column. Blank samples or current values do not prove unavailability. Availability is not inferred
from examples, sample workbooks, names, prefixes, or `axis_*` fields.

`intentionally_unsupported` requires a citation to a frozen scope or contract that deliberately
excludes the capability. An unregistered, unclear, or merely inconvenient column is classified
`blocked_official_semantics`, not silently excluded. There is no fallback/default classification;
all 207 decisions are explicit.

### 7.3 Required explicit concepts and aliases

Every current planner alias target maps to exactly one typed target: product aliases map to a
registered product type, field aliases to a product-scoped coverage concept, period aliases to a
canonical period token, and ranking aliases to a sort direction. Every registered field and metric
is represented or explicitly dispositioned. Reverse reachability gaps remain visible diagnostics
even when they do not make the configuration structurally invalid.

The report explicitly includes:

- manager;
- base index;
- strategy;
- replication method;
- coupon rate;
- duration;
- evaluation price; and
- risk grade.

`risk_grade` remains `blocked_official_semantics` until the repository has an authorized,
product-scoped definition, source mapping, missing/null policy, ordering or explicit
non-orderability rule, and evidence rule. Domestic listed-product and public-fund risk columns are
candidate mappings, not proof of cross-source equivalence. Bond `PD_RISK_GCD` is not silently
merged with either.

Likewise, Task 3 does not choose `DUR` over `NDY_DUR`, `EVAL_PRICE` over `NDY_EVAL_PRICE`, or an
unverified meaning/unit for `SRFC_IRT`. These remain blocked until the domain contract authorizes
the distinction.

### 7.4 Deterministic report

`tools/build_coverage_report.py` exposes:

```python
build_coverage_report(
    catalog: DatasetCatalogModel,
    coverage: QuestionCoverageBundleModel,
) -> QuestionCoverageReportModel
```

The second argument is an explicit parsed bundle with exactly `question_coverage`,
`field_registry`, `metric_registry`, and `planner_catalog` typed objects. The CLI assembles and
strictly validates the immutable bundle
from repository files; the pure function never reads them implicitly. The function has no
filesystem, environment, clock, network, or locale dependency. Its canonical result contains:

- catalog and coverage contract versions/fingerprints;
- all 207 sorted column records;
- sorted product-scoped concept records;
- typed planner-alias bindings;
- status totals by table and concept scope;
- named gaps;
- sorted structured diagnostics;
- `structurally_valid`; and
- `all_supported`.

`structurally_valid` means the inventory is exact and internally consistent. It does not mean all
concepts are supported. Reordering YAML input cannot change the report. Changing samples,
examples, or `axis_*` hints cannot change classifications. Adding, removing, duplicating,
case-folding, or implicitly absorbing a catalog pair fails closed.

Commit the canonical result as `config/question_coverage.lock.json`. It includes SHA-256 values for
the exact question-coverage, field-registry, metric-registry, and planner-catalog YAML bytes; the
catalog fingerprint; the 207-pair inventory; and the canonical report hash. The builder's CLI
computes that hash over the Canonical JSON v1 projection with only root
`canonical_report_sha256` removed, then stores the resulting lowercase digest. The builder's CLI
provides `--check` and fails when regenerated JSON differs from the committed lock. The expected
Task 3 state is `structurally_valid: true` and `all_supported: false`; unresolved capabilities
remain visible rather than making a false completeness claim.

Stable diagnostic IDs begin with:

- `COV001_DUPLICATE_CATALOG_PAIR`;
- `COV002_DUPLICATE_COVERAGE_PAIR`;
- `COV003_MISSING_COVERAGE_PAIR`;
- `COV004_EXTRA_COVERAGE_PAIR`;
- `COV005_INVALID_STATUS`;
- `COV006_MISSING_REASON`;
- `COV007_UNKNOWN_CONCEPT_REF`;
- `COV008_UNKNOWN_SOURCE_PAIR`;
- `COV009_ALIAS_TARGET_UNBOUND`;
- `COV010_SUPPORTED_CONTRACT_INCOMPLETE`;
- `COV011_REVERSE_MAPPING_MISMATCH`; and
- `COV012_CATALOG_BINDING_MISMATCH`.

Diagnostics sort by code, concept ID, table ID, column name, and config path. Tests assert codes and
paths rather than mutable explanatory prose.

## 8. Evaluation governance contracts

These are machine-validatable repository interfaces, not an operational security boundary by
themselves. Task 3 can reject malformed public artifacts and inconsistent commitments. Only the
Phase 4 custodian environment can enforce private-store ACLs, atomic writes, HMAC verification,
blindness, and out-of-band non-disclosure.

### 8.1 Versioned policy

Create `config/evaluation_governance.yaml`. It freezes:

- policy version;
- lane and state identifiers;
- `independence_model: single_human_combined` and its implementer-blindness/mechanical-second-check
  invariants;
- a private, externally attested stable-human-principal curation-scope/output-exposure ledger whose
  public projection uses only pseudonymous role IDs;
- allowed transitions;
- named checkpoint identifiers;
- truth-release and consumption semantics;
- fingerprint component names;
- canonicalization version;
- a closed HMAC-domain registry containing exactly `evidence-package`, `case-set`, `suite-history`,
  `history-attestation`, `organizer-cycle-authorization`, `owner-remediation-authorization`,
  `disposition-policy`, `exclusion`,
  `evaluation-storage-reservation`,
  `case-attempt-binding`, `case-dispatch-receipt`, `candidate-attempt`, `candidate-attempt-set`,
  `runtime-observation`, `infrastructure`, `attempt-transport-close`, `late-output-receipt`, `output-sink-ledger`,
  `retired-token-ledger`, `suite`, `run-binding`, `recovery-record`,
  `truth-capability-terminal-receipt`, `outcome-set`, `corrected-outcome-set`, `private-report`, and
  `report-attestation`, with no missing/extra domain or cross-domain key-ID reuse;
- one exact generated 27-row HMAC registry. Each row is
  `(domain, owning_field, projection_id, projection_version, formula_key_slot, literal_tag,
  key_controller, deployment_key_role)` and is frozen as follows:

  | domain | owning field | projection ID | key slot | literal tag | controller / deployment role |
  |---|---|---|---|---|---|
  | `evidence-package` | `evidence_package_commitment` | `evidence_package_projection` | `K_evidence_package` | `FinProof/EvidencePackage/v1\x00` | custodian / `hmac:evidence-package` |
  | `case-set` | `case_set_commitment` | `case_set_index_projection` | `K_case_set` | `FinProof/CaseSet/v1\x00` | custodian / `hmac:case-set` |
  | `suite-history` | `private_registry_commitment` | `history_projection` | `K_history` | `FinProof/SuiteHistory/v1\x00` | custodian / `hmac:suite-history` |
  | `history-attestation` | `history_attestation` | `public_history_projection` | `K_history_attestation` | `FinProof/SuiteHistoryAttestation/v1\x00` | custodian / `hmac:history-attestation` |
  | `organizer-cycle-authorization` | `organizer_cycle_authorization_commitment` | `organizer_cycle_authorization_projection` | `K_owner_cycle_authorization` | `FinProof/OrganizerCycleAuthorization/v1\x00` | repository owner / `hmac:organizer-cycle-authorization` |
  | `owner-remediation-authorization` | `owner_remediation_authorization_commitment` | `owner_remediation_authorization_projection` | `K_owner_remediation_authorization` | `FinProof/OwnerRemediationAuthorization/v1\x00` | owner blind signer / `hmac:owner-remediation-authorization` |
  | `disposition-policy` | `disposition_policy_commitment` | `disposition_policy_projection` | `K_disposition_policy` | `FinProof/EvaluationDispositionPolicy/v1\x00` | custodian / `hmac:disposition-policy` |
  | `exclusion` | `exclusion_commitment` | `exclusion_projection` | `K_exclusion` | `FinProof/ExclusionSet/v1\x00` | custodian / `hmac:exclusion` |
  | `evaluation-storage-reservation` | `evaluation_storage_reservation_commitment` | `evaluation_storage_reservation_projection` | `K_evaluation_storage_reservation` | `FinProof/EvaluationStorageReservation/v1\x00` | custodian / `hmac:evaluation-storage-reservation` |
  | `case-attempt-binding` | `case_attempt_binding_commitment` | `case_attempt_binding_projection` | `K_case_attempt_binding` | `FinProof/CaseAttemptBinding/v1\x00` | custodian / `hmac:case-attempt-binding` |
  | `case-dispatch-receipt` | `case_dispatch_receipt_commitment` | `case_dispatch_projection` | `K_case_dispatch` | `FinProof/CaseDispatchReceipt/v1\x00` | custodian / `hmac:case-dispatch-receipt` |
  | `candidate-attempt` | `candidate_attempt_commitment` | `candidate_attempt_projection` | `K_candidate_attempt` | `FinProof/CandidateAttempt/v1\x00` | custodian / `hmac:candidate-attempt` |
  | `candidate-attempt-set` | `candidate_attempt_set_commitment` | `candidate_attempt_set_projection` | `K_candidate_attempt_set` | `FinProof/CandidateAttemptSet/v1\x00` | custodian / `hmac:candidate-attempt-set` |
  | `runtime-observation` | `runtime_observation_attestation_commitment` | `runtime_observation_projection` | `K_runtime_observation` | `FinProof/RuntimeObservation/v1\x00` | trusted deployment/egress controller / `hmac:runtime-observation` |
  | `infrastructure` | `infrastructure_attestation` | `infrastructure_projection` | `K_infrastructure` | `FinProof/InfrastructureFailure/v1\x00` | custodian / `hmac:infrastructure` |
  | `attempt-transport-close` | `attempt_transport_close_commitment` | `attempt_transport_close_projection` | `K_attempt_transport_close` | `FinProof/AttemptTransportClose/v1\x00` | custodian / `hmac:attempt-transport-close` |
  | `late-output-receipt` | `late_output_receipt_commitment` | `late_output_projection` | `K_late_output` | `FinProof/LateOutputReceipt/v1\x00` | custodian / `hmac:late-output-receipt` |
  | `output-sink-ledger` | `output_sink_ledger_head_commitment` | `output_sink_ledger_step_projection` | `K_output_sink_ledger` | `FinProof/OutputSinkLedger/v1\x00` | custodian / `hmac:output-sink-ledger` |
  | `retired-token-ledger` | `retired_token_fence_ledger_commitment` | `retired_token_fence_ledger_projection` | `K_retired_token_ledger` | `FinProof/RetiredTokenFenceLedger/v1\x00` | custodian / `hmac:retired-token-ledger` |
  | `suite` | `suite_commitment` | `suite_projection` | `K_suite` | `FinProof/Suite/v1\x00` | custodian / `hmac:suite` |
  | `run-binding` | `run_binding_attestation` | `run_projection` | `K_run` | `FinProof/RunBinding/v1\x00` | custodian / `hmac:run-binding` |
  | `recovery-record` | `truth_release_fence_recovery_record_commitment` | `recovery_record_projection` | `K_recovery_record` | `FinProof/TruthReleaseFenceRecoveryRecord/v1\x00` | custodian / `hmac:recovery-record` |
  | `truth-capability-terminal-receipt` | `truth_capability_terminal_receipt_commitment` | `truth_capability_terminal_projection` | `K_truth_capability_terminal` | `FinProof/TruthCapabilityTerminalReceipt/v1\x00` | custodian / `hmac:truth-capability-terminal-receipt` |
  | `outcome-set` | `outcome_set_commitment` | `outcome_set_projection` | `K_outcome_set` | `FinProof/OutcomeSet/v1\x00` | custodian / `hmac:outcome-set` |
  | `corrected-outcome-set` | `corrected_outcome_set_commitment` | `corrected_outcome_set_projection` | `K_corrected_outcome_set` | `FinProof/CorrectedOutcomeSet/v1\x00` | custodian / `hmac:corrected-outcome-set` |
  | `private-report` | `private_report_commitment` | `private_report` | `K_private_report` | `FinProof/PrivateEvaluationReport/v1\x00` | custodian / `hmac:private-report` |
  | `report-attestation` | `report_attestation` | `canonical_report_sha256_bytes` | `K_report` | `FinProof/EvaluationReport/v1\x00` | custodian / `hmac:report-attestation` |

  Every row has projection version `1`. The generated lock and validator compare this table
  bidirectionally with the 27 formulas and acceptance list, require unique domain/key slot/literal tag/
  deployment role, and resolve the actual opaque key resource only through the immutable deployment
  trust-anchor manifest;
- a closed AEAD key-purpose registry with exactly `recovery_record_aead` and
  `truth_session_aead`; Task 3 freezes AES-256-GCM, purpose/separation/rotation and atomic global nonce-
  claim rules only. The Phase-4 deployment trust-anchor manifest supplies the real opaque key IDs and
  immutable KMS key-resource attestations, distinct from each other and every HMAC/asymmetric resource;
- one exact closed 13-row asymmetric store-attestation registry, explicitly outside the 27 HMAC
  domains and the non-store signature registry:

  | purpose | resource kind | owning schema / signature field | signed projection ID v1 | literal tag | controller / deployment role | reuse, rotation, genesis rule |
  |---|---|---|---|---|---|---|
  | `private-control-pointer` | `private_control_pointer` | `private_control_pointer_attestation.attestation_value` | `private_control_pointer_attestation_projection` | `FinProof/PrivateControlPointerAttestation/v1\x00` | custodian private-control store / `private-control-store-attestor` | unique; deterministic dynamic g0 created once in claim and bound by run HMAC/current witness; contiguous prior/generation; no reset/rotation/reuse |
  | `suite-history-current` | `suite_history` | `registry_current_pointer_attestation.signature` | `registry_current_pointer_attestation_projection` | `FinProof/SuiteHistoryCurrent/v1\x00` | custodian suite-history store / `suite-history-store-attestor` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `human-governance-current` | `human_governance` | `registry_current_pointer_attestation.signature` | `registry_current_pointer_attestation_projection` | `FinProof/HumanGovernanceCurrent/v1\x00` | custodian human-governance store / `human-governance-store-attestor` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `sink-registry-current` | `sink_registry` | `registry_current_pointer_attestation.signature` | `registry_current_pointer_attestation_projection` | `FinProof/SinkRegistryCurrent/v1\x00` | custodian sink-registry store / `sink-registry-store-attestor` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `slot-preparation-current` | `slot_preparation` | `registry_current_pointer_attestation.signature` | `registry_current_pointer_attestation_projection` | `FinProof/SlotPreparationCurrent/v1\x00` | custodian slot-preparation store / `slot-preparation-store-attestor` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `aead-nonce-registry-current` | `aead_nonce_registry` | `registry_current_pointer_attestation.signature` | `registry_current_pointer_attestation_projection` | `FinProof/AeadNonceRegistryCurrent/v1\x00` | custodian nonce-registry store / `aead-nonce-registry-store-attestor` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `candidate-ingress-current` | `candidate_ingress` | `candidate_ingress_current_attestation.signature` | `candidate_ingress_current_attestation_projection` | `FinProof/CandidateIngressCurrent/v1\x00` | custodian candidate-ingress store / `candidate-ingress-store-attestor` | unique; deterministic dynamic g0 created once in claim and bound by run HMAC/current witness; contiguous prior/generation; no reset/rotation/reuse |
  | `owner-remediation-signer-current` | `owner_remediation_signer` | `owner_remediation_signer_current_attestation.signature` | `owner_remediation_signer_current_attestation_projection` | `FinProof/OwnerRemediationSignerCurrent/v1\x00` | owner blind signer / `owner-remediation-signer-current` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `official-instruction-current` | `official_instruction_current` | `activation_authority_read_attestation.signature` | `official_instruction_current_attestation_projection` | `FinProof/OfficialInstructionCurrent/v1\x00` | official-instruction custodian / `official-instruction-current` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `trusted-clock-current` | `trusted_clock_current` | `activation_authority_read_attestation.signature` | `trusted_clock_current_attestation_projection` | `FinProof/TrustedClockCurrent/v1\x00` | trusted-clock service / `trusted-clock-current` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `submission-state-current` | `submission_state_current` | `activation_authority_read_attestation.signature` | `submission_state_current_attestation_projection` | `FinProof/SubmissionStateCurrent/v1\x00` | submission-state custodian / `submission-state-current` | unique; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `identity-authority-current` | `identity_authority_current` | `identity_authority_current_attestation.signature` | `identity_authority_current_attestation_projection` | `FinProof/IdentityAuthorityCurrent/v1\x00` | identity authority / `identity-authority-current` | unique and distinct from identity-object signing; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |
  | `release-action-current` | `release_action_current` | `release_action_current_attestation.signature` | `release_action_current_projection` | `FinProof/ReleaseActionCurrent/v1\x00` | custodian release-action store / `release-action-store-attestor` | unique and distinct from verified-publication signer; g0-pinned; contiguous prior/generation; no reset/rotation/reuse |

  Every row uses scheme `ED25519_STORE_ATTESTATION_V1`; shared owning schema/projection IDs remain
  branch-discriminated by the row's literal resource kind and tag. The generated lock, schemas,
  deployment manifest and acceptance fixtures compare this table bidirectionally and reject a missing,
  extra or changed row. Task 3 deliberately does not freeze a synthetic deployment resource/key ID or
  fingerprint. The immutable manifest supplies every row's real key tuple and supplies a g0 checkpoint
  only for deployment-global rows. The two per-run rows `private-control-pointer` and
  `candidate-ingress-current` instead use the exact dynamic absent-to-deterministic-g0 claim semantics
  in their owning contracts; the manifest pins only their key/purpose/projection/genesis policy, while
  the run HMAC/current witness binds the actual g0. No two
  store rows share a key resource, and no store row shares one with any HMAC or non-store signature
  purpose;
- one exact generated non-store FinProof signature-purpose registry, explicitly separate from both the
  thirteen store rows and the 27 HMAC domains:

  | purpose | owning schema / signature field | signed projection v1 | scheme / literal tag | controller / deployment role / reuse |
  |---|---|---|---|---|
  | `deployment_trust_anchor_manifest` | `deployment_trust_anchor_manifest.owner_signature` | `deployment_trust_anchor_manifest_digest_bytes` | `ED25519_OWNER_APPROVAL_V1` / `FinProof/DeploymentTrustAnchorManifest/v1\x00` | repository owner / `deployment-trust-manifest-owner` / unique |
  | `evaluation_deployment_trust_anchor_pin` | `deployment_trust_anchor_pin_receipt.signature` | `deployment_trust_anchor_pin_receipt_without_signature` | `ED25519_OWNER_APPROVAL_V1` / `FinProof/DeploymentTrustAnchorPin/v1\x00` | repository owner / `deployment-trust-pin-owner` / unique |
  | `checkpoint_candidate_pin` | `checkpoint_candidate_pin_receipt.signature` | `checkpoint_candidate_pin_receipt_without_signature` | `ED25519_OWNER_APPROVAL_V1` / `FinProof/CheckpointCandidatePin/v1\x00` | repository owner / `checkpoint-candidate-pin-owner` / unique |
  | `official_instruction_semantic_review` | `official_instruction_semantic_review_record.signature` | `official_instruction_semantic_review_without_signature` | `ED25519_OWNER_APPROVAL_V1` / `FinProof/OfficialInstructionSemanticReview/v1\x00` | repository owner / `official-instruction-review-owner` / unique |
  | `owner_remediation_public_approval` | `owner_remediation_public_approval_attestation.signature` | `owner_remediation_public_decision_request` | `ED25519_OWNER_APPROVAL_V1` / `FinProof/OwnerRemediationPublicApproval/v1\x00` | repository owner / `owner-remediation-approval` / unique |
  | `human_stable_identity` | `human_stable_identity_attestation.signature` | `human_stable_identity_attestation_without_signature` | `ED25519_IDENTITY_AUTHORITY_V1` / `FinProof/HumanStableIdentity/v1\x00` | identity authority / `identity-authority-object-signing` / reusable only with next row |
  | `owner_curator_non_alias` | `owner_curator_non_alias_proof.signature` | `owner_curator_non_alias_proof_without_signature` | `ED25519_IDENTITY_AUTHORITY_V1` / `FinProof/OwnerCuratorNonAlias/v1\x00` | identity authority / `identity-authority-object-signing` / reusable only with prior row |
  | `verified_published_report` | `verified_published_report_receipt.signature` | `verified_published_report_receipt_without_signature` | `ED25519_VERIFIED_PUBLICATION_V1` / `FinProof/VerifiedPublishedReport/v1\x00` | custodian publication signer / `verified-published-report-signer` / unique |

  Every owning object has exactly one canonical base64 64-byte signature and byte-reproduces the row's
  purpose/scheme/tag/controller/resource/key ID/public-key fingerprint; the manifest digest projection
  means exactly `bytes.fromhex(canonical_manifest_sha256)`, while the other rows use the canonical
  object/projection already stated in their owning contract. The deployment manifest contains one
  exact key tuple for each row and the validator compares this table bidirectionally with schema,
  manifest, formulas and acceptance fixtures. Cross-row/store/HMAC key reuse is forbidden except the
  one explicitly paired identity-authority role above. The organizer's externally supplied
  method-specific authority evidence is not a FinProof signer purpose and remains outside this table;
- a strict `$defs/deployment_trust_anchor_manifest` contract for the owner-approved immutable Phase-4
  artifact `release/evaluation-deployment-trust-anchors.json`. Before any non-open selection/review/
  preparation, Phase 4 creates and externally pins its sole version with manifest version, governance-
lock SHA-256, every real HMAC/AEAD/KMS/asymmetric/owner-approval/blind-signer purpose, the non-signing
`access-context-reader` service role with immutable service/image/config digest and accepted OS-peer/
mTLS trust-root fingerprints, and the exact
`verified-published-report-signer` publication-signature purpose with controller, resource ID, key ID,
immutable public-key fingerprint and `ED25519_VERIFIED_PUBLICATION_V1`, plus each remaining purpose's
resource/key IDs/immutable attestation or public-key fingerprint, the complete concrete non-generative
reference-executor manifest descriptor/hash validated against the Task-3 role policy, the complete
concrete evaluation-scorer-resource and scoring-rule manifest descriptors/hashes validated against
their Task-3 interface/AST policies, cross-kind
  non-alias/separation proof, and every deployment-global generation-zero store attestation/checkpoint
  tuple. Each such
  tuple contains only resource/genesis/generation/store version, complete signed attestation bytes and
  digest, and the signed state digest; it never inlines a custodian-private state, reservation plan/
  receipt, allocation identity, usage counter or store-enforcement metadata. Those private bytes are
  resolved only through their deployment-pinned bounded readers. Key bytes are absent. The manifest
  contains exactly one `owner_signature` object matching the non-store registry row above; no threshold,
  array, second owner or alternate scheme is legal. The strict unsigned projection removes only root
  `canonical_manifest_sha256` and that one owner-signature value while retaining signature metadata/key
  references. `canonical_manifest_sha256 = SHA256(canonical_bytes(unsigned_projection))`; owner
  signatures are over
  `b"FinProof/DeploymentTrustAnchorManifest/v1\x00" || bytes.fromhex(canonical_manifest_sha256)`.
  `complete_deployment_trust_anchor_manifest_sha256` is computed externally over the complete canonical
  object including canonical hash/signatures and is never a member of that object.

  The one manifest is externally pinned by repository-owner approval in the release dossier and is
  immutable for this competition history. `$defs/deployment_trust_anchor_manifest` therefore requires
  `manifest_version: 1` and no predecessor/current-successor member. `DeploymentTrustAnchorReader`
  exposes exactly `read_pinned_manifest() -> (pin_receipt_bytes, manifest_bytes)`. The strict
  `$defs/deployment_trust_anchor_pin_receipt` contains exactly receipt version, immutable release-
  dossier artifact ID/SHA-256, complete manifest SHA-256, signed-at tick, purpose
  `evaluation_deployment_trust_anchor_pin`, externally provisioned repository-owner deployment-
  approval key role/resource ID/key ID/public-key fingerprint, `ED25519_OWNER_APPROVAL_V1`, and one
  canonical base64 64-byte signature. Its signed message is exactly
  `b"FinProof/DeploymentTrustAnchorPin/v1\x00" || canonical_bytes(receipt_without_signature)`.
  The owner public-key fingerprint is a Phase-4 out-of-band release-dossier trust root obtained before
  either returned object is parsed; it may not come from the manifest, receipt or caller. Task 3 checks
  the exact projection/tag/key-reference and Phase 4 cryptographically verifies the signature. The
  reader returns the immutable external pin receipt plus the
  complete canonical manifest bytes; every non-open validator byte-compares the supplied model and
  external complete digest to that independently read object. A caller-selected self-signed object,
  alternate pin receipt, unsigned `canonical_manifest_sha256`, second manifest or stale/forged reader
  result is invalid. Any real key/resource rotation, revocation or loss stops every later non-open
  action and requires a new owner-approved frozen design; it never resets this global history or
  silently creates a successor trust manifest. Synthetic Task-3 fixtures validate shape/order only.
  The complete manifest and pin receipt are deployment/custodian/implementer-ACL-private release-
  dossier objects, never UI, report, outbox, anonymous-repository or repository-disclosure payloads;
  public artifacts may carry only the already specified complete-object digest and intentionally
  public-safe checkpoint commitments. This ACL is defense in depth, not a hiding claim: every resource
  ID, service/image/config digest, public-key/trust-root fingerprint and signed checkpoint value inside
  the complete manifest is explicitly classified non-secret verification metadata, and no credential,
  key byte, bearer endpoint, private allocation state or access-enabling token may occur. A plain
  manifest SHA-256 is not treated as a hiding commitment. If deployment requires any such field to be
  confidential, this manifest shape is invalid and the design must be re-frozen with a separate
  private projection/secret-backed commitment before use.
  Every non-open suite/history/fingerprint/run/current-resource witness reproduces the one
  `complete_deployment_trust_anchor_manifest_sha256`, and Phase 4 resolves keys/checkpoints only through
  it. The manifest carries complete generation-zero checkpoint tuples only for deployment-global
  resources. Dynamic per-run private-control and candidate-ingress rows carry only their purpose/tag/
  projection/key-resource and deterministic-genesis policy here; their actual later generation-zero
  attestations are created at claim and bound by the run HMAC/current witness, never predicted or
  inserted into this manifest. Domain/tag/key-resource substitution, an unregistered signer, alternate
  genesis, silent rotation or reuse outside its exact policy row is invalid;
- for each official-instruction, trusted-clock and submission-state authority resource, the exact
  immutable generation-zero checkpoint tuple from that deployment manifest. Those three tuples are the
  sole activation-chain starting anchors;
  caller-selected later checkpoints and alternate pin receipts are forbidden. Each resource has at
  most 4,096 lifetime successors under this design; exceeding that bound stops for a new frozen design
  rather than silently advancing the trust anchor;
- disclosure classes, fixed report views, `minimum_non_open_eligible: 10`, `cell_k: 5`, and
  whole-partition suppression rules;
- closed scorer-interface ID/version, deterministic input/output/evidence contract and strict
  scoring-rule AST/schema policy. Task 3 freezes no future scorer executable/rule-manifest content
  hash. Before non-open truth creation, Phase 4 builds strict
  `$defs/evaluation_scorer_resource_manifest` and `$defs/scoring_rule_manifest`, validates them against
  those policies and binds their complete descriptors/hashes in the immutable deployment trust-anchor
  manifest; every suite/fingerprint/runtime/outcome/report reproduces those deployment-pinned hashes;
- a closed checkpoint-discriminated evaluation-execution-contract registry with exactly
  `FINPROOF_DETERMINISTIC_CORE_V1` version `1.0.0` for
  `POST_PHASE_2_DETERMINISTIC_ENGINE`, and `FINPROOF_GET_ANSWER_V1` version `1.0.0` for
  `POST_PHASE_3_HCX_PLANNER_API` and `RELEASE_CANDIDATE`, plus the Canonical JSON v1 SHA-256 of the
  selected closed projection;
- a closed candidate-independent isolation-profile registry with exactly one versioned security
  template per execution kind, its canonical hash, immutable UID/security-context/read-only-root
  requirements, mount/environment-name/secret-purpose/IPC role allowlists, and the explicit
  custodian/truth/KMS/host-control deny set defined in Section 4; each later fingerprint supplies the
  complete candidate-build resource manifest constrained by that template;
- branch-specific deny-by-default evaluation egress-policy ID/version/hash: deterministic core allows
  no candidate network egress, while end-to-end allows only the exact HCX endpoints; both may use
  named custodian operational services (KMS, durable clock, audit/attestation) that receive no
  question/product payload and return no financial facts, and every legal end-to-end provider
  invocation is receipted;
- the single global history-registry identity, immutable genesis-anchor contract, atomic current-head
  compare-and-swap rule, pre-decryption truth-release commit, and post-outcome successor requirement;
- the private append-only slot-preparation-registry identity/genesis/current-head lineage and permanent
  one-selection-per-global-slot rule;
- one pinned, attested, monotonic private-control current-pointer resource per activated allocation,
  its no-reset/no-fork CAS generation contract, and exact snapshot-predecessor transition rule;
- the private append-only human-governance-registry identity/genesis/current-head lineage, stable-
  principal curation-approval scope, output-exposure fence, and all-scoped-suites-before-access rule;
- `max_human_curation_scope_entries: 4`, `max_human_governance_records_per_scope: 32`,
  `max_human_governance_record_bytes: 1048576`, and
  `max_human_governance_bytes_per_scope: 33554432` in a separately preallocated private governance
  store that is never charged to or disclosed through a suite reservation;
- competition-lifetime `max_organizer_opportunities: 64`, `max_human_curation_scopes: 64`,
  `max_human_governance_records_total: 2048`, and
  `max_human_governance_bytes_total: 2147483648`; these global archive bounds are distinct from and
  simultaneously respect the per-scope limits above;
- global locked-checkpoint/sealed-cycle consumption-slot identifiers and the pre-truth
  claim/transport-close/transfer/burn/truth-commit state machine, persistent
  retired-token fence ledger, and two-way truth-capability terminalization;
- write-only late-output sink retention/destruction, no-routine-read, exceptional-forensic-role, one
  pinned private sink-registry ID/genesis/current-head lineage, fixed per-slot audit-closure schedule,
  and monotonic watermark/head rules;
- `max_cases_per_non_open_suite: 10000`, `reserved_suites_per_slot: 1`, and
  `max_output_sink_receipts_per_slot: 10001` (at most 10,000 initial tokens plus the one
  suite-wide retry token);
- `max_candidate_response_bytes: 1048576` per case attempt;
- `max_public_report_bytes: 16777216` per original/corrected canonical outbox payload;
- `max_candidate_response_bytes_per_run: 67108864` across unique response blobs,
  `max_public_report_outbox_bytes_per_run: 33554432`,
  `max_private_control_manifest_snapshot_bytes: 65536`,
  `max_private_control_snapshot_descriptor_delta: 16`,
  `max_private_control_pointer_attestation_bytes: 16384`,
  `max_candidate_ingress_state_bytes: 16384`,
  `max_candidate_ingress_pointer_attestation_bytes: 16384`,
  `max_candidate_ingress_terminal_receipt_bytes: 16384`,
  `max_candidate_ingress_terminal_receipts_per_run: 10001`,
  `max_candidate_ingress_terminal_receipt_manifest_bytes: 8388608`,
  `max_candidate_ingress_current_witness_bytes: 16777216`,
  `max_candidate_ingress_terminal_receipt_stream_bytes: 163856384`,
  `max_private_control_current_read_receipt_bytes: 16384`,
  `max_private_control_records_per_run: 200002`,
  `max_private_control_manifest_snapshots_per_run: 210014`,
  `max_private_binary_blob_descriptors_per_run: 10004`,
  `max_private_control_record_bytes: 134217728`, `max_truth_payload_record_bytes: 16777216`,
  `max_recovery_record_ciphertext_bytes: 48`, `max_truth_session_ciphertext_bytes: 16777232`,
  `max_aead_nonce_claim_receipts_per_run: 2`, and private-control reservation formula version `1`;
- `max_registry_current_pointer_attestation_bytes: 16384`,
  `max_current_registry_snapshot_receipt_bytes: 65536`,
  `max_current_registry_witness_bytes: 524288`,
  `max_deployment_trust_anchor_manifest_bytes: 16777216`,
  `max_deployment_trust_anchor_pin_receipt_bytes: 1048576`,
  `max_deployment_trust_anchor_roles: 64`,
  `max_checkpoint_candidate_provenance_subject_bytes: 4194304`,
  `max_checkpoint_candidate_pin_receipt_bytes: 1048576`,
  `max_checkpoint_candidate_pre_execution_order_witness_bytes: 4194304`,
  `max_checkpoint_candidate_final_repository_order_witness_bytes: 4194304`,
  `max_checkpoint_candidate_artifact_bytes: 1073741824`,
  `max_checkpoint_candidate_git_object_stream_bytes: 1073741824`,
  `max_reference_executor_manifest_bytes: 16777216`,
  `max_reference_executor_closure_entries: 4096`,
  `max_reference_executor_disjointness_receipt_bytes: 4194304`,
  `max_reference_truth_derivation_receipt_bytes: 1048576`,
  `max_reference_truth_execution_request_bytes: 16777216`,
  `max_reference_truth_execution_output_bytes: 16777216`,
  `max_reference_executor_artifact_bytes: 1073741824`,
  `max_evaluation_scorer_resource_manifest_bytes: 16777216`,
  `max_scoring_rule_manifest_bytes: 16777216`,
  `max_reference_truth_suite_witness_bytes: 268435456`,
  `max_reference_truth_derivation_receipts_per_suite: 10000`, and
  `max_reference_truth_artifact_stream_bytes_per_suite: 1099511627776`,
  `reference_truth_execution_timeout_ms: 60000`,
  `reference_truth_suite_timeout_ms: 86400000`,
  `reference_truth_executor_memory_bytes: 2147483648`, and
  `reference_truth_executor_cpu_ms_per_suite: 86400000`,
  `max_owner_remediation_public_request_bytes: 262144`,
  `max_owner_remediation_owner_approval_bytes: 524288`,
  `max_owner_remediation_private_join_projection_bytes: 4194296`,
  `owner_remediation_private_join_padded_bytes: 4194304`,
  `max_owner_remediation_private_join_bytes: 4195328`,
  `max_owner_remediation_signer_result_bytes: 524288`,
  `max_owner_remediation_signer_receipt_bytes: 1048576`,
  `max_owner_remediation_signer_state_witness_bytes: 1048576`,
  `max_human_stable_identity_attestation_bytes: 65536`,
  `max_owner_curator_non_alias_proof_bytes: 65536`,
  `max_identity_authority_current_witness_bytes: 1048576`,
  `max_postfreeze_incomplete_scope_fence_bytes: 1048576`,
  `max_revoked_public_id_plan_bytes: 16384`,
  `max_evaluation_scope_schedule_offset_profile_bytes: 65536`,
  `max_evaluation_scope_deadline_stage_witness_bytes: 16777216`,
  `max_activation_authority_transition_records_per_resource: 4096`,
  `max_activation_authority_transition_record_bytes: 1048576`, and
  `max_activation_authority_transition_bytes: 16777216`; every raw attestation, manifest, current-read
  receipt and transition record is length-checked before JSON parsing or signature verification;
  `max_official_instruction_snapshot_records: 4096`,
  `max_official_instruction_record_bytes: 1048576`,
  `max_official_instruction_snapshot_bytes: 16777216`,
  `max_official_instruction_applicability_manifest_bytes: 16777216`,
  `max_non_open_irreversible_action_subject_bytes: 65536`,
  `max_non_open_irreversible_action_authority_state_bytes: 65536`,
  `max_non_open_irreversible_action_authority_guard_bytes: 65536`, and
  `max_irreversible_action_authority_binding_bytes: 262144`;
- `max_private_history_record_bytes: 16777216`, `max_initial_private_history_records_per_suite: 100000`,
  `max_initial_private_history_bytes_per_suite: 4294967296`,
  `max_total_private_history_records_per_suite: 400000`,
  `max_total_private_history_bytes_per_suite: 34359738368`,
  `max_private_history_archive_manifest_bytes: 134217728`,
  `max_private_history_archive_descriptors_per_manifest: 200000`,
  `max_private_history_records_per_transition: 160000`,
  `max_private_history_bytes_per_transition: 17179869184`,
  `max_private_history_manifests_per_transition: 1`, and private-history reservation formula version
  `1`;
- competition-lifetime `max_global_history_revisions: 100000`,
  `max_global_history_archive_manifests: 100000`,
  `max_global_history_archive_descriptors: 76800000`, and
  `max_global_private_history_bytes: 8796093022208`; validators precheck committed aggregate counts/
  lengths before traversal and stream within these finite bounds;
- `max_cumulative_disclosure_entries: 100000`,
  `max_cumulative_disclosure_archive_manifests: 100000`,
  `max_cumulative_disclosure_archive_manifest_bytes: 134217728`,
  `max_cumulative_disclosure_descriptor_bytes: 137438953472`,
  `max_release_report_validation_dossier_bytes: 134217728`,
  `max_release_report_validation_entries: 100002`,
  `max_release_report_validation_shards: 196`,
  `max_release_report_validation_entries_per_shard: 512`,
  `max_release_report_validation_entry_shard_bytes: 67108864`,
  `max_release_report_validation_descriptor_bytes: 137438953472`,
  `max_verified_published_report_receipt_bytes: 1048576`,
  `max_release_action_receipt_bytes: 1048576`,
  `max_release_action_state_bytes: 1048576`,
  `max_release_action_current_attestation_bytes: 16384`,
  `max_release_action_current_witness_bytes: 4194304`,
  `max_release_action_store_reservation_plan_bytes: 1048576`,
  `max_release_action_store_reservation_receipt_bytes: 1048576`,
  `max_release_action_result_record_bytes: 16777216`,
  `max_release_action_entries: 100256`, and
  `max_release_action_archive_bytes: 2199023255552`; the independently authenticated totals are checked
  before the first cumulative report/outbox read;
- `max_derivation_parents_per_case: 8`,
  `max_history_index_proofs_per_registration_transition: 300000`,
  `max_total_history_index_proofs_per_suite: 400000`, and `max_history_proofs_per_chunk: 512`;
- `max_open_evaluation_record_bytes: 16777216`, `max_open_evaluation_records: 50000`,
  `max_open_evaluation_manifest_bytes: 67108864`, and
  `max_open_evaluation_total_bytes: 1073741824`;
- end-to-end `max_provider_invocations_per_case_attempt: 2`,
  `max_provider_invocations_per_run: 20000`, and `provider_transport_retries_per_invocation: 0`;
  deterministic core requires both provider-invocation maxima to be zero;
- `max_runtime_observations_per_run: 30004`: deterministic core has one `run_start`, at most 10,000
  `at_local_invoke`, no `at_egress`/`provider_invocation`, one `pre_truth_commit`, one
  `scoring_start`, and one `scoring_finalized` (at most 10,004 total); end-to-end substitutes at most
  10,000 `at_egress` plus at most 20,000 `provider_invocation` observations (at most 30,004 total);
  the never-dispatched ordinal-0 retry binding adds none;
- `max_pretruth_infrastructure_retries_per_suite: 1`;
- precommitted integer `request_timeout_ms`, `suite_deadline_ms`,
  `authorization_event_deadline_ms`, `capability_terminal_deadline_ms`, and
  `truth_recovery_deadline_ms`, and `scoring_finalization_deadline_ms`, each measured by one
  registered monotonic-clock
  service/version and each bounded from 1,000 through 86,400,000 milliseconds. Every conversion from
  one of these durations or a schedule-profile offset to an absolute tick uses the single checked
  integer contract
  `duration_ns = checked_mul(duration_ms, 1000000)` followed by
  `deadline_tick = checked_add(start_tick, duration_ns)`, where the duration is a nonnegative integer,
  the start and result are signed 64-bit monotonic nanoseconds in the same resource/genesis/epoch, and
  either checked operation failing rejects the object before any write. Directly adding milliseconds
  to a nanosecond tick, floating-point conversion, rounding, saturation, or unit inference from a field
  name is invalid;
- strict `$defs/evaluation_scope_schedule_offset_profile` is an owner-approved immutable row of the
  governance lock, not caller configuration. It contains exactly profile ID/version, the authenticated
  official competition/submission milestone source/message/archive IDs and
  content SHA-256, canonical RFC 3339 UTC milestone and integer UTC-nanosecond value, schema ceiling
  `official_scope_terminal_horizon_ms: 31536000000`, an exact four-entry ordered array for
  `POST_PHASE_2_DETERMINISTIC_ENGINE`, `POST_PHASE_3_HCX_PLANNER_API`,
  `RELEASE_CANDIDATE(candidate_cycle_ordinal=0)`, and
  `RELEASE_CANDIDATE(candidate_cycle_ordinal=1, conditional_remediation_child)`, plus one
  `scope_completion_offset_ms`. Each entry contains its fixed obligation identity and positive integer
  `suite_execution_offset_ms`, `report_closure_offset_ms`, and `slot_audit_not_before_offset_ms`;
  `owner_resolution_offset_ms` is non-null exactly on the conditional-child entry and null elsewhere.
  Every offset is at most the stated horizon and the profile itself proves the same strict ordering
  required of the absolute schedule below. Its external digest is
  `complete_schedule_offset_profile_sha256 = SHA256(canonical_bytes(complete_profile))`; the strict
  `schedule_offset_profile_ref` is exactly `{profile_id, profile_version,
  complete_schedule_offset_profile_sha256}`. The profile expressly forbids its containing governance-
  lock SHA-256, its own digest, deployment-manifest digest or any resulting object: the acyclic order is
  source inputs -> profile row -> generated governance lock -> external complete lock SHA-256 ->
  deployment manifest. The immutable deployment manifest binds the complete governance-lock SHA-256
  that contains this exact row, so no standalone JSON, later owner choice, implementation
  default, or unsigned replacement is an approval. Generator/schema/model/lock comparison is
  bidirectional and a missing, fifth, reordered, unit-renamed, or differently hashed entry fails
  before review;
- a strict `$defs/evaluation_scope_terminal_schedule_projection` and registry entry. The projection
  begins with schedule ID/version, exact `scope_batch_id`, authenticated `scope_created_tick`, common
  monotonic-clock resource/genesis/epoch, the complete `schedule_offset_profile_ref`, and the complete
  current `submission_freeze_basis` that maps the profile's exact milestone to that same clock epoch,
  followed by the entries and
  final deadlines below. Review approvals
  and the conditional-child base bind only the immutable `schedule_offset_profile_ref` and must
  forbid every absolute schedule tick/descriptor/hash. During the winning
  `scope_and_slot_prepare_commit`, after the complete current official-instruction/trusted-clock/
  submission-state authority tuple is independently read and held but before the scope record is
  serialized, Phase 4 builds the one absolute schedule from preselected `scope_batch_id`, candidate
  `scope_created_tick`, clock resource/genesis/epoch and that profile. `scope_created_tick` must equal
  the held trusted-clock current attestation tick and the common authority read-lock observed tick; it
  is never caller chosen. Any clock successor requires rebuilding the schedule and every downstream
  candidate object. The profile milestone fields
  must byte-equal the first-ranked source fields in `submission_freeze_basis`; the basis conversion
  and `submission_freeze_effective_tick` are recomputed exactly as specified below. Every schedule
  deadline, including scope completion, must be at or before that effective tick, and no result-bearing
  writer may commit at or after it. A losing CAS discards this
  candidate schedule/scope/bases/sources and rebuilds them with the new held tick while reusing only the
  earlier approvals/base;
- the schedule contains one through four entries in exact scope execution-ordinal order. Each entry
  has schedule-entry version, ordinal, lane/checkpoint, complete slot/candidate-cycle identity and
  absolute `suite_execution_deadline_tick`, `report_closure_deadline_tick`, and
  `slot_audit_not_before_tick`. It also has nullable `owner_resolution_deadline_tick`, non-null exactly
  on the `conditional_remediation_child`/candidate-cycle ordinal-1 entry and null on every other entry,
  plus one final `scope_completion_deadline_tick`. Every absolute
  value is `checked_add(scope_created_tick,
  checked_mul(the_matching_profile_offset_ms, 1000000))` under the shared signed-64-bit contract above;
  all tick fields are monotonic nanoseconds and all profile offset fields are milliseconds.
  The profile is derived from the dated official competition/submission milestone recorded in the
  governance lock and has no seven-day or implementation default; each positive offset is bounded by
  the profile's generated `official_scope_terminal_horizon_ms` and schema ceiling. Missing official/
  owner approval, a milestone already passed, a current official/submission-state mismatch, or checked
  multiply/add overflow
  is a pre-review stop condition. Within each entry execution < report < audit-not-
  before, and each unconditional entry's audit-not-before < the next entry's execution. For a sealed
  parent/child pair, parent audit-not-before < owner-resolution deadline < child execution < child
  report < child audit-not-before < scope-completion deadline. The last unconditional audit-not-before
  is also strictly before scope completion. Duplicate/missing ordinals, one shared audit tick or an
  owner deadline before the parent audit are invalid;
- the strict `$defs/evaluation_scope_terminal_schedule_ref` contains exactly schedule ID/version,
  `scope_batch_id`, schedule-record descriptor/length/SHA-256, the complete
  `schedule_offset_profile_ref` and the selected
  entry ordinal. The complete schedule is a custodian-private human-governance record (at most
  1,048,576 bytes) written in the same scope CAS, named in that transition's ordered record list and
  resolved only by `HumanGovernanceRecordReader`. It consumes one of the fixed 32 records and bytes;
  crash recovery never depends on caller-held schedule bytes. The scope record contains the schedule
  descriptor/hash. The combined basis, every slot-preparation source/row/receipt, complete suite
  preclaim basis, claim/run/candidate-set, private report/
  audit append and human-completion record byte-reproduce the exact ref and select only their matching
  entry; no approval/base does. A repository report, public history/lifecycle event or outbox forbids
  the private descriptor/hash/ticks and carries only the fixed offset-profile ID/version plus its
  ordinary opaque secret-backed commitment. `identity_valid_through_tick` is exactly the final
  scope-completion deadline. The generator compares this propagation map bidirectionally with every
  strict schema/model. A schedule ID alone, a substituted entry or a retry retaining a prior candidate
  tick is insufficient;

  The following augmentation table is authoritative and augments every later field list that says
  “exactly” or “contains exactly”; generated schema/model parity fails if an owner omits it:

  | owner | exact schedule member |
  |---|---|
  | human review approval and conditional-child base | complete `schedule_offset_profile_ref` only; absolute ref/bytes/ticks forbidden |
  | private schedule record | complete `evaluation_scope_terminal_schedule_projection`; own descriptor/hash and every human/slot/storage/resulting head forbidden |
  | human scope and combined human transition | complete schedule-record descriptor/length/SHA-256 plus offset-profile ref; transition ordered-record list names that descriptor |
  | `scope_and_slot_prepare_basis_projection`, slot source/row/receipt, `suite_preclaim_basis`, private-control/history reservation plans and HMAC projection | byte-identical selected `evaluation_scope_terminal_schedule_ref` |
  | claim/run/candidate-attempt-set, outcome/private-report append, claimed-slot audit and human completion | byte-identical selected schedule ref; selected ordinal/slot must equal the owner; the public fingerprint joins it only through the existing storage HMAC |
  | public fingerprint/history/lifecycle/report/outbox/summary | private schedule ref/descriptor/hash/ticks forbidden; fixed offset-profile ID/version and the already registered suite-specific `evaluation_storage_reservation_hmac_reference` are the only schedule continuity fields where that HMAC reference already exists |

  This shared rule introduces no new HMAC domain: the preclaim ref is already inside
  `evaluation_storage_reservation_projection`, and every later private owner is covered by its existing
  HMAC/signature projection. The complete human-governance witness must include the schedule-record
  descriptor and `HumanGovernanceRecordReader` must resolve/recompute it before any downstream ref is
  accepted;
- immediately before the common scope CAS publishes any candidate head, the transaction performs a
  final independently current trusted-clock read under the same resource/genesis/epoch, rechecks all
  three authority generations and the guarded global/human/slot/allocation generations, and requires
  `commit_tick < min(suite_execution_deadline_tick for every unresolved scope entry)` as well as
  `scope_completion_deadline_tick <= submission_freeze_effective_tick`. Equality with the earliest
  execution deadline belongs to expiry and cannot publish the scope. A stall, clock successor,
  official-milestone successor or submission-state successor discards the candidate schedule, scope,
  provisional rows and HMACs; only unreachable provisional `prepared` allocations remain eligible for
  the already specified nonmembership reaper;
- every later non-open action that could create dispatch, truth delivery, scoring, an outcome, a report,
  a correction, readiness or submission bytes independently rebuilds the current
  `submission_freeze_basis` from its fresh three-resource authority witness. Its effective bound is
  `min(schedule.submission_freeze_effective_tick,
  current_basis.submission_freeze_effective_tick)` and its observed tick must be strictly less than
  that bound; the complete current basis and bound are retained inside the private
  `irreversible_action_authority_binding`. A later actual `not_submitted -> submitted_frozen` event or
  higher-ranked earlier official milestone therefore cannot be grandfathered by a pre-freeze scope or
  artifact. At or after the current bound no new dispatch/decrypt/scorer/outcome/report/correction/
  readiness/package write is legal; only the already typed no-new-result fence/burn/audit/scope-
  incident cleanup may run. The deployment submission transaction itself must prove every current
  non-open scope has no pending result-bearing obligation and no active/prepared result-bearing slot
  before it may write an early `submitted_frozen` state. An externally observed submission that raced
  this precondition is a stop incident, never permission to finish evaluation after freeze;
- audit closure is not an impossible exact-tick callback. For a claimed/activated slot with a real
  channel, once its required terminal report/burn predecessor exists, the first successful idempotent
  audit CAS at `observed_tick >= slot_audit_not_before_tick` closes it; replay returns the same closure.
  A never-activated zero-channel child/preclaim close is expressly exempt: its resolution writes the
  zero-channel audit and applicable scope-completion suffix immediately in the same CAS, before the
  unused child entry's later audit-not-before tick, because no retention channel ever existed. Ordinary
  execution/report/owner actions require an authoritative tick strictly before their matching
  deadline, while equality belongs to the deterministic expiry branch below. Every per-run suite,
  authorization, truth capability/recovery and scoring-finalization effective deadline is recomputed
  as the minimum of its ordinary component deadline and the matching entry's execution deadline; that
  clamped value is persisted in its existing receipt/HMAC. Therefore a run admitted at deadline-1
  cannot remain legally pending past the schedule boundary, regardless of the separately permitted
  86,400,000-millisecond component maximum;
- strict `$defs/evaluation_scope_deadline_transition` is a private, prepaid action `oneOf` keyed by
  schedule/entry/stage. At or after the applicable tick it deterministically selects: an unclaimed
  prepared/batched entry -> exactly that entry's `scope_schedule_deadline_close` plus zero-channel
  audit; if and only if that entry is sealed ordinal 0, the same CAS also writes the exact
  `not_activated_parent_schedule_deadline` child resolution and its zero-channel audit because the
  activation predicate became impossible. Later unconditional entries remain must-execute and either
  run or reach their own later deadline; claimed with no egress -> existing
  consumption burn; partially dispatched/incomplete candidate set -> fence every live transport/
  ingress, preserve the authenticated attempt prefix and burn; candidate sealed before truth commit ->
  pretruth burn; truth/scoring pending while the current effective freeze bound remains future -> first
  run the already frozen component deadline terminal/uniform-error branch; durable outcome but missing
  report while that bound remains future -> create the one factual deterministic report without
  changing outcome; terminal report/burn -> audit close; and unresolved conditional
  child -> `owner_resolution_expired_nonpass`. The strict transition contains exactly transition/
  schema version, `evaluation_scope_terminal_schedule_ref`, selected stage/reason, observed trusted-
  clock tuple/tick, exact old state/lineage descriptor hashes, branch result kind and no result bytes or
  future head. It is capped at 4,096 bytes and embedded byte-identically in the already reserved owning
  history/control/report/audit/resolution source; at most sixteen occurrences per scope (four entries
  times execution/report/audit plus owner/scope suffix) are included in the generated maximum schedule;
  a generated maximum enclosing `history_transition_source` witness proves the complete 4,096-byte-
  bounded transition plus common fields/proofs remains within that source's 16,384-byte cap.
  Each transition binds the complete schedule/entry,
  trusted-clock witness/tick and exact predecessor proofs in the existing HMAC-protected private append,
  uses only the already prepaid terminal/report/audit records and atomically advances every touched
  global/human/slot/allocation/sink/control head or none. It is a safety terminal and cannot be blocked
  by an official-action prohibition. The earliest unresolved scope ordinal/stage wins; an ordinary
  writer racing at equality loses. Crash recovery queries the authoritative heads and either returns
  the committed transition or retries the same deterministic branch. If authoritative recovery first
  resumes at/after the current submission-freeze bound while truth/scoring/outcome/report work needed
  to satisfy a branch is still absent, the higher-priority official no-post-freeze-results rule is an
  explicit stop condition: no terminal outcome/report/outbox or substitute transition is fabricated,
  existing private evidence is retained, release/readiness/submission stay permanently non-PASS, and
  the unresolved scope is reported as `incomplete_must_execute_scope` to the owner. This exceptional
  external-freeze stop is the only case in which the terminal schedule intentionally does not claim a
  completed result successor. Before returning that stop, strict private
  `$defs/postfreeze_incomplete_scope_fence` must win exactly once for every affected active entry. It
  contains fence/schema version, scope/schedule ref, complete freshly current submission-freeze basis
  and effective bound, observed trusted-clock/current-stage witness digests, exact private-control
  predecessor and one stage `capability_available|truth_session_redeemed|scoring_active|
  outcome_unreported`. The first branch binds the recovery/capability/token identities and makes every
  redemption/decrypt/KMS reader deny; the second binds the durable truth-session/ciphertext refs and
  revokes every session/scorer read grant; the third additionally revokes the scoring lease and seals
  any authenticated work prefix unusable; the fourth binds the immutable outcome/HMAC and denies every
  report/outbox/correction writer. All branches fence live ingress/sink handles, retain ciphertext/
  evidence/prefix/outcome bytes for authorized incident custody, and forbid result/outcome/report/
  outbox bytes, public lifecycle/history/event fields and future/resulting heads in the fence source.
  Its external descriptor is appended in the already prepaid terminal safety-control record slot and
  a same-stage private-control snapshot gains the exact immutable fence ref. One multi-resource CAS
  advances that signed pointer and the applicable KMS/session/lease/ingress access-control generations,
  but no public/global result head; decrypt/scorer/report gates must independently read that current
  pointer and reject once fenced. Replay returns the byte-identical fence, a second fence or later
  access is invalid, and ambiguous crash recovery reads every named generation before retry. The scope
  remains `incomplete_must_execute_scope`, permanently non-PASS/no-readiness/no-submission; the fence is
  administrative security cleanup, not a fabricated terminal result;
- strict validation-only `$defs/evaluation_scope_deadline_stage_witness` is the sole current-stage
  join accepted by the deadline transaction. Its common fields are scope/schedule ref, one held-read-
  fence ID, and the exact signed current-attestation/generation/store-receipt digests for trusted clock,
  the coherent five-registry set, human governance, both prepared allocation stores, and every
  branch-applicable private-control, candidate-ingress, truth-capability, scoring, outcome/report and
  sink resource. Its closed `oneOf` is exactly `unclaimed_preclaim`, `claimed_no_egress`,
  `partial_dispatch`, `candidate_sealed_pretruth`, `truth_or_scoring_pending`,
  `outcome_report_pending`, `terminal_audit_pending`, `owner_resolution_pending`, or
  `scope_completion_pending`; each branch carries only predecessor/current descriptors and proofs
  required by the already defined owning transition and requires every other branch field null. It
  contains no caller stage/reason boolean, terminal result bytes, candidate bytes, or future head and
  is capped at 16,777,216 bytes before parse. `EvaluationScopeDeadlineStageReader.read_current_stage(
  scope_batch_id)` takes only that authenticated key and composes the deployment-pinned existing
  current-resource/read-record protocols; the validator byte-compares the supplied witness to this
  independently returned object. A self-consistent caller witness or one missing any resource touched
  by its branch is non-authorizing and invalid;
- at `scope_completion_deadline_tick`, recovery first applies those state-specific closures in ordinal
  order, then records permanent scope non-PASS/completion from their exact proofs. It never overwrites a
  durable outcome or report: an existing outcome receives only its factual report and a separate
  authenticated schedule-breach/scope-nonpass leaf while still before the current freeze bound; an
  existing report is immutable and only remaining
  audit/scope state closes. Clock unavailability supplies no tick and blocks both ordinary and expiry
  writers until authoritative recovery; recovery at/after the freeze bound applies the stop condition
  above instead of creating a late result. Generated boundary/race vectors cover every stage at
  deadline-1/equality/deadline+1;
- `max_result_bearing_locked_disclosures_per_checkpoint: 1`;
- `max_candidate_cycles_per_organizer_opportunity: 2`, exactly ordinals 0 and 1;
  `max_result_bearing_sealed_disclosures_per_candidate_cycle: 1` and
  `max_result_bearing_sealed_disclosures_per_organizer_opportunity: 2`, with ordinal 1 the sole
  precommitted conditional remediation child and no third/reset/replacement; and
- `max_true_corrections_per_report_lineage: 1` and a closed correction-derivation rule registry; and
- denominator and cumulative sealed-disclosure rules.

The common closed `FINPROOF_CANDIDATE_RESPONSE_V1` projection is strict unique-key UTF-8 JSON with no
BOM/trailing data and exactly five required string fields—`question_id`, `question`,
`retrieved_context`, `think_trace`, and `answer`—with no extras. The first two exactly echo the
committed request strings; `answer` contains at least one non-whitespace Unicode scalar. The other two
may be empty strings but not null/non-string. Its SHA-256 is over the complete Canonical JSON v1
contract projection, not a candidate response instance.

`FINPROOF_DETERMINISTIC_CORE_V1` has exactly execution kind `deterministic_core`, contract ID/version,
literal callable `finproof.service.answer_service.AnswerService.answer_plan`, the exact registered
absolute `$defs/deterministic_core_request` and `$defs/deterministic_core_result` fragment refs/content
hashes, canonical QueryPlan root schema ID/content hash, input serializer
`canonical_json_v1_request_plan_pair`, response-adapter artifact/version, the common response-contract
ID/hash, exact candidate-isolation-profile ID/version/hash, and
`candidate_network_egress: forbidden`. The adapter constructs the internal `AnswerRequest`, invokes
`answer_plan(request, precommitted_plan)` once in the isolated candidate process, converts the result
to the closed deterministic-core result wire, then adds the committed request echoes and emits the
common five-field response into the private output-buffer/seal path. The complete schema-valid
canonical `expected_plan` is deliberate candidate input only in this checkpoint. The expected result,
expected answer, evidence package, score, and every other truth field remain withheld until the
ordinary truth-release commit.

`FINPROOF_GET_ANSWER_V1` has exactly execution kind `end_to_end_api`, contract ID/version, literal
method `GET`, literal path `/answer`, ordered required query names `question_id` and `question`, the
canonical query serializer version below, the common response-contract ID/hash, and the exact
authenticated transport profile plus candidate-isolation-profile ID/version/hash. It never receives a
precommitted QueryPlan. Its response bytes must match the common five-field contract.

`evaluation_execution_contract_sha256` is SHA-256 over Canonical JSON v1 bytes of the selected closed
projection. Governance, manifest, fingerprint, run/runtime/attempt/set/outcome/report objects bind
the same execution kind, contract ID/version/hash, and response-contract hash before any hidden case
is selected. Their conditional schemas require deterministic-core fields and forbid HCX/prompt/
provider/API/origin/TLS/query fields at Phase 2; the end-to-end branch requires those fields and
forbids a candidate-input plan/callable. No per-attempt mode or contract version exists.

The clock is one custodian-store authoritative, durable monotonic time/lease service with a pinned
`clock_instance_id`, epoch ID, and persisted start/deadline ticks; runner process/host clocks are never
authoritative. Every transition reads and updates that service in the same transaction as its state
CAS. An epoch reset, rollback, host-local substitution, or clock-service unavailability burns/blocks
before truth commit. After truth commit or redemption it blocks every transition until the same
instance/epoch and persisted tick sequence are restored; it never fabricates an expiry, switches
epochs, or extends a deadline. Once restored, the ordinary bound-deadline rule applies. If the same
authoritative epoch cannot be recovered, execution stops with no report, continuity, or new cycle.
The reserve commitment, manifest, and freeze fingerprint bind only timeout durations plus clock
service/version/instance/epoch; they never predict future ticks. The atomic claim derives and binds
suite start/deadline ticks. Each dispatch derives its request start/deadline ticks; the truth-release
commit derives authorization, capability-terminal, and recovery ticks plus
`effective_truth_terminal_deadline_tick`, the minimum of those three persisted deadline ticks;
truth-session redemption derives scoring start/deadline ticks. Every later runtime observation,
receipt, outcome, and report
reproduces the applicable already-created ticks. No projection contains the hash of its own future
successor.
Request timeout after `dispatch_committed` becomes that invocation's typed candidate timeout.
A pre-truth suite deadline burns/stops the one slot without replacement. A missed authorization or
capability-terminal deadline enters only the same attempt's deterministic recovery/revocation path.
Terminal precedence is exact: at `observed_tick >= effective_truth_terminal_deadline_tick`, only
`truth_terminal_deadline_expired` may win; before that tick, an exact fresh redemption-authority guard
conflict selects `authority_conflict_after_truth_commit`; otherwise redemption is mandatory when the
transaction can succeed. Neither reason is caller-selected. Boundary equality is expired.
For either revoked branch, the cause-independent private
`revoked_publication_not_before_tick` is exactly the selected scope-schedule entry's
`report_closure_deadline_tick`. The schedule generator proves it is strictly later than
`effective_truth_terminal_deadline_tick`; the report-closure tick itself is the complete not-before
policy and no undefined execution-duration allowance is inferred. The terminal receipt, private
outcome/report, pending release dossier, verified-publication
receipt and release-action completion basis reproduce that same private tick; redeemed and every open
branch forbid it. No public event, history row, report, summary, outbox, receipt or readable identifier
contains the tick, a relative bucket or a branch marker.

All public-shaped successors for a revoked non-open run are staged in custodian-ACL-private storage,
even though their canonical projections are public-safe. Neither repository replication, lifecycle/
history reader, controlled review nor anonymous access may expose any of them before the one guarded
`enable_outbox` CAS wins at or after the common not-before tick. The deployment-owned release call
finishes/revalidates any already prepaid private terminal-to-report prefix before that visibility CAS
and exposes no intermediate state; a caller cannot trigger or advance the release. If clock/current-
store recovery delays the call, both causes remain identically embargoed until the same guarded release
operation succeeds. Thus a pre-deadline authority conflict cannot create an availability oracle for the
deadline-expiry cause.

Create `schemas/evaluation_disposition_policy.schema.json`. Its instances remain custodian-private,
but one instance is owner-approved and HMAC-committed before its reserve batch is activated. The
closed root requires policy ID/version, governance-policy version, checkpoint/lane applicability,
creation/approval role and timestamp, and a `sealed_acceptance` object. Locked validation always uses
the literal disposition `retired`. Sealed acceptance is the conjunction of exact predeclared bounds:
`minimum_passed`, exact-decimal `minimum_pass_rate`, `maximum_failed`, `maximum_runtime_error`,
`maximum_timeout`, `maximum_malformed_output`,
`maximum_evidence_verification_failures`, and `maximum_claim_verification_failures`. Counts are unique
case-invocation counts. Parse `minimum_pass_rate` into its exact non-exponent integer coefficient and
decimal scale, require a value from zero through one, and compare
`passed * 10**scale >= coefficient * eligible`; never divide or depend on a `Decimal` context. Phase 4
chooses and owner-approves the values before selection; Task 3 freezes their shape and deterministic
decision rule, not the competition threshold itself.

Public manifests/history/events/reports carry only `disposition_policy_id`, version, and the complete
foreign-domain `disposition_policy_hmac_reference: $defs/hmac_reference`. The reserve-batch commitment,
suite reservation, freeze fingerprint, claim/run binding, candidate/outcome set, terminal disposition
event, `post_outcome`, private/public report pair, and `report_recorded` receipt reproduce those values
byte-for-byte. The pure validator receives the complete schema-valid private policy, recomputes the
terminal disposition from the outcome set, and checks every non-secret binding; Phase 4 separately
verifies the secret HMAC. Substitution after reserve activation or outcome access fails closed.
The reserve, fingerprint, run binding, runtime observations, scoring ledger/finalization receipt,
outcome set, terminal disposition event, and report also reproduce the exact scorer/rule and egress-
policy identities; neither may be selected after candidate/truth observation.

Independent of configurable numeric bounds, a sealed suite may retire only when
`truth_capability_state: redeemed_with_durable_truth_session` and its outcome set was derived from
that durable session. `revoked_without_delivery` always terminalizes the spent budget and report but
forces sealed `invalidated`; even an all-zero/permissive acceptance policy cannot retire it. Locked
validation retains its fixed retirement/reporting rule while plainly reporting the operational
failure. Any `scoring_completion_state: evaluation_error` likewise forces sealed `invalidated`.

The locked checkpoints are exactly:

- `POST_PHASE_2_DETERMINISTIC_ENGINE`; and
- `POST_PHASE_3_HCX_PLANNER_API`.

The sealed checkpoint is `RELEASE_CANDIDATE`.

The checkpoint-to-execution mapping is total and immutable:

- `POST_PHASE_2_DETERMINISTIC_ENGINE` -> `deterministic_core` /
  `FINPROOF_DETERMINISTIC_CORE_V1`; and
- `POST_PHASE_3_HCX_PLANNER_API` and `RELEASE_CANDIDATE` -> `end_to_end_api` /
  `FINPROOF_GET_ANSWER_V1`.

Mode substitution is not an infrastructure retry or diagnostic variation; it invalidates the suite.

The two locked labels are artifact provenance, not permission to choose a later build. Each Phase-2/
Phase-3 gate must create one strict head-independent `$defs/checkpoint_candidate_provenance_subject`
before the next implementation phase mutates the repository. It contains exactly subject version,
checkpoint ID, governing phase-plan ID/SHA-256, gate command/evidence ID, passed gate tick,
`git_object_format: sha1`, the native lowercase 40-hex candidate commit/tree OIDs, source-snapshot and
dependency-lock descriptors/SHA-256, complete candidate-build resource-manifest descriptor/SHA-256,
reproducible artifact/image IDs/byte lengths/content SHA-256 values, and execution-contract/isolation-
profile IDs/hashes. It contains no pin field, own digest, future repository commit, case, truth, runner
output or evaluation result. Its external
`complete_checkpoint_candidate_provenance_subject_sha256` is SHA-256 of the complete canonical subject
bytes and is never a member of that subject; the current repository uses native SHA-1 Git OIDs and no
schema may mislabel those 40-hex OIDs as SHA-256.

One separate strict `$defs/checkpoint_candidate_pin_receipt` contains exactly receipt version,
checkpoint ID, that complete subject digest, the exact native candidate commit/tree OIDs, signed-at
tick, purpose `checkpoint_candidate_pin`, repository-owner phase-gate approval key role/resource/key
ID/fingerprint, `ED25519_OWNER_APPROVAL_V1`, and one canonical base64 64-byte signature. Its message is
`b"FinProof/CheckpointCandidatePin/v1\x00" || canonical_bytes(receipt_without_signature)`. The owner
fingerprint originates as an out-of-band phase-gate trust root and is copied into the immutable
deployment manifest's exact `checkpoint_candidate_pin` row; it is never selected by the subject or
receipt. Before parsing candidate artifacts, every locked facade independently loads the pinned
manifest, byte-compares the receipt purpose/role/controller/resource/key ID/fingerprint/scheme/tag to
that row and cryptographically verifies this message. A self-signed receipt or a key tuple present only
inside the receipt is invalid.
The pin receipt is written in a dedicated post-gate provenance commit. Repository ordering is split
into two acyclic strict witnesses. `$defs/checkpoint_candidate_pre_execution_order_witness` contains
exactly the candidate and immediate provenance native commit/tree OIDs, provenance path/blob OID, the
current Phase-4 execution-checkout commit/tree OIDs, and the exact parent edges proving
candidate -> immediate provenance -> current execution checkout. It expressly forbids every later
evaluation/report/result, next-phase-gate commit/tree, final witness descriptor/hash and future head.
It is constructed and verified before claim or execution, so locked evaluation never depends on a
future Phase-4 gate.

After both locked evaluations, but before submission readiness is evaluated, Phase 4 creates one
immutable `phase4_evaluation_complete_candidate` commit `G0`. The separate strict
`$defs/checkpoint_candidate_final_repository_order_witness` contains the complete pre-execution
witness descriptor/hash, that same candidate/provenance/execution-checkout tuple, the exact `G0`
commit/tree OIDs and every exact intervening parent edge from the execution checkout through `G0`.
It is constructed only after `G0` exists and is required by the later `release_readiness`/submission
Phase-4 gate. Successful gate evidence is committed afterward as a distinct descendant `G1`; `G1` is
never an input to the witness or to the gate that produces it. Neither locked claim, dispatch, truth
nor scoring may consume the final witness, and no witness field may name a future gate/evidence/result
commit or head.

`CheckpointCandidateArtifactReader.read_pinned_checkpoint(checkpoint_id)` independently returns only
the pin receipt, provenance subject, candidate-build manifest and reproducible artifact bytes.
`read_pre_execution_order_witness(checkpoint_id)` and
`read_final_repository_order_witness(checkpoint_id)` return their distinct bounded canonical witness
bytes. `CheckpointCandidateGitObjectReader` streams the bounded native Git commit/tree/blob objects and
verifies every applicable OID/parent/tree/path edge. Thus a later reconstructed commit cannot be
back-labelled as the earlier gate artifact, while execution does not require a future object.
Phase 4 may execute only byte identities reproduced by the pinned subject. A later build labeled
`POST_PHASE_2_*` or `POST_PHASE_3_*` is invalid.
The Phase-2 and Phase-3 execution plans must therefore be amended before use: each candidate worktree
must be clean, the candidate checkpoint is committed first, the full gate runs against that exact
commit/artifact, and only then may the pin receipt be written in a separate provenance-only commit.
The next phase may begin only after that provenance commit; a gate run over dirty/index-only bytes or a
later status-and-code commit is not a valid checkpoint. The pre-execution and final witnesses freeze
their disjoint exact parent relationships through `G0`; the final Phase-4 gate records its evidence
only in `G1`. The reconciled Phase-4 plan must name and create those two commits in that order, and its
tests execute the current repository's native SHA-1 OIDs.

Because the real locked runner/custody is Phase-4 work, both locked evaluations are delayed historical
evidence produced after the Phase-3 gate from those pinned artifacts. Their report order inside the
four-entry governance scope does not imply the Phase-2 report was available to guide Phase-3 tuning or
served as the Phase-3 entry gate. Phase 3 proceeds only on its own governing plan checks; Phase 4 first
replays the pinned Phase-2 artifact, records that report, then replays the pinned Phase-3 artifact.

The strict deployment-time `$defs/evaluation_scorer_resource_manifest` contains exactly manifest/
interface IDs and versions, deterministic entrypoint/protocol, content-addressed code/artifact/build/
dependency/image/resource closure, input/output/evidence schema descriptors and the closed no-network/
no-generative isolation policy. It forbids every model/prompt/provider/credential artifact and any
suite result, threshold or future fingerprint. The strict `$defs/scoring_rule_manifest` contains only
rule/schema IDs and versions, the closed deterministic rule AST, score-component/evidence/claim-
verification mappings, numeric/rounding/error semantics and output schema; it forbids executable
bytes, candidate/truth/output data, suite-selected thresholds, future heads and own digest. Complete
object descriptors/hashes are external. Phase 4 builds both only after Task 3, validates them against
the frozen interface/AST policies, and has the immutable deployment manifest pin them before any non-
open truth. `DeploymentTrustAnchorReader.read_pinned_deployment_artifact(descriptor)` resolves their
bounded canonical bytes; every fingerprint/runtime/scoring lease byte-compares the supplied identities
to those pinned objects. Before claim, the same `reference_executor_disjointness_receipt` also proves
the complete scorer closure has no candidate planner/compiler/executor/renderer/claim-verifier overlap
outside the exact inert dependency allowlist; deployment pinning alone is never treated as independence.
Task 3 does not claim to create either concrete artifact.

Every non-open execution is a multi-case suite-run envelope, never one batched model request.
`run_attempt_id` names the one suite run that owns the global slot. Its private run-binding projection
contains an ordered `case_invocations` array whose length equals the immutable eligible denominator.
Each entry has an opaque custodian-private `case_invocation_id`, custodian-private stable case
fingerprint, and contiguous `case_ordinal`. Each actual initial or retry invocation is separately
frozen before dispatch by a custodian-private `case_attempt_binding` record/HMAC with fresh
`case_attempt_id`, attempt ordinal, immutable candidate-invocation ID, and output-channel token hash.
For deterministic core the runner makes exactly one isolated local `answer_plan` call per initial
invocation with that case's precommitted canonical plan. For end-to-end it calls organizer-compatible
`GET /answer` exactly once per initial invocation and never sends multiple questions in one request.
Public artifacts expose only the suite-run ID, eligible count, and secret-backed set
commitments; they never expose invocation IDs, case fingerprints, questions, expected truth, per-case
terminal states, or accepted-output flags.

Locked/sealed dispatch is deterministic and sequential: `case_dispatch_order: case_ordinal_ascending`
and `max_in_flight_case_requests: 1`. The next ordinal is not bound or dispatched until the current
ordinal is sealed or its sole retry is terminally resolved; a retry of an ordinal occurs before any
later ordinal. Governance policy, freeze fingerprint, and run binding all bind those two values. This
removes scheduler-selected retry allocation, bounds the live-token set to one, and makes a transfer CAS
prove exact equality between the run-binding invocation prefix and the closed-token ledger. Parallel
locked/sealed dispatch is outside this contract and fails closed.

Each non-infrastructure response/failure is sealed separately by a custodian-private
`candidate_attempt_sealed` record/HMAC against its exact case-attempt binding. After every eligible
case has exactly one final sealed attempt, a public `candidate_attempt_set_sealed` lifecycle event and
domain-separated HMAC bind the complete private ordered invocation/
attempt history and its count, including the initial and retry binding graph. The global truth-release
commit binds that set event/commitment, not a selectable single
response. At most one pre-egress infrastructure retry is available across the entire suite/version.
It is legal only when the attempt remained `bound`, no dispatch/outbox commit or network egress
occurred, the sink proves zero ingress, and the inactive token was durably tombstoned. It replaces
only that failed case attempt while preserving every other sealed case attempt byte-for-byte. Once a
dispatch commit exists, the request is treated as potentially observed by the system under test and
can never receive an evaluation-exempt retry. If ordinal 1 reaches dispatch and then fails, the
affected invocation becomes a typed case outcome and the same suite proceeds as the one
result-bearing run. If ordinal 1 cannot reach dispatch, the exact binding remains blocked for recovery
or the slot burns; an undispatched attempt is never fabricated as an attempted case outcome.
No claim release, reserve replacement, abort, or fingerprint change may advance to another hidden
suite. Existing seals can never be discarded or rerun, and their original binding/head ancestry
remains valid when the run-level active head advances by transfer.

Commit its canonical projection as `config/evaluation_governance.lock.json`. The lock records the
exact YAML-byte SHA-256, policy version, transition/checkpoint projection, canonicalization and
commitment versions, and canonical policy hash. `tools/evaluation_control.py --check` regenerates
and compares it. Bootstrap verification parses the lock with the standard library and verifies the
YAML byte hash; full tests parse and validate the YAML semantics.

### 8.2 Suite manifest

Create `schemas/evaluation_suite_manifest.schema.json`. A manifest publishes no question, expected
plan, expected value, answer claim, evidence payload, or failure detail for locked/sealed cases. It
records:

- suite ID, version, lane, immutable `initial_state: draft`, governance-policy version,
  non-resettable `release_cycle_id`, and the lane-conditional complete `candidate_cycle_identity`;
- selected execution kind/contract ID/version/content SHA-256, common response-contract SHA-256, and
  static candidate-isolation-profile ID/version/content SHA-256 plus
  `candidate_build_resource_manifest_sha256`;
- authored/excluded/eligible totals; open manifests may also carry category/product/metric
  applicability counts, while non-open manifests keep every fine applicability count inside the
  case-set commitment until the disclosure policy permits it;
- a complete case-set `$defs/hmac_reference` that does not expose low-entropy truth;
- curator/reviewer/custodian role IDs;
- truth method and the case-set-bound evidence-package `$defs/hmac_metadata`; every per-entry complete
  evidence-package binding must reproduce that profile's domain/scheme/version/key ID;
- authoring/review dates;
- allowed checkpoint, reserve-batch ID/ordinal, and sealed-disclosure ordinal;
- the complete preapproved exclusion `$defs/hmac_reference`;
- disposition-policy ID/version and complete `$defs/hmac_reference`;
- disclosure class;
- `history_registry_id`, `history_genesis_attestation_sha256`, and
  `eligibility_history_head_sha256`; and
- suite commitment.

The manifest is a closed lane-discriminated `oneOf`: `open_regression` forbids disposition-policy,
history, reserve, and locked/sealed custody fields; both non-open lanes require them.

`case_count` counts every authored case in the committed suite, including preapproved exclusions;
it is not an eligible-only count. Current lifecycle state is derived only from the append-only event
chain. The manifest and its suite commitment never mutate to mirror current state; any truth or
manifest-content edit creates a new suite version.

Create `schemas/evaluation_suite_history_attestation.schema.json` for the public, non-truth-bearing
projection of an external custodian registry. Its closed `attestation_kind` enum is
`registry_genesis`, `reserve_batch`, `suite_reservation`, `consumption_claim`,
`consumption_claim_transfer`, `consumption_claim_burn`, `authority_conflict_preclaim_close`,
`scope_schedule_deadline_close`,
`truth_release_commit`, `post_outcome`, `report_recorded`, `post_adjudication`,
`corrected_report_recorded`, `slot_private_audit_closed`, `candidate_cycle_resolution`, and
`registry_continuity`. Every variant records
the global `history_registry_id`, registry version/revision, governance-policy version, opaque
`private_registry_commitment`, prior attestation hash, role/key IDs, cumulative disclosure counters, and the
applicable public slot state/budget deltas.
Every non-genesis variant also requires the immutable `history_genesis_attestation_sha256`.
Variant-specific schemas use `oneOf` and forbid every field not assigned to that variant. The
attestation value is secret-backed under Section 8.5.
Every public variant from `reserve_batch` onward forbids the complete storage plans/receipts, their
IDs/plain SHA-256 values, descriptor-manifest hashes, store metadata, and actual staged/reserved/used/
remaining record counts or bytes. Where storage binding applies, it carries only the two formula
versions, `evaluation_storage_reservation_commitment`, and the exact HMAC metadata defined in Section
8.5.

The head-independent `reserve_batch_subject` has exactly registry/genesis,
global slot, batch ID, the one future suite ID/version/lane/checkpoint/release-cycle/ordinal, the lane-
conditional complete `candidate_cycle_identity`, authored/
excluded/eligible counts, case-set and disposition-policy commitments/metadata, governance-policy
version, selected execution kind/contract ID/version/content SHA-256, common response-contract SHA-256,
static candidate-isolation-profile ID/version/content SHA-256, role IDs, and creation date. It
deliberately forbids any candidate-build resource manifest/hash, exact code/config/artifact/image
identity, or other future build-resolved value.
`reserve_batch_subject_sha256` is SHA-256 over its Canonical JSON v1 bytes. The subject forbids storage
plans/receipts/commitments, suite commitment/manifest/
fingerprint, future reservation/claim heads, private-registry commitment, attestation HMAC/value, and
its own digest.

`reserve_batch` commits the ordered, custodian-private set of disjoint future suite identities,
case-set commitments, checkpoint assignments, ordinals, and the preapproved disposition-policy commitment
after private storage preparation but before any `suite_reservation`, claim, dispatch, or result for
its global slot. Its CAS is allowed only when
that slot has no active reserve batch and sets one immutable `active_reserve_batch_id` plus
`active_reserve_batch_size: 1`, `next_reserve_ordinal: 0`, and
`reserve_batch_exhausted: false`. It also sets closed `reserve_batch_claim_gate_state`: `active` for
locked/candidate-cycle-0 slots or `dormant_conditional` for the preallocated candidate-cycle-1 child.
Here `active_reserve_batch_id` means that storage and case registration are durably activated; it does
not make a dormant child claim-eligible. The fixed public dormant state exists for every organizer
opportunity before parent output and therefore reveals no parent result or owner decision. Its
public projection exposes the subject fields/digest, both non-secret storage formula versions,
`evaluation_storage_reservation_commitment` and its HMAC metadata, plus the secret-backed
`private_registry_commitment`. Its CAS atomically activates the two prepared store allocations,
archive records/proofs, and private append. If that CAS loses, the unreachable prepared allocation is
abort-tombstoned and reclaimed without producing a history successor, fingerprint, claim, or usable
receipt. A per-slot batch contains exactly one
suite and each non-open suite at most 10,000 cases; schema and policy enforce both bounds.
No second/replacement batch or additional member can be registered for that slot; the sole suite is
the complete evaluation opportunity for that locked-checkpoint slot or exact candidate-cycle-specific
sealed slot. The shared organizer opportunity may contain only the separately preallocated ordinal-0
and ordinal-1 sealed slots defined above.
`suite_reservation` and claim require `reserve_batch_claim_gate_state: active`. Only the exact owner-
remediation resolution may atomically change a child batch from `dormant_conditional` to `active`; all
exact unused-child close branches, including owner-deadline expiry, change it to `terminal_unused` and
permanently forbid claim.
The batch explicitly forbids a future `suite_commitment`, manifest hash, or eligibility head because
those acyclic values depend on the later predicted reservation; only the listed pre-result facts are
frozen.
`suite_reservation` names exactly the current `next_reserve_ordinal`
batch member and records suite ID/version/lane/checkpoint, release-cycle ID, the lane-conditional
complete `candidate_cycle_identity`, batch/ordinal, immutable
case-set and disposition-policy commitments, selected execution kind/contract ID/version/content SHA-
256, common response-contract SHA-256, static candidate-isolation-profile ID/version/content SHA-256,
the exact `candidate_build_resource_manifest_sha256`, both
storage formula versions and the exact
`evaluation_storage_reservation_commitment` value plus the exact HMAC metadata defined in Section
8.5, plus booleans attesting no visible-seed overlap, no prior
locked/sealed overlap,
`case_truth_selection_not_derived_from_disclosed_results`, and no shared truth payload. That boolean
governs only suite/case/truth/evidence selection and derivation; it does not forbid the separately
authorized post-result candidate-build changes represented by the ordinal-1 remediation build subject
and change evidence. It is never committed alone: the
reservation and its matching `consumption_claim` are a two-revision atomic registry transaction. The
reservation revision preserves the prior `resulting_counters` byte-for-byte; the immediately following
claim revision alone advances the queue ordinal and slot state. Selecting the final ordinal also sets
`reserve_batch_exhausted: true`. Both revisions are stored or neither is.

`consumption_claim` records the immediately preceding paired suite-reservation head, global budget-slot
ID (the named locked-checkpoint slot or the sealed candidate cycle's exact `global_budget_slot_id`),
the lane-conditional complete `candidate_cycle_identity`,
candidate fingerprint, disposition-policy
ID/version/commitment and HMAC metadata, selected execution kind/contract ID/version/content SHA-256,
common response-contract SHA-256, static candidate-isolation-profile ID/version/content SHA-256,
`candidate_build_resource_manifest_sha256`, fresh run-
attempt ID, the two non-secret storage-reservation
formula versions, and `evaluation_storage_reservation_commitment` plus its HMAC metadata,
and `claim_state: active`, with zero truth-release/result-bearing deltas. The run-attempt ID names the
suite-run envelope, not an individual question request. A
  slot may be `free`, `authority_closed_preclaim`, `scope_deadline_closed_preclaim`, `active`,
`consumed_burned`, `truth_committed`, or
`closed_unused_conditional`, plus the transaction-local/non-current
`closing_unused_conditional` revision used only inside the atomic unused-child close suffix,
with at most one active owner. A truth-committed slot has the closed closure substate
`outcome_pending`, `report_pending`, or `reported`; result budget is consumed in all three, but only
`reported` permits an unrelated later reservation or continuity append. A first claim binds an empty
retired-token fence ledger. The atomic reservation/claim pair requires both `slot_state: free` and
`reserve_batch_claim_gate_state: active`, binds the exact empty inherited ledger, and atomically
rejects any recorded late-byte receipt before becoming active. For a sealed candidate cycle the same
claim CAS is the only transition that writes its authenticated cycle leaf to `active`: ordinal 0
proves `free -> active`, while ordinal 1 proves the immediately preceding owner-resolution-produced
`activation_authorized -> active` transition. The resolution revision alone consumes the unique
remediation-authorization leaf; the claim proves that exact ancestor and cannot consume it again.
Locked checkpoints have no candidate-cycle leaf. No later suite can claim that slot, and a
`closed_unused_conditional` slot can never return to `free`.

The retired-token fence ledger is a custodian-private, append-only object per global budget-slot ID,
not a caller-provided digest. Version `1.0.0` has exact root keys `ledger_version`,
`history_registry_id`, `global_budget_slot_id`, and `entries`. Entries are ordered by a contiguous
zero-based `retirement_sequence` and have exactly `suite_id`, `suite_version`, `run_attempt_id`,
`case_invocation_id`, `case_attempt_id`, `attempt_ordinal`, `candidate_invocation_id`, `close_kind`,
`transport_request_id`,
`output_channel_token_sha256`,
`output_sink_fence_epoch`, `attempt_transport_close_event_sha256`,
`attempt_transport_close_commitment`, and `tombstoned_at`. A first claim uses the exact empty projection
with `entries: []`. The sole successful transfer appends its newly tombstoned ordinal-0 token exactly
once before deriving the next commitment, with `close_kind: undispatched_token_closed` and a null
`transport_request_id`. A dispatched attempt can never enter this retry ledger. The producer may not
delete, reorder, replace, or deduplicate a prior entry.
Burn and truth-commit successors freeze the inherited value applicable at their CAS point. Section
8.5 defines the domain-separated commitment, key/version metadata, and producer/verifier ordering.
`consumption_claim_transfer` keeps the same slot, suite, and run-attempt ID. Its private append binds
the failed `case_invocation_id`, ordinal-0 case-attempt ID,
pre-egress infrastructure-attestation event hash and durable `attempt_transport_closed` event/HMAC receipt,
binds the prior and one-entry-extended retired-token ledger commitments, replaces only that case's
attempt ID with a fresh ordinal-1 case-attempt ID, preserves every other invocation/seal, and remains
active without releasing the slot. The public variant exposes only suite/slot/run identity, aggregate
zero-byte/one-retry assertions, commitments, and deltas—never invocation/attempt/request/channel IDs.
No
second transfer exists. The close receipt binds the exact inactive channel token, runner, attempt,
`request_dispatch_state: not_dispatched`, `egress_attempted: false`, null dispatch-receipt and
transport-request IDs, accepted-byte count zero, `candidate_output_observed: false`, and the output
sink's new closed-token/fence epoch. The transfer CAS rechecks that receipt, the absence of any
dispatch/outbox record, and the sink ledger at the same serialization point as the registry head.
The immutable root `run_binding_attestation` always retains the original winning claim head. In the
candidate-set, truth-commit, outcome, and report schemas, `consumption_claim_head_sha256` means the
exact current active owner head: the original claim for an unretried suite or the transfer head after
its one case retry. Validators never substitute the pre-transfer head for those later run-level
operations. Immutable case records sealed before transfer retain and validate their actual historical
claim/root-run-binding ancestry.

`truth_release_commit` is the only active-to-result-bearing-consumed transition and occurs before any
truth read, decryption, or delivery. It binds the active claim/transfer head, suite coordinates,
historical `eligibility_history_head_sha256`, candidate fingerprint, suite run-attempt ID,
consuming-event hash, run-binding-event hash, exact `candidate_attempt_set_sealed` event hash and
secret-backed candidate-attempt-set commitment, disposition-policy ID/version/commitment and HMAC
metadata, the two non-secret storage-reservation formula versions and the exact
`evaluation_storage_reservation_commitment` plus exact HMAC metadata,
global budget-slot ID, complete retired-token
fence-ledger HMAC reference, and the lowercase 64-hex SHA-256 of a fresh uniformly random 256-bit
release-fence token plus an opaque `truth_release_fence_recovery_record_id` and complete
`truth_release_fence_recovery_record_hmac_reference` from Section 8.5, plus authoritative clock identity
and authorization/capability/recovery start/deadline ticks plus their recomputed effective terminal
deadline tick. The HMAC-protected private append, never the public attestation, additionally binds the
same five reservation record descriptor IDs/lengths/SHAs plus current used/remaining allowances;
validators stream the canonical records instead of copying them. In the same atomic
custodian registry/capability transaction, the raw token is encrypted into that attempt-bound recovery
record, its nonce receipt/ciphertext/control descriptor is appended to the authoritative private-
control snapshot lineage, the prepaid allowance is decremented, and the current pointer advances
before the public history head advances. If any recovery record, snapshot, pointer, or allowance write
cannot be durably committed, the
CAS fails and no commit or budget increment exists. Its successful CAS increments the applicable
truth-release/result-bearing locked or sealed
budget exactly once and changes the slot irrevocably to `truth_committed` with closure substate
`outcome_pending`; the raw token is returned
only to that CAS winner or reissued from the same encrypted record to an authorized recovery of the
same immutable attempt. Every unwrap is audited, never creates a new token, and is never written to
history, logs, repository, or public artifacts. A truth store accepts
only that raw token after matching its hash, commit head, attempt, durable lifecycle authorization event,
recovery-record ID, candidate-attempt-set commitment, and current-or-descendant global history. Redemption
atomically succeeds only by changing the capability from `available` to
`redeemed_with_durable_truth_session`: the same transaction creates the exact truth-payload control
record and authenticated encrypted truth-session record from Section 8.5 for that immutable sealed
suite response set, verifies its AEAD/decrypted payload hash and bindings, consumes the prepaid
private-control allowance, appends the descriptor snapshots, advances the authoritative private-
control pointer, tombstones the raw token and recovery record, and issues/persists the domain-separated
terminal receipt/record that contains the complete session-record projection. Every listed write and
state transition commits or none does. The competing terminal operation changes `available`
to `revoked_without_delivery`, tombstones the token and recovery record without creating a truth
session, and issues its own domain-separated terminal receipt commitment. Redemption and revocation
serialize in the truth store
and exactly one can win; either terminal state rejects token replay. A transfer or burn cannot
succeed after this commit. A crash after the commit spends the slot and permits recovery of the same
attempt/outcome only, never another run. Before the effective truth-terminal deadline, the truth
store must redeem the already sealed candidate-attempt set whenever the transaction can succeed and
the fresh `truth_session_redeem` authority guard is allowed.
Transient or permanent store unavailability leaves the capability `available` and recovery blocked;
it never authorizes an early caller-selected revocation. At or after the deadline only
`truth_terminal_deadline_expired` is legal. Before it, only a byte-identical fresh authority binding
with decision `authority_conflict` and selector `authority_conflict_after_truth_commit` may revoke;
custodian discretion, store health, or candidate-output observation never may. Before terminalization it may not record an
outcome. After either
terminal receipt, it may neither dispatch another case request nor deliver truth again.

`post_outcome` records the prior `truth_release_commit` head, suite coordinates, historical
`eligibility_history_head_sha256`, final run-attempt ID, exact
`truth_release_authorization_event_sha256`, exact `truth_capability_terminal_event_sha256`, exact
`truth_release_fence_recovery_record_id`, exact
`truth_release_fence_recovery_record_hmac_reference`, and exact
`outcome_event_sha256` and `outcome_set_hmac_reference`, plus the candidate-attempt-set event hash and
complete HMAC reference already frozen by the commit
and the same disposition-policy commitment and retired-token fence-ledger commitment. Its HMAC-
protected private append also binds the atomic `output_sink_snapshot_watermark`/
`output_sink_ledger_head_commitment` pair. The public attestation carries only its ordinary revision-
specific `private_registry_commitment`; it forbids a standalone sink commitment, watermark, count,
late-byte field, or private-state marker whose equality or occurrence could reveal sink activity. It
requires `truth_capability_state`
(`redeemed_with_durable_truth_session` or
`revoked_without_delivery`) and the matching non-null complete
`truth_capability_terminal_receipt_hmac_reference`. The slot is already consumed; this variant records
zero new truth-release, result-bearing, locked, and sealed budget deltas and cannot create evaluation
budget. Its purpose is to make the outcome globally durable and auditable, not to perform the first
consumption. It cannot be appended while the capability remains `available`, and the global
resulting state maps each truth-release-commit head to exactly one deterministic post-outcome
receipt/source descriptor and hash; the resulting public history head is derived afterward and never
stored in that same leaf. A second receipt
for the same commit/outcome is rejected even after unrelated valid successors. The slot closure
substate changes atomically from `outcome_pending` to `report_pending`.

`report_recorded` is the required result-bearing closure after `post_outcome`. It records the exact
post-outcome head, outcome-set commitment, original `complete_public_report_sha256`, secret-backed private-report
commitment, disposition-policy ID/version/commitment and HMAC metadata,
`disclosure_authorized` event hash, terminal retirement/invalidation-event hash, durable
disclosure-outbox record ID, and zero new budget deltas. Its HMAC-protected private append contains
the complete schema-valid private-report control-record descriptor/hash and the head-independent
outbox record plus binary descriptor ID/length/SHA-256, never copied public-report bytes or the future
resulting head. It also binds the exact private human-governance registry/genesis and expected
predecessor head, scope-entry membership, exposure nonmembership, and the entry's required prior-
ordinal closure proofs. It explicitly forbids a completion record/descriptor and the resulting human-
governance head. A sealed ordinal-0 invalidated report is durable historical remediation evidence but
does not complete the scope; it binds the dormant child identity/base/batch and leaves that obligation
unresolved. A sealed ordinal-0 pass first computes/HMACs/hashes its complete `report_recorded`
attestation/head, then the same all-or-none transaction appends the parent-pass child resolution and
zero-channel audit closure and derives the unique human-scope completion from that audit head. A sealed
ordinal-1 report's repository projection requires the exact immutable ordinal-0
`remediation_predecessor_public_ref`; its private report/append additionally requires the matching
`remediation_predecessor_private_witness` and inserts the append-only remediation disclosure-
dependency leaf; its own
report head is the final scope-obligation head and derives completion. The child report can never hide,
replace, or merge the parent denominator. Earlier locked checkpoints and an ordinal-0 invalidated
report read-lock the expected human head unchanged. Report finalization holds one sink snapshot barrier while it creates
the disclosure-
authorization and terminal lifecycle events and atomically persists the history receipt plus those
descriptor-bound bytes in the append-only disclosure outbox. The receipt binds the authoritative sink
state only inside its HMAC-protected private append at that same serialization point; the public
receipt exposes no sink, scope, completion, or exposure field. A missing branch-required proof or
concurrent human-governance transition makes the transaction lose. Ingress cannot interpose a later
receipt between
report snapshot and CAS. External read access remains embargoed after this CAS: the transaction
durably persists the exact canonical outbox record and closure receipt but grants no external read
capability. Only the later `ReleaseActionTransaction.execute(enable_outbox)` may atomically persist the
matching signed verified-publication receipt and insert the immutable completed enable-action leaf;
the access gate derives readability from that leaf and no report-record or separate ACL bit is flipped. The authorization
event and `report_recorded` event never mean actual disclosure. For a sealed report, the same CAS verifies the candidate's prior sealed-disclosure head/
count and stores the exactly one-entry successor head/count defined below; locked/open receipts forbid
that delta. The same sealed CAS also proves the exact authenticated candidate-cycle `active` leaf and
replaces it with sequence + 1 `reported_pass` or `reported_invalidated`, chosen solely from the
precommitted disposition result and carrying the exact source `report_recorded` descriptor/hash;
locked/open reports forbid that index mutation. Global
state maps each post-outcome head to exactly one original report receipt/source descriptor and hash,
never that writer's resulting public history head, and keeps the result-bearing
slot `report_pending` until then; the successful receipt changes it to `reported`. A duplicate,
substituted report, or later reservation/continuity
while any result-bearing commit lacks post-outcome/report closure fails closed.

A private `output_sink_checkpoint` is a content-addressed private-history record summarizing one or
more already durable private sink-registry transitions; it is never a public history attestation or
public lifecycle event.
It binds the terminal suite/run/state branch, prior and exact new watermark/head pairs, strict positive
delta, and only newly added sequence-ordered content-free receipt descriptors/projections from prior
watermark + 1 through the new watermark and every matching `late_output_receipt_commitment`. Starting
from the prior head, the validator streams each delta once and recomputes the chained new sink-ledger
head. It never repeats a prior receipt prefix; commitments alone are insufficient. Raw bytes, lengths,
case IDs, and per-case outcomes remain forbidden.

Governance pins exactly one private sink-registry ID/genesis/current-head lineage per history
registry. Genesis alone has sequence zero/null predecessor; reset, fork, deletion, or alternate
genesis is invalid. The registry owns permanent coalescing-key/receipt-identity indexes plus per-slot
current watermark/head. Each receipt/checkpoint CASes that authoritative private head but advances no
public revision. Every already-required global successor holds one cross-store sink barrier and
atomically CASes both the expected global head and expected current sink head through outbox
visibility. Its private append streams every receipt since the prior privately bound sink head,
updates the authenticated `bound_sink_state` leaf, and rejects a gap, reorder, duplicate, or receipt
that wins between observation and CAS. The public successor exposes only its existing transition-
specific secret-backed `private_registry_commitment`; it forbids the bare deterministic sink head or
another value whose equality across revisions would disclose whether private sink state changed.

Every claimed terminal slot, including one with zero late receipts, has exactly one
`slot_private_audit_closed` successor at the first successful CAS on or after its precommitted
`slot_audit_not_before_tick`. Its public projection has only registry/slot identity, public-safe
`schedule_offset_profile_id`/version, zero budget deltas, its already registered suite-specific
`evaluation_storage_reservation_hmac_reference`, and its ordinary transition HMAC; it expressly
forbids the per-scope schedule ID/ref/descriptor/hash/ticks, receipt reason/count, watermark, sink head,
late-byte boolean, and a conditional marker. Its private append performs the same two-head CAS, binds the final private sink
state and destruction receipts, and proves every issued token/channel is irreversibly closed so no
further ingress can reach that sink lineage. A slot cannot authorize an organizer cycle or final
retention destruction before this unconditional closure. If physical ingress remains possible at the
deadline, the system stops without claiming closure; a byte after a claimed closure is a private
security incident and global stop condition, never another public per-slot failure marker.
Construction is acyclic: the system first computes/HMACs/hashes the audit-closure attestation, then
derives `private_audit_closed` from that attestation hash. One transaction CASes the global head,
private sink head and the independently read private-control pointer whose snapshot is the sole
authoritative non-open lifecycle-current head, and persists both objects plus that snapshot/pointer or
neither. Every later
organizer/continuity/retention transition requires both resulting heads. A backend that cannot make
the global-head/sink-head/private-control-pointer/outbox transaction linearizable fails the Phase 4 gate; a
sequential best-effort adapter is forbidden.

A candidate-cycle-1 slot closed while still `dormant_conditional` has never issued a run, token,
channel, or sink-current leaf. Its required audit successor therefore uses the closed
`never_activated_conditional` branch at immediate fixed schedule
`conditional_child_zero_channel_close_v1`: it reproduces the complete child candidate-cycle identity,
suite/base/batch IDs, resolution head, null run, proves nonmembership of every claim/token/ingress and
the sink-current leaf, inserts a zero-watermark closed sink leaf, and forbids any receipt/ledger step,
late-byte field, or destruction receipt for a nonexistent channel. Its private append requires
`terminal_close_pending_audit`, consumes only the pre-reserved final-record allowance, and atomically
changes the private-history allocation to `terminal_archive_sealed`; no intermediate H1 state is
externally usable because the full suffix commits all-or-none. The parent-pass, parent-pretruth-burn,
parent-withdrawal-only, or owner-decline transaction orders global revisions as the branch's parent
closure/adjudication when applicable ->
`candidate_cycle_resolution` -> this `slot_private_audit_closed`; it then derives
`human_scope_completion` from the audit-closure head. All global revisions, the sink close, allocation
tombstone/archive seal, and human completion are persisted by one multi-head CAS or none. Unlike a
claimed slot, this branch has no lifecycle chain or `private_audit_closed` lifecycle event; the typed
resolution plus zero-channel sink receipt is its exact equivalent continuity proof. Organizer/
retention transitions require that audit head just as they require the claimed-slot lifecycle pair.

An unconditional locked, P3 or candidate-cycle-0 slot closed before claim by either
`authority_conflict_preclaim_close` or `scope_schedule_deadline_close` uses the distinct closed
`audit_subject_kind: never_claimed_preclaim_close`. It carries exact lane/checkpoint and slot/suite or
complete candidate-cycle identity, preparation row and both allocation identities/states, selected
schedule ref, cause `authority_conflict|scope_schedule_deadline`, and the matching complete private
close-source descriptor/hash/head plus branch-exact authority binding or deadline transition. It
requires null run/token/channel/lifecycle identity, zero receipt sequence/watermark, null sink-ledger
HMAC, nonmembership of claim/dispatch/ingress/truth/result and the prior sink-current leaf, then inserts
the same zero-watermark permanently closed sink leaf. It forbids a conditional-child base/resolution,
receipt/ledger step, late-byte/destruction field and any cause not proved by the named close source.
The close source -> zero-channel audit -> allocation archive seal prefix is one prepaid multi-head
CAS. It appends `human_scope_completion` in that same CAS if and only if this close, plus the coupled
RC0-to-RC1 close when applicable, resolves the last outstanding scope obligation; an earlier P2/P3
close leaves completion absent and every later unconditional entry must still execute or meet its own
deadline. Like `never_activated_conditional`, this branch has no lifecycle event; a
fabricated `private_audit_closed` event for any never-claimed/no-channel audit is invalid.

The terminal retirement/invalidation event is not a discretionary reaction to a disclosed score. A
versioned, precommitted disposition policy mechanically selects it under embargo from the immutable
lane, checkpoint, candidate fingerprint, and reconciled outcome set. Locked result-bearing suites
retire. A sealed suite retires only when the precommitted release threshold accepts the unchanged
candidate; otherwise it invalidates. The owner cannot see the public report before that decision is
durably bound. Later tuning, rejection, withdrawal, or defect discovery appends the defined
`post_adjudication`/withdrawal metadata and may withdraw a release claim, but it never performs a forbidden
`retired -> invalidated` transition or reopens evaluation budget.

There is no `consumption_claim_release` variant and no pre-truth path back to free or into a reserve
replacement. A fingerprint change burns the one slot. `custodian_abort_after_claim` is legal only
before every dispatch/outbox/egress/ingress operation, with zero accepted bytes and an authenticated
`candidate_output_observed: false`; after any dispatch or candidate-output observation it is
forbidden. Otherwise the exact claimed suite remains active for deterministic recovery.
An ordinal-1 pre-egress infrastructure failure remains on that exact recoverable binding or burns the
slot; because no dispatch was committed, it is never fabricated as an attempted runtime outcome.
These rules prevent the custodian or system under test from advancing the hidden denominator by
manufacturing a zero-byte failure.

`authority_conflict_preclaim_close` is the only terminal successor when the current official guard
conflicts after the permanent slot/preparation row exists but before a claim. Because scope and every
slot preparation commit atomically, each affected scope entry must bind its already durable preparation
row and prepared-or-activated private-control/private-history allocations; only its `reserve_batch`
leaf may be absent. Its strict private source binds the exact rows, nullable reserve proofs,
allocations, suite preclaim
basis, human scope/obligation, subject/guard/state digests and current authority tuple. It also contains
an ordered `affected_scope_entries` suffix from the current ordinal through at most the remaining four
entries. No entry may omit its preparation/allocation or have a claim/dispatch/truth/result; an absent
reserve is proved by exact nonmembership at the observed current root. The public attestation carries only the ordinary
opaque registry commitment, affected slot/batch identities, state `authority_closed_preclaim`, generic
`terminal_control_failure`, and zero truth/result/disclosure deltas. One atomic global/human/slot/
allocation CAS makes every affected allocation `terminal_unused_tombstone`, changes every
affected slot to `authority_closed_preclaim`, and closes the whole suffix permanent non-PASS. For a
sealed ordinal-0 entry it also changes that cycle to `closed_authority_conflict` and its dormant child
to `closed_parent_authority_conflict`; every affected no-channel entry receives its direct zero-channel
audit, and the final audit head derives the unique human-scope completion. This forbids every later
reserve/claim/reuse while avoiding a stranded earlier locked or dormant-child obligation. It occupies
the same mutually exclusive prepaid terminal-history/control/audit slots already reserved for burn/
unused-child closure, so it adds no record-count maximum. A crash commits the ordered suffix or none;
a caller abort, store-health claim or candidate observation cannot select this branch.

`consumption_claim_burn` is the terminal fail-closed successor for an active claim/transfer when a
dispatched request cannot produce an authentic transport-close
receipt, when a closed-token byte is later observed, or when the transport/output-fence state cannot
be atomically reconciled. The HMAC-protected private append binds the affected prior attempts/current
owner, complete inherited fence ledger, content-free close/late receipt records, applicable
invalidation events, and exactly one closed reason: `transport_close_unproven`,
`late_output_after_close`, `fence_state_unreconciled`, `fingerprint_changed_after_claim`,
`custodian_abort_after_claim`, `pre_dispatch_infrastructure_exhausted`, `suite_deadline_expired`,
`provider_egress_fence_breach`, `candidate_response_run_budget_exceeded`,
`authority_conflict_before_egress`, `authority_conflict_incomplete_candidate_set`, or
`authority_conflict_before_truth_commit`. Each authority-conflict reason additionally binds the exact
subject/guard/state digests and independently current authority tuple described above. The public
variant binds
only suite/slot/run identity, opaque inherited fence/private-registry commitments, generic
`terminal_control_failure`, and zero truth-release/result-bearing deltas; it forbids the private
reason, receipt commitments/counts, watermark, late-byte boolean, and invalidation subtype. It changes
the slot to `consumed_burned` and permanently forbids
retry or another suite at that locked-checkpoint or exact candidate-cycle-specific sealed slot. Late bytes are rejected and quarantined
in a write-only custodian audit sink whose raw payload is inaccessible to the runner, curator,
custodian decision maker, implementer, and scorer in every current or future release cycle. The
content-free receipt and `late_byte_observed: true` exist only in private sink/history records; no
public object carries either. The encrypted raw sink has a policy-bound retention/destruction
schedule and no routine human
read path. Exceptional access requires a separately authorized non-implementation forensic role and
organizer/legal incident record; otherwise automatic destruction occurs while the opaque receipt
remains. If the burn CAS itself cannot be persisted, the slot remains in its prior nonterminal state and
is blocked rather than being assumed free.

For a sealed candidate cycle, that same burn CAS proves the exact authenticated `active` cycle leaf
and replaces it with sequence + 1 `burned` carrying the complete source burn attestation/event
descriptor/hash. An ordinal-0 pre-truth burn additionally computes the child's
`not_activated_parent_burn` resolution and zero-channel audit suffix described below; no caller may
write `burned` from `free` or `dormant_conditional`, substitute another parent, or omit the child
closure. Locked burns forbid a candidate-cycle index mutation.

The burn linearization also atomically advances the slot output-fence epoch and tombstones every live
current-owner channel token (at most one under the sequential dispatch rule). The burn record binds the
new epoch and aggregate close commitments. Any later byte under either an inherited retired token or
a formerly current token goes only to the write-only quarantine. If registry state and sink fencing
cannot advance together, no terminal burn is claimed; the prior state remains blocked.

The public `post_adjudication` records the adjudication event hash, exact
`target_public_report_sha256`, secret-backed `target_private_report_commitment`, target revision,
supersession-or-withdrawal decision, and `correction_expected`. It forbids
`target_private_report_sha256`. Its HMAC-protected private append contains that exact complete private
digest/commitment and the current private-report control-record descriptor ID/length/SHA-256. The
validator streams that record and recomputes the complete digest; it never inlines the report. It may
target only the global report-lineage map's current unsuperseded revision; the CAS records the target-
report-hash -> unique deterministic adjudication receipt/source
descriptor and hash; the resulting adjudication head is derived afterward and is not in that leaf. Only
`correction_expected: true` also contains the schema-valid correction-derivation and correction-
disclosure-delta record descriptors, complete corrected outcome-set projection/commitment, and
acyclic corrected-report subject defined below.
Validators recompute private hashes and the deterministic derivation rather than
trusting stored digests. A false branch is terminal for that correction workflow at `post_adjudication`,
although unrelated later history may extend it. A true branch requires the direct
`corrected_report_recorded` successor described next; those two revisions are precomputed and
committed as one atomic registry transaction under one sink snapshot barrier, or neither exists.
`corrected_report_recorded` is the direct successor of that `post_adjudication` head and publicly
records the final corrected public report hash, final corrected private-report commitment, and zero
disclosure-budget delta; its private append additionally binds the corrected private-report control-
record descriptor ID/length/SHA-256 and original/corrected outcome-index/root record descriptors. The
validator streams them and recomputes the final hash/commitments; the append never inlines a report or
outcome array. The
same paired CAS persists the corrected public bytes in the append-only disclosure outbox under embargo
without granting external read access. The corrected revision requires its own later
`ReleaseActionTransaction.execute(enable_outbox)` and distinct verified-publication receipt before it
becomes readable. The paired CAS updates the lineage map to exactly the next revision and
records the adjudication-head -> unique deterministic corrected-receipt source descriptor/hash mapping;
the corrected-receipt resulting head is external to that leaf. Replay, branching, skipped revision,
or a second correction from an old target fails closed.
`registry_continuity` has the sole closed reason `organizer_opportunity`; it records the applicable
dated decision reference
without resetting counters. `organizer_opportunity` additionally
requires a separately owner-attested and externally pinned `organizer_cycle_authorization` artifact. Its exact
projection binds unique `opportunity_id`, registry/genesis, nullable prior opportunity ID, the exact
ordered two distinct candidate-specific release-cycle IDs, attributable
official source/channel/date and source-artifact SHA-256, authorization timestamp, signer role/key ID,
closed `authority_verification_method` (`organizer_signature`, `authenticated_official_api`, or
`human_verified_archived_official_source`), its method-specific signature/API/archive/message-ID-or-URL
evidence, and the mandatory owner-authorization HMAC metadata/value from
Section 8.5. The repository owner attests an actual first-ranked organizer notice with a key domain
separate from every custodian key; the custodian history-HMAC key alone is never sufficient. The global
registry state has an append-only consumed-opportunity map, and the continuity CAS verifies the
external pin, owner HMAC, method-specific machine evidence when available, and consumes that
authorization exactly once. The same CAS must also consume a freshly independently read
`ActivationAuthorityWitnessModel`, validate its complete official-instruction/clock/submission chain
from the governance checkpoint, prove no current first-ranked one-attempt/no-retest/disclosure/freeze
conflict, and hold/recheck those three resource generations/tick with the five-registry transition.
The archived organizer authorization is evidence of scope, never evidence that it is still current.
opportunity exactly once. Missing, replayed, malformed, or mismatched authorization fails
mechanically. An owner HMAC proves accountable provenance, not organizer authenticity. When no
organizer signature or authenticated official API exists, Phase 4 must stop until the authorized
human verifies the archived artifact against the first-ranked official channel and records the exact
source/message evidence; Task 3 does not claim it can cryptographically detect an invented notice.
The authorization also requires a closed `official_remediation_compatibility_review` over those exact
source/message IDs and SHA-256 values. It contains reviewer role/tick, an ordered closed restriction-
code array (`one_attempt_only`, `no_correction`, `no_internal_retest`, or `other_explicit_conflict`),
and result `no_explicit_internal_remediation_conflict` or `explicit_conflict`; the no-conflict result
requires an empty array, and any restriction requires conflict. The HMAC binds this complete review.
Only a present no-conflict review may create the two internal candidate-cycle slots; missing/conflict
stops before the transition. This is accountable human semantic review, not cryptographic proof of
organizer meaning, and Phase 4 must still verify the archived first-ranked source.
`prior_organizer_opportunity_id` is null only for the first authorized successor whose predecessor is
the pinned genesis with no opportunity/release-cycle leaf. Every later authorization requires a non-
null prior ID equal to the authenticated current registry state's `current_organizer_opportunity_id`;
the new current value is the artifact's unique `opportunity_id`. The genesis current value is null. A
fabricated non-null first prior, later null prior, wrong-current-opportunity CAS, duplicate candidate-
specific release-cycle ID, or reuse of either release-cycle ID across opportunities is
invalid.

`$defs/conditional_child_selection_comparability_projection` is public-safe and contains exactly
version; the parent and child candidate-cycle identities; the identical selection-policy ID/version;
the two complete opaque case-set `$defs/hmac_reference` objects, plus the two complete opaque exclusion
`$defs/hmac_reference` objects; the required
disjointness/no-derivation policy version; and booleans asserting independently reviewed, disjoint,
non-derived selection. It forbids raw case/truth/evidence IDs, proof paths, people, scope/store
metadata, current/future heads, and its own digest. Its external binding is
`conditional_child_selection_comparability_sha256 = SHA256(b"FinProof/ConditionalChildSelectionComparability/v1\x00" || canonical_bytes(complete schema-valid projection))`.
This is deliberately a domain-separated SHA-256 over already public-safe policy identities and opaque
commitments, not an HMAC domain. Private validation still streams both complete case-set indexes,
requires their `selection_quota_projection` values byte-for-byte equal, requires every case-set/
exclusion binding byte-for-byte equal to the corresponding manifest/index object including all HMAC
metadata, and validates the underlying
registration, disjointness, derivation, review, and quota proofs; the public projection cannot
substitute for them.

`$defs/conditional_child_base` is the head-independent, pre-output record for candidate-cycle ordinal
1. It has exactly version; complete parent/child candidate-cycle identities; child suite/version,
case-set/exclusion commitments and reserve-batch subject SHA-256; immutable completed human-
review approval receipt descriptors/hashes; prospective scope-batch ID and entry ordinal; a closed
`conditional_child_public_build_basis`; the complete
`conditional_child_selection_comparability_projection` plus its exact external SHA-256, which binds
both case-set commitments while private validation proves their embedded quota projections byte-for-
byte equal, requires the same policy/version/quotas, and proves the child is independently curated
and disjoint;
the execution-contract class, common-response contract, static isolation/security template and safety-
floor hashes; source snapshot; evaluation/GoldenCase/response/scoring/governance schema hashes;
scoring rule, disposition, disclosure/K10/K5, denominator, timeout/clock, and storage-formula
identities; plus literal activation predicate
`parent_truth_committed_fully_reported_invalidated_audit_closed_and_owner_resolution`. It explicitly
forbids an enclosing human-curation-scope record/receipt/hash/head, actual candidate build/resource
manifest, correctable runtime/egress/scorer implementation identity, any parent result/report/
fingerprint, owner authorization, current/future head, or its own SHA. The scope record is built only
after this base and binds its descriptor/SHA plus the same approval receipt. This one-way order is
review approval -> conditional child base -> curation scope.
`conditional_child_base_sha256` is its external Canonical JSON v1 SHA-256. The child case set is
disjoint, fully reviewed, registered, and storage-reserved before parent dispatch and is never changed
after output.

`$defs/conditional_child_public_build_basis` is the public-safe subprojection with exactly the child
candidate-cycle identity, suite/version, opaque case-set/exclusion and reserve-subject
commitments, the complete public-safe `conditional_child_selection_comparability_projection` and
`conditional_child_selection_comparability_sha256`, execution-contract class/common-
response/static-isolation/safety-floor hashes, source snapshot, immutable evaluation/GoldenCase/
response/scoring/governance schema hashes, scoring rule, disposition, disclosure/K10/K5, denominator,
timeout/clock, and storage-formula identities. It contains no approval/scope descriptor, stable person,
private proof/store metadata, child truth/evidence record ID, current/future head, or own digest. The
full private base contains this exact subobject plus private governance evidence; public fingerprint
extension is defined only over this public-safe basis, never over the complete private base.

The common schema's strict `$defs/current_report_receipt_ref` has exactly report ID/revision,
complete public-report SHA-256, public private-report HMAC commitment plus registered metadata, outbox descriptor/hash,
`current_report_receipt_kind` (`report_recorded` or `corrected_report_recorded`), and the matching
receipt descriptor/hash/resulting head. The first kind requires an original current lineage revision;
the second requires a corrected current lineage revision and its exact correction predecessor/event/
head. In every use, the supplied authenticated report-lineage proof must show that exact revision is
current and unsuperseded. A generic `report receipt`, report ID alone, or an original receipt for a
current corrected revision is invalid.

`$defs/remediation_predecessor_public_ref` is the later-use, public-safe immutable ordinal-0 reference
assembled only after the successful owner-activation transaction. It contains exactly the report ID/
revision, complete public-report SHA-256, public private-report HMAC commitment and its registered
metadata, outbox descriptor/hash, original-or-corrected receipt kind and exact public receipt
descriptor/hash/resulting head that were present in the owner authorization's
`current_report_receipt_ref`; the complete opaque owner-remediation HMAC commitment/metadata; literal
action `activate`; complete parent/child candidate-cycle identities; and the public candidate-cycle-
resolution attestation hash/head. It forbids the private authorization/base/change-evidence record
descriptor or plain hash, stable-person proof, guarded-lineage proof descriptor/hash, private transition
source, scope metadata, and every child report/resulting head.

`$defs/remediation_predecessor_private_witness` is validation-only and never serialized in a public
report, public index key or activation-state leaf. It contains that exact public ref plus the complete
owner-authorization record descriptor/commitment, activation transaction's initial guarded parent-
lineage head and proof descriptors/hashes showing the revision was current and unsuperseded then, and
the private resolution source descriptor/hash. It is assembled after activation from existing bounded
archive records and the already durable public resolution attestation/head; it is not a newly persisted
self-hashed record and never contains a child report/resulting head. The child private report/append
binds those private components while its repository-disclosure pair carries only the public ref, and
validation proves their public projection byte-for-byte equal.

At child report/dependency validation, the frozen parent receipt and activation head must be
authenticated ancestors, but the parent report need not still be the current lineage revision. No
later corrected/withdrawn revision may be substituted. Release readiness separately requires the
ordinal-0 revision to remain current byte-for-byte and is permanently non-PASS after any later
adjudication/correction/supersession/withdrawal. This split lets an already-activated mandatory child
reach report-or-burn and scope completion without exposing private governance metadata or treating
stale parent facts as release-ready.

`$defs/adjudicated_target_report_receipt_ref` contains that exact byte-identical
`current_report_receipt_ref`, the transaction's initial guarded history head/revision and lineage
proof, plus the direct `post_adjudication(correction_expected: false)` descriptor/hash/resulting head.
It proves the target ref was current and unsuperseded at the initial pre-adjudication head; it
explicitly forbids requiring that ref to remain current at the later resolution head, where the direct
withdrawal has superseded it. Any non-direct adjudication, wrong guarded head, or target substitution
is invalid.

`$defs/activation_authority_read_attestation` is a strict three-branch, non-HMAC store attestation. Its
`official_instruction_current` branch signs exactly literal kind, resource/genesis IDs, CAS generation,
snapshot ID/byte length/SHA-256, store-monotonic version and the registered authority-ranking-policy
ID/version. Its `trusted_clock_current` branch signs exactly literal kind, resource/genesis IDs, CAS
generation, clock epoch, snapshot ID, current signed 64-bit monotonic nanosecond tick, current UTC nanosecond instant and
store-monotonic version. Its `submission_state_current` branch signs exactly literal kind, resource/
genesis IDs, CAS generation, state `not_submitted` or `submitted_frozen`, and branch-exact null/non-null
actual submission-event ID/receipt/head and signed 64-bit monotonic freeze tick. Every branch also
signs `prior_complete_attestation_sha256` (null only at its pinned generation-zero genesis) and requires
CAS generation/store-monotonic version to advance contiguously. All three use
`ED25519_STORE_ATTESTATION_V1`, a branch-specific pinned public-key
resource/key ID and canonical base64 64-byte signature. The exact signature messages are respectively
`b"FinProof/OfficialInstructionCurrent/v1\x00"`,
`b"FinProof/TrustedClockCurrent/v1\x00"`, or
`b"FinProof/SubmissionStateCurrent/v1\x00"` concatenated with Canonical JSON v1 bytes of the complete
branch projection. Scheme/version/key-resource/key ID remain inside that signed projection; only the
signature value is removed. Their complete-object SHA-256 is external and is
not signed inside itself. These signatures are asymmetric store attestations explicitly outside the
closed 27-domain HMAC registry; a plain digest, opaque alias, unregistered HMAC or cross-branch key is
invalid.

`$defs/submission_freeze_basis` prevents an owner/configured deadline from defining the gate. It
contains the exact first-ranked official deadline source/message/archive IDs and content SHA-256,
canonical RFC 3339 UTC deadline plus its integer UTC-nanosecond value, and the authenticated trusted-
clock epoch conversion record that maps that UTC instant to a monotonic effective tick using exact
signed-integer nanosecond addition/subtraction. The conversion record reproduces the exact trusted-
clock resource/genesis/epoch/snapshot ID and complete-attestation SHA-256 above; its formula is
`deadline_monotonic_tick = snapshot_monotonic_tick + (deadline_utc_ns - snapshot_utc_ns)` with checked
signed-64-bit operands/result and no floating point, timezone re-interpretation or alternate epoch. It
copies the current submission-state branch and,
only for `submitted_frozen`, requires the earlier immutable actual-submission-freeze event ID/receipt/
head and attested monotonic tick byte-for-byte; `not_submitted` requires those fields null. The
authoritative `submission_freeze_effective_tick` is the minimum of the recomputed official-deadline
tick and the current submitted/frozen event tick when present. If no authenticated first-ranked
deadline/mapping or current submission-state attestation exists, activation stops. Neither omission of
an existing event, a YAML/config tick nor a caller-selected later basis is legal.

`$defs/submission_freeze_authority_state` is the closed activation-time official-authority review,
not a caller boolean. It contains exactly its version; the complete official-instruction, trusted-
clock and submission-state `activation_authority_read_attestation` objects plus their external digests;
the ordered first-
ranked official source/message IDs and content SHA-256 values considered; the complete
`submission_freeze_basis`; checked tick; `activation_observed_tick`;
`no_newer_ranked_instruction_observed`; and state `not_effective` or `effective`. The activation CAS
read-locks all three independently supplied current resources in the same multi-resource transaction.
The ordinary candidate-cycle-resolution private append/history HMAC binds this fresh state; the earlier
owner HMAC expressly does not. `activation_observed_tick` must equal the checked tick and the
clock attestation's current tick, and the effective tick must equal the recomputed basis. A stale clock/
instruction snapshot or newer first-ranked instruction makes the CAS lose. `not_effective` requires
that activation tick to precede the effective tick and forbids every exception field. `effective`
requires one exact authenticated first-ranked organizer `post_freeze_change_authorization` artifact
with source/message/archive IDs and hashes, authenticity or recorded authorized-human verification
evidence, allowed component-path identities, applicable opportunity/candidate-cycle identity and time
bounds, and literal `explicitly_authorizes_this_remediation_build: true`; the activation tick must lie
inside those bounds and every changed build-resource/component path must be a member of that closed
allowlist. Missing, expired, scope-mismatched, lower-ranked, or owner-only permission is invalid. The
subobject contains no raw secret, future suite/claim/report/history head, or own digest. Phase 4 verifies
the Ed25519 signatures, real archive/current-pointer reads, clock and available organizer authenticity
evidence; Task 3 freezes the projections and fail-closed comparisons without claiming that a human-
reviewed message's meaning is cryptographically provable. This artifact may authorize custody and
construction of the named changed build, but the current schema intentionally contains no separate
authorization for post-freeze evaluation/results or a replacement schedule. Therefore an `effective`
state cannot make the already scoped `child_activate` transaction win: it deterministically selects
the nonactivation permanent non-PASS path. Actual post-freeze child evaluation would require a new
first-ranked organizer instruction, owner-approved offset profile/opportunity and re-frozen design;
component-path permission alone is insufficient.

Each activation-authority resource has a pinned resource/genesis/key and no reset/delete/fork path.
Official-instruction snapshots are append-only supersets of prior archived source/message identities;
a typed retraction may change ranking status only by adding a signed retraction record and can never
erase the earlier conflict/source bytes. Submission state has the sole edge
`not_submitted -> submitted_frozen`; its event/head/tick are immutable and no reverse transition exists.
Trusted-clock ticks/UTC instants are monotonic within the pinned epoch, and a new epoch requires an
explicit signed continuity record rather than a reset. The strict validation-only
`$defs/activation_authority_transition_manifest` contains, for each of the three resource kinds, the
complete generation-zero checkpoint attestation bytes/digest/generation/store version copied byte-for-
byte from the externally pinned deployment-trust-anchor manifest tuple and an
ordered array of zero through 4,096 transition descriptors with exact kind/resource/genesis,
generation, byte length and SHA-256. The descriptor arrays plus the cumulative canonical bytes of all
resolved checkpoint/transition records across the three resources are together at most 16,777,216
bytes, and each record is at most 1,048,576 bytes. The validator sums declared descriptor lengths and
rejects over-cap input before the first read/parse. The final descriptor must
resolve to the independently read current attestation unless checkpoint equals current. Chain records
and manifests are validation-only/private and forbidden from the owner HMAC/public resolution.

The validator independently loads the governance lock plus the owner-approved deployment trust-anchor
manifest and rejects any chain checkpoint that is not byte-identical to its named tuple; the transition
manifest cannot nominate its own trust anchor.
`ActivationAuthorityTransitionReader` streams exactly those immutable canonical attestation/transition-
receipt bytes by descriptor/hash. The activation witness checks every literal signature tag and pinned
asymmetric-registry row, prior complete-attestation digest, contiguous generation/store version,
official-snapshot append/retraction rule, one-way submission-state edge and clock epoch/tick continuity
from checkpoint through the independently read current object. It then acquires one common activation-
authority read-lock receipt over all three current generations plus the observed clock tick and holds or
atomically rechecks it through activation CAS. A fresh genesis, truncated/extra/reordered chain,
rollback, omitted conflict/event, reverse submission edge, clock epoch substitution or current object
that does not equal the manifest terminus fails before owner activation.

The signer-expiry path uses the narrower strict `$defs/trusted_clock_current_witness`, never the full
three-resource activation witness. It contains exactly the deployment-pinned trusted-clock generation-
zero tuple, one ordered clock-only transition-descriptor manifest, the complete observed current clock
attestation/current-store receipt, and the observed tick. `TrustedClockCurrentResourceReader.read_current()`
takes no caller argument and independently obtains the real current attestation/current-store receipt
for the manifest-pinned clock resource/genesis; every validator byte-compares the witness terminus to
that return and holds or rechecks its generation through the signer/deadline CAS.
`TrustedClockTransitionReader` streams only
that bounded clock lineage and verifies the same tag, prior-digest, generation/store-version, epoch and
monotonic-tick rules. Official-instruction, submission-state and derived freeze fields are forbidden.
This witness proves the signer observed `issued <= tick < expires`; later activation separately uses
the fresh full `ActivationAuthorityWitnessModel` and also requires the signed request still unexpired.

The canonical official-instruction bytes are not an opaque snapshot label. Strict
`$defs/official_instruction_snapshot`, `$defs/official_instruction_record` and
`$defs/official_instruction_semantic_review_record` contain exactly archive/snapshot versions,
content-addressed source/message descriptors and hashes, authenticated issue/effective/expiry ticks,
source-authenticity evidence, target scope selectors, and one closed effect. Effects are
`stop_all_non_open`, `new_opportunity_forbidden`, `internal_evaluation_forbidden`,
`retest_forbidden`, `truth_release_forbidden`, `correction_forbidden`, `disclosure_forbidden`,
`submission_forbidden`, `post_freeze_build_change_forbidden`, or `retract_exact_record`.
`retract_exact_record` names one prior record and never deletes its bytes. Natural-language official
text additionally requires the exact signed semantic-review record containing reviewer authority/
identity, source descriptor/hash, selected effect/scope and review tick. Its strict signature subobject
contains purpose `official_instruction_semantic_review`, scheme/version
`ED25519_OWNER_APPROVAL_V1`, the out-of-band deployment-dossier-pinned repository-owner official-
instruction-review key role/resource/key ID/public-key fingerprint, and one canonical base64 64-byte
signature over
`b"FinProof/OfficialInstructionSemanticReview/v1\x00" || canonical_bytes(record_without_signature)`.
The owner stable-person attestation must be independently current and distinct from the combined
curator/reviewer/custodian; the store snapshot signature alone cannot substitute for this review
signature. Effect, scope, source hash, tick, reviewer or key mutation invalidates the record. Ambiguity or an
unsupported interpretation is itself a conflict, never an allow. The independently read current
snapshot contains the complete append-only ordered record inventory and semantic-review descriptors.
Validation first filters active, unexpired, unretracted records whose target selector matches the
pending action, then applies source precedence from Section 1 and signed issue/order ticks; any active
applicable prohibition wins unless a later same-or-higher-authority record explicitly retracts it.
An unrelated action/scope record cannot block or permit the transaction. The archive reader streams
these exact bytes under the transition record/count/aggregate caps, and no caller boolean, free-form
label or missing review can determine applicability. The deterministic filtered view is the strict
`$defs/official_instruction_applicability_manifest`: manifest/action-subject versions and digest,
snapshot descriptor/hash, applicable count, ordered zero-through-4,096 active record plus semantic-
review descriptors/hashes, and a domain-separated ordered descriptor-list SHA-256. The ordered list is
exactly an array of strict `{instruction_record_descriptor, semantic_review_record_descriptor}` pairs;
the review member is required for natural-language instructions and is JSON `null` only for a machine-
typed official record that requires no semantic review. Its root is exactly
`SHA256(b"FinProof/OfficialInstructionApplicabilityList/v1\x00" ||
canonical_bytes(exact_ordered_descriptor_pair_array))`. Flattening the pairs, concatenating digests,
changing the tag, or using another pair-boundary encoding is invalid. The manifest forbids the
authority decision, guard and future action head; its complete descriptor/hash is external. The
validator regenerates it and this exact root from the archived snapshot for every action, checks the
16,777,216-byte cap before the first record read, and the archive reader can reproduce the same bytes
after a crash.

The governance lock carries this exhaustive effect-to-action applicability table; scope selectors are
matched before the row is applied and an omitted action is not affected by that effect:

| effect | exact affected action kinds |
|---|---|
| `stop_all_non_open` | all sixteen kinds below |
| `new_opportunity_forbidden` | `opportunity_create` |
| `internal_evaluation_forbidden` | `review_access`, `scope_and_slot_prepare_commit`, `reserve_batch`, `claim`, `dispatch`, `truth_release_commit`, `truth_session_redeem`, `scoring_start`, `outcome_finalize`, `true_correction`, `child_activate` |
| `retest_forbidden` | only `claim` with `claim_operation: transfer`, `dispatch` with exact invocation `attempt_ordinal == 1`, aggregate truth/redemption/scoring/outcome subjects with derived `suite_retry_used: true`, and `reserve_batch`/`claim`/`dispatch`/truth/scoring/outcome/`child_activate` whose complete candidate-cycle identity has ordinal 1 |
| `truth_release_forbidden` | `truth_release_commit`, `truth_session_redeem` |
| `correction_forbidden` | `true_correction` |
| `disclosure_forbidden` | `enable_outbox`, `release_readiness`, `internal_submission_package`, `outbox_read` |
| `submission_forbidden` | `internal_submission_package` |
| `post_freeze_build_change_forbidden` | `child_activate` only when its exact build-change set is nonempty |
| `retract_exact_record` | no action directly; it deactivates only its exact named prior record before the table is evaluated |

The `retest_forbidden` predicate is part of the strict applicability-manifest entry, not a reviewer
annotation. `candidate_attempt_set_projection` derives and binds exact
`retry_ledger_count: 0|1` from the sole legal transfer/retry graph and
`suite_retry_used == (retry_ledger_count == 1)`. Every truth-release, redemption, scoring-start and
outcome-finalize subject byte-reproduces those values from the authenticated candidate-attempt set;
an individual dispatch instead uses its own exact attempt ordinal. An ordinal-0 initial execution with
only attempt ordinal 0 is unaffected, while either the one in-suite infrastructure retry/claim
transfer or the conditional remediation child is blocked.
`no_internal_retest` in the organizer compatibility review maps to both predicate branches. The
validator generates every effect/action boundary from this table. A wildcard scope is explicit;
otherwise registry/opportunity/cycle/checkpoint/suite selectors must all match byte-for-byte. Source
precedence, retraction, expiry and ambiguity are evaluated before this table and never inferred from
the action name.

The head-independent strict `$defs/scope_and_slot_prepare_basis_projection` is built before the
combined authority subject. It contains exactly basis/version, predecessor human/slot-preparation/
allocation resource identities, stable principal attestation, the already content-addressed candidate
scope record descriptor/SHA-256, the exact complete schedule-record descriptor/hash and for each entry
its byte-identical selected `evaluation_scope_terminal_schedule_ref`, ordered approval descriptors and scope-entry content, and for each
entry the complete `suite_preclaim_basis` reproducing that scope SHA, deterministic preparation/batch/
suite/case-set/candidate-cycle identities, distinct private-control and private-history reservation-plan
SHA-256 values, and the exact two `(store_id, allocation_id, allocation_kind)` identities. It rejects
swapped/duplicated/kind-mismatched pairs. It forbids the candidate human state/head,
the authority subject/state/guard/binding, every slot-preparation source/row/root/receipt/head/pointer,
every storage receipt or post-allocation confirmation, every resulting allocation state, and every
future reserve/claim/result. Its digest is exactly
`SHA256(b"FinProof/ScopeAndSlotPrepareBasis/v1\x00" || canonical_bytes(basis_projection))`.

Every non-open irreversible action uses strict validation-only
`$defs/non_open_irreversible_action_subject`,
`$defs/non_open_irreversible_action_authority_state`, and
`$defs/non_open_irreversible_action_authority_guard`; no locked checkpoint or already claimed suite is
grandfathered. The subject is a closed `oneOf` over `opportunity_create`, `review_access`,
`scope_and_slot_prepare_commit`, `reserve_batch`, `claim`, `dispatch`, `truth_release_commit`,
`truth_session_redeem`, `scoring_start`, `outcome_finalize`, `true_correction`, `child_activate`,
`enable_outbox`, `release_readiness`, `internal_submission_package`, or `outbox_read`. Common fields
are subject version, action kind/lane, deployment/
governance/resource/genesis identities and exact already-current predecessor tuples. Branch fields are
exactly: authorization/opportunity identities for opportunity; authenticated human-review session/
stable-principal, suite/case-set/evidence descriptor and observed human/identity predecessors for
review access; the complete head-independent
`scope_and_slot_prepare_basis_projection` plus its tagged digest for scope-and-preparation; reserve/slot/
suite/fingerprint/disjointness and exact `claim_operation: initial|transfer` plus transfer/attempt
ordinal when applicable and
history/control predecessors for claim; run/case/invocation/attempt/request and control/ingress
predecessors for dispatch; candidate-set event/HMAC-reference and history/control predecessors for
truth commit; commit/token-hash/recovery/capability/control predecessors for redemption; current
truth-session/terminal receipt, scorer/rule/lease and predecessor control/outcome heads for scoring and
outcome finalization; current
report/revision/hash, enable-action identity and correction-delta/adjudication subjects for correction;
owner authorization/child-base/build/parent-receipt predecessors for activation; and deterministic
release-action identity/request/dossier/target plus observed release-action predecessor for the three
release branches; and report/revision/outbox, complete authenticated access-context digest, enable
identity, branch kind, nullable readiness identity (required only for `anonymous_current`) and current
authority/five-registry/identity/release-action predecessors for `outbox_read`.
It forbids raw tokens, truth/result bytes, the guard, its own digest and every resulting/future head.
The scope-and-preparation branch requires the same candidate scope descriptor/SHA from that basis but
forbids any candidate human state/head, authority-binding copy, slot/storage receipt descriptor/hash,
candidate slot root/head and resulting
allocation state. Its digest is exactly
`SHA256(b"FinProof/NonOpenIrreversibleActionSubject/v1\x00" || canonical_bytes(subject))`.
The strict private `$defs/irreversible_action_authority_binding` contains exactly binding version, the
complete subject, authority state and guard objects, plus their three lowercase-64-hex fields
`non_open_irreversible_action_subject_sha256`,
`complete_non_open_irreversible_action_authority_state_sha256`, and
`complete_non_open_irreversible_action_authority_guard_sha256`. The latter two are exactly SHA-256 of
Canonical JSON v1 bytes of the complete strict state and guard respectively, after schema/cap
validation and with no omitted field; the subject uses the tagged formula above. The binding byte-
compares every nested/copied digest and contains no public alias, descriptor indirection, result or
future head. It is capped at 262,144 bytes and is durably embedded in the already prepaid private
HMAC/signature-protected owning action record; it is never a transient hash with a lost preimage.
Every owning projection below carries this byte-identical subobject.

The authority state contains exactly that derived digest/action kind/lane, the complete freshly
validated official-instruction snapshot digest and the applicability-manifest descriptor/count/list-
root/complete hash (never its potentially 4,096 inline descriptors), the
three independently current authority-resource generations/tick, the complete bounded common read-
lock receipt plus its recomputed digest, and one closed freeze-time branch. `pre_scope` contains the
complete freshly recomputed `submission_freeze_basis`, its effective tick and observed tick, requires
the latter strictly earlier, and forbids a schedule ref/stored bound. `scheduled_action` contains the
byte-identical selected `evaluation_scope_terminal_schedule_ref`, the stored schedule
`submission_freeze_effective_tick`, the complete freshly recomputed current basis/current effective
tick, exact `effective_bound = min(stored_effective_tick, current_effective_tick)`, observed tick and
comparison `before_effective|at_or_after_effective`. It additionally contains the closed
artifact/freeze branch and decision `allowed` or `authority_conflict` with one safe-terminal selector;
only an already typed no-new-result cleanup action may be `allowed` at-or-after-effective. The guard
byte-reproduces the schedule-ref/null branch, current-basis digest, effective bound and comparison, so
the durable complete authority binding and its existing HMAC/signature owner authenticate every one of
these fields.
Ordinary evaluation of an exact candidate/fingerprint/artifact pinned before the submission-freeze
effective tick uses `prefreeze_artifact_unchanged`, but that provenance label never permits a
result-bearing action at or after the freshly recomputed current effective freeze tick. Every such
subject/state/guard carries the complete current `submission_freeze_basis` and the minimum stored/
current effective bound required by the schedule contract above. `postfreeze_unchanged_reporting`
permits only verification, immutable archive custody, and serving bytes that were already durably
reported before the bound; it forbids creating or changing a report, outcome, correction, readiness or
submission package and still applies every action-specific official restriction. Only
`child_activate` may carry `postfreeze_changed_build_exception` as validation evidence, and it must
reproduce the complete `submission_freeze_authority_state` plus exact organizer exception/change
allowlist, but within this frozen schedule that branch's decision is necessarily
`authority_conflict`/nonactivation as above; no other action
reinterprets that activation-only state. A true correction applies `correction_forbidden`; disclosure/
readiness/package apply `disclosure_forbidden`/`submission_forbidden`; and every build-changing branch
applies `post_freeze_build_change_forbidden`. The guard contains the complete authority-state digest,
subject digest, observed tuples and decision, but forbids a caller decision, owner HMAC, truth/result
bytes, future head and own digest. Subject, state and guard are each capped at 65,536 bytes.

`non_open_irreversible_action_authority_guard_errors` accepts the complete typed subject—not a caller-
supplied digest—canonicalizes and hashes it internally, derives kind/lane and the action-specific state
from the independently current `ActivationAuthorityWitnessModel`, transition reader and official
archive reader, and holds or atomically rechecks all three observed generations/tick through the action
CAS. The pending transaction byte-compares the same subject and embeds the complete byte-identical
`irreversible_action_authority_binding` inside an already authenticated private object as follows:
opportunity/scope-and-preparation/reserve/claim/true-correction/child-resolution in their strict
history or human-governance source projection; dispatch in
`case_dispatch_projection`; truth commit in `history_projection` and `recovery_record_projection`;
redemption/revocation in `truth_capability_terminal_projection`; scoring start/outcome finalization in
the scoring-work/finalization and `outcome_set_projection` records; and the three release actions in
`release_action_completion_basis` and the signed release-action leaf. These fields are mandatory parts
of the named existing HMAC/signature projections, use no new HMAC domain, remain private, and are
forbidden from every public report/artifact. `review_access` is a validation-only guarded read; its
start/end bindings are retained only in the private human-review authority-interval receipt described
below. Open-regression paths require subject/guard/witness/readers
null. The generator proves every augmented maximum object still fits its existing per-kind cap and
prepaid record slot.

All locked and sealed opportunity creation, every hidden human-review access, atomic scope-and-slot-preparation commit, `reserve_batch`,
claim, each pre-egress dispatch, truth-release commit/redemption, true correction, child activation and
release action route through that exact validator. Scoring start and outcome finalization use it too;
`outbox_read` uses the same typed subject/state/guard under the gate's held read without creating a
durable action record. Conflict handling is state-discriminated. Before a
durable preparation/reserve, the action writes nothing and abort-tombstones only reversible prepared
allocations. If a permanent preparation row or active reserve exists without a claim, one mutually
exclusive typed `authority_conflict_preclaim_close` history/human-governance transition changes the
slot to `authority_closed_preclaim`, makes the allocation `terminal_unused_tombstone`, closes its scope
obligation non-PASS with zero truth/result/disclosure delta and forbids reuse; it occupies the same
prepaid terminal slot as a later burn. After claim but before any dispatch,
`consumption_claim_burn(reason=authority_conflict_before_egress)` wins with no dispatch. After any
dispatch/terminal attempt prefix but before the complete candidate-attempt-set seal,
`consumption_claim_burn(reason=authority_conflict_incomplete_candidate_set)` atomically fences current
transport/ingress, preserves the immutable attempt/retired-token prefix, forbids later dispatch/retry/
truth and closes non-PASS. After complete candidate seal but before `truth_release_commit`,
`consumption_claim_burn(reason=authority_conflict_before_truth_commit)` creates no capability/recovery
record. Only after an allowed truth commit has created an `available` capability may a redemption-
guard conflict win the ordinary truth-store terminal transaction with reason
`authority_conflict_after_truth_commit`, tombstone token/recovery, create no truth session/decrypt and
produce the existing authenticated terminal receipt. After an already redeemed durable truth session,
a conflict at `scoring_start` or `outcome_finalize` selects only
`authority_conflict_after_truth_delivery`: it forbids a new scorer call or favorable/unfavorable score,
seals any existing private scoring prefix as unusable, and atomically creates the uniform eligible-
count `evaluation_error/AUTHORITY_RESTRICTION` outcome with `scoring_completion_state:
evaluation_error`, the exact authority binding and permanent invalidated disposition. No truth/session
byte, score or private cause becomes public; only ordinary audit/embargoed non-PASS reporting may
continue. A true correction becomes
`correction_expected:false` withdrawal; child activation becomes the exact nonactivation/zero-channel
closure; and enable/readiness/internal-package returns rejected with no public write. Caller/store-
health/output observation cannot manufacture these branches. Terminal audit/reporting of immutable
failure evidence remains legal but cannot dispatch, decrypt or expose new bytes.

`$defs/owner_remediation_authorization` is the one canonical, secret-backed owner decision for that
base, with literal purpose `corrected_release_candidate_cycle`, action `activate` or `decline`, and
exact registry/genesis/opportunity/parent-child identities. It binds the child-base SHA-256; the
complete child-base record descriptor; its exact public-build-basis subprojection; the
parent's exact `current_report_receipt_ref`, outcome-set/candidate-set commitments,
freeze-fingerprint SHA-256, terminal
capability and branch-conditional scoring-finalization state, disposition `invalidated`, and fixed-
schedule audit-closure head; plus a closed trigger `oneOf`. `candidate_quality_failure` requires
redeemed truth, normally finalized scoring, and the precommitted threshold/rule's invalidated result.
`post_truth_control_failure` requires the exact authenticated `revoked_without_delivery` or scored
`evaluation_error`/objective-control-cause projection and forbids pretending normal quality scoring.
Both require a fully recorded invalidated parent and closed audit. The authorization additionally
binds owner role/stable-person attestation, an identity-authority non-alias proof against the exact
curator principal, owner key/tick, and the HMAC metadata/value from Section 8.5. Distinct role labels,
pseudonyms, or HMAC keys alone do not establish a different human. The authorizing repository-owner
person/key must be externally attested and distinct from the combined curator/reviewer/custodian
principal and every organizer/custodian HMAC key. It sees only the already readable public report and
secret-backed public commitments, never raw private report/outcome bytes, a plain private-report
digest, child truth, or suppressed failure detail. The trigger is recomputed only from those exact
authenticated terminal/outcome/scoring receipts; a free-form or caller-supplied remediation-cause
adjudication is invalid. The activation CAS additionally proves the bound parent revision is the
current unsuperseded report-lineage leaf with no pending adjudication/correction and freezes the exact
inputs from which the later `remediation_predecessor_public_ref` and private witness are assembled as
the child's immutable remediation predecessor. Any later adjudication, correction,
supersession, or withdrawal of that parent revision makes the organizer opportunity permanently
non-PASS for release readiness; it remains visible historical evidence but never rewrites this
ancestry, reauthorizes the child, or permits a replacement.

The owner-controlled key is non-exportable and usable only through the closed
`owner_remediation_blind_signer_v1` service. Its strict
`$defs/owner_remediation_public_decision_request` contains exactly request version/ID, a fresh random
256-bit nonce, issued/expiry trusted-clock identity/ticks, owner stable-person/key identity, purpose/
action, opportunity/candidate identities, current public report ref/opaque commitments, the child
base's public-build-basis subprojection, immutable first-ranked organizer exception artifact/policy
references when applicable, and one fixed-length opaque
`private_join_commitment`. It forbids every private descriptor, length, record kind, trigger detail,
child truth or suppressed cell. `$defs/owner_remediation_public_approval_attestation` contains that
request's complete bytes/SHA-256, literal `ED25519_OWNER_APPROVAL_V1`, pinned owner-approval key resource/
key ID/fingerprint and a canonical base64 64-byte signature over
`b"FinProof/OwnerRemediationPublicApproval/v1\x00" || canonical_bytes(request)`; the approved owner
principal must equal the non-alias proof in the authorization.
The request/result action is a strict `oneOf`: `activate` requires corrected-build/change-path identities
and any immutable organizer-exception artifact/allowed-path basis the owner intends to rely on, while
`decline` forbids every corrected-build/change/exception field. The request expressly forbids current
official-instruction/clock/submission attestations, current ticks/generations and a caller-computed
freeze state. It is a head-independent human decision basis; UI-only context outside this signed object
cannot authorize either branch.

The separately ACL-isolated custodian channel supplies strict
`$defs/owner_remediation_private_join` with exactly `{version, request_id, nonce,
owner_remediation_private_join_commitment_projection, private_join_commitment}`. Its strict projection
reproduces every public request field except `private_join_commitment`, request bytes/hash/signature and
every result/future digest; it adds the complete private child-base/trigger/change-evidence descriptors,
mechanically verified lineage/immutable authority-policy/exception inputs, and one custodian-generated
`private_join_blinding_salt_hex` containing exactly 32 uniformly random bytes as 64 lowercase hex
characters. The salt is generated and durably retained before the public commitment is emitted, is
reused only for recovery of that same request ID/nonce, and is forbidden from every public request,
approval, signer result, acknowledgement, log, UI and repository artifact. Reuse across requests,
caller selection, all-zero/nonrandom salt, substitution on recovery or salt disclosure is invalid.
The wrapper and projection explicitly forbid every transient current official-instruction/clock/
submission attestation, generation, tick, read receipt or derived freeze state. The wrapper carries the
computed commitment and request ID/nonce for correlation, but neither wrapper-only field re-enters the
commitment projection. The service never returns private fields.

The canonical commitment projection is at most 4,194,296 bytes. Let `P = 4,194,304` and `L` be its byte
length; the padded preimage is derived transiently and exactly as
`uint64_be(L) || canonical_projection_bytes || 0x00 * (P - 8 - L)`. It is never a serialized wrapper
field, record member or separately stored blob. The commitment is
`SHA256(b"FinProof/OwnerRemediationPrivateJoin/v1\x00" || padded_preimage)`. A nonzero pad byte,
alternate length encoding, `L > P - 8`, omitted nonce/salt or noncanonical join is invalid. The complete
strict wrapper is capped at `max_owner_remediation_private_join_bytes: 4195328` before parsing; its
projection is separately capped before canonicalization and padding. The public request is capped at
262,144 bytes, owner approval at 524,288, signer result at 524,288, and the consumption receipt/state
witness at 1,048,576 each before parsing. Fixed padding hides descriptor kind/count/length, while the
private uniformly random salt prevents offline enumeration and cross-request equality testing of
low-entropy private alternatives without adding an HMAC domain.

The signer has a strict private `$defs/owner_remediation_signer_state` with signer resource/genesis,
contiguous sequence, consumed-request count and authenticated consumed-key root. Genesis is exactly
`SHA256(b"FinProof/OwnerRemediationSignerGenesis/v1\x00" || canonical_bytes({resource_id, store_id,
service_attestation_sha256, deployment_anchor_role: "owner-remediation-signer-current", version:
"1"}))`;
generation zero
has sequence/count zero and the domain-separated empty root. Only Phase-4 deployment provisioning may
create absent -> generation zero, and its complete attestation is bound in the deployment manifest.

The strict `$defs/owner_remediation_signer_current_attestation` has exactly resource/genesis/store,
CAS generation, state sequence/count/complete-state SHA-256/root, store-monotonic epoch/version,
`prior_complete_attestation_sha256` (null only at generation zero), literal
`ED25519_STORE_ATTESTATION_V1`, deployment-pinned key resource/key ID and canonical base64 64-byte
signature. Generation/store version advance contiguously; epoch/resource/genesis/key never change. Its
message is exactly `b"FinProof/OwnerRemediationSignerCurrent/v1\x00" ||
canonical_bytes(signed_projection)` with only signature removed; complete-object SHA-256 is external.
The state/attestation forbid consume receipts, authorization HMAC/results and their digests.
`$defs/owner_remediation_signer_state_witness` carries the
independently read prior state/pointer/current-store receipt, old-root nonmembership proof, candidate
leaf/new-root/state and candidate pointer; `OwnerRemediationSignerStoreReader` reads the real current
resource and bounded proof bytes, never a caller-selected ancestor. Starting from the observed state,
the signer builds the consumed leaf/root/candidate state, then the candidate current-pointer attestation
that binds only that state and expressly forbids the consume receipt, authorization HMAC/result and their
digests. The later consume receipt reproduces the observed/candidate sequence, roots and state/pointer
digests. Receipt/HMAC/result/state/pointer persist in one atomic CAS; reset/fork/duplicate consume is
invalid.

Blind signing consumes the owner-approved stable decision and may finish before the later activation
transaction. Neither its preclaim basis, final owner authorization HMAC nor result contains a transient
official-instruction/clock/submission attestation, generation, current-read receipt, observed tick or
derived freeze state. For `activate`, the later candidate-cycle-resolution transaction independently
obtains and locks a fresh `ActivationAuthorityWitnessModel`; its ordinary private append and suite-
history/history-attestation HMACs bind the complete fresh authority state, the consumed signer-result
reference and request expiry. The same three generations/tick remain locked or are atomically rechecked
through the resolution/reservation/claim group. `decline` independently reads only the current trusted
clock to enforce request expiry and forbids an activate-only authority state. If approval latency reaches
the current effective freeze bound or a newer instruction appears, activation fails unconditionally in
this scope and selects the permanent nonactivation non-PASS path. An immutable exception artifact/path
basis is retained only as diagnostic evidence and cannot extend the stored schedule or make the atomic
resolution/reservation/claim group win; a later authorized evaluation requires a new re-frozen
opportunity/scope. No stale owner signature is reinterpreted as fresh authority.

The strict `$defs/owner_remediation_authorization_preclaim_basis_projection` contains exactly the
stable intended authorization fields enumerated above plus the exact registered root `attestation`
HMAC metadata, and forbids the consume receipt, signer result/result digest, only the root
`attestation.value`, every transient authority-current field and its own
`owner_remediation_authorization_preclaim_basis_sha256`. The signer first computes
`owner_remediation_authorization_preclaim_basis_sha256 = SHA256(canonical_bytes(
owner_remediation_authorization_preclaim_basis_projection))`. The final authorization is the exact
fieldwise extension of that projection with this digest, the complete consumption-receipt descriptor/
hash and final `attestation.value`; the metadata already exists exactly once in the basis and no other
addition is legal. It then
atomically consumes the unique `(request_id, nonce, owner_approval_attestation_sha256)` key in its
monotonic one-use store after verifying unexpired owner approval plus both channels. The private
`$defs/owner_remediation_signer_consumption_receipt` contains only observed/candidate signer-state
sequence/count/complete-state SHA-256/root, observed/candidate complete current-attestation SHA-256,
the old nonmembership/new membership proof, consumed key, service attestation, exact retained-input
descriptors `{id, schema_or_kind, byte_length, sha256}` for request, approval and private join, that
preclaim-basis digest, and the independently read trusted-clock resource/genesis/epoch/
tick/complete-attestation/current-read-receipt digests proving `issued <= observed < expires`. It
forbids the final authorization projection/HMAC, signer
result and result digest.

The signer next builds the complete authorization object as exactly that preclaim basis plus its
external digest and the consumption-receipt descriptor/hash, preserving the basis HMAC metadata once.
For the HMAC projection it
removes only root `attestation.value`, computes the owner-remediation HMAC, inserts that one value, and
only then builds strict
`$defs/owner_remediation_blind_signer_result`. This complete result and its external digest are
custodian-ACL-private, never human/UI/repository/public-response fields. It contains the request and
approval digests, the already public fixed-padded `private_join_commitment` (never the complete
unpadded join descriptor/SHA), private consume-receipt descriptor/hash, fixed-length HMAC reference,
identical stable decision fields, and no own digest. Any optional human acknowledgement is a constant-
shape status carrying at most that same padded commitment and no result/receipt/private descriptor.
`owner_remediation_blind_signer_result_sha256` is computed externally as SHA-256 of its complete
canonical bytes. Neither the result nor that digest is an HMAC input. Before signer use, the public
request/approval and private join are durably retained by their respective ACL-separated content-
addressed input stores under exact descriptors/hashes; the signer service still retains no payload.
One atomic service transaction
compare-and-swaps the observed signer pointer and persists candidate state/pointer, consume receipt and
result. An ambiguous crash may recover only the identical stored result; channel
mutation, a second private join, expired/replayed approval or second result is invalid. The later
resolution CAS independently consumes the authorization once, so signer recovery cannot mint
evaluation budget. `OwnerRemediationSignerStoreReader.read_consumption_receipt_and_result(consumed_key)`
independently returns the exact committed receipt/result after a crash, and
`OwnerRemediationDecisionInputReader.read_inputs(consumption_receipt)` resolves the three retained
request/approval/private-join inputs only by those exact bounded descriptors/hashes. Recovery recomputes the join commitment and strict preclaim
basis, verifies the receipt's basis digest and the result's final HMAC reference, then reconstructs
byte-identical complete authorization bytes. Those bytes are first materialized as the content-
addressed private-history authorization record inside the later resolution CAS; its descriptor/hash
is not an input to its own HMAC or signer state. A crash after one-use consume but before resolution can
therefore reconstruct only the same authorization, never strand or mint one.

The service's immutable image/config/API schemas, owner-authenticated request channel, no-human-read/
no-log/no-APM/no-service-payload-persistence policy, two-channel role ACLs, monotonic one-use store and key-
resource attestation SHA-256 are frozen in governance and bound by the authorization. Raw combined
canonical bytes never reach the human owner, UI, logs or repository. Task 3 tests all request/join/
approval/result/consume schemas, exact correlation/join, one-use state and public-output noninterference
with synthetic keys; Phase 4 attests and integration-tests the real HSM/service/ACL/log/store boundary.
A caller boolean, general owner process or exported key is forbidden.
The complete authorization is a content-addressed private-history record capped at 4,194,304
canonical bytes and is referenced by exact descriptor ID/schema/length/SHA-256. Only its opaque HMAC
commitment/metadata and the intentionally public action/candidate-cycle transition fields cross the
repository boundary.

`activate` additionally binds a closed `$defs/corrected_candidate_build_subject` and one complete
`$defs/corrected_candidate_change_evidence` record descriptor plus the immutable exception-policy/
artifact/path basis from the public request. It forbids every transient
`$defs/submission_freeze_authority_state`, current authority attestation/generation/tick/read receipt.
`decline` forbids the corrected-build/change/exception fields. The head-independent build subject
contains the exact public build basis copied from the private child base; the complete candidate-build
resource manifest; the exact immutable code/prompt/model/config/production-schema/artifact/dependency/
image byte-identity fields and content descriptors/SHA-256 values already enumerated by that manifest;
and the branch-authorized correctable runtime/egress/scorer-implementation attestations. It contains
no inline binary, prompt/config/artifact bytes, filesystem path, environment/secret value, suite
commitment, eligibility/reservation/claim head, complete future fingerprint, or its own
digest. For `candidate_quality_failure`, at least one allowlisted candidate-controlled code/prompt/
model/config/production-schema/artifact/dependency/image byte identity must differ from the parent and
the owner change evidence must name it. This mechanically proves build-identity change, not semantic
improvement. Every changed
production schema must still map byte-identically to the frozen request/response/QueryPlan/GoldenCase/
evidence/scoring/governance contracts; changing one of those evaluation contracts is permanent non-
PASS, not remediation. For `post_truth_control_failure`, the candidate bytes may remain unchanged only
when the exact authenticated parent terminal/outcome/scoring receipts mechanically name the objective
revoked/evaluation-error cause and at least one
causally relevant runtime/egress/scorer-implementation or build-resource attestation changes under the
precommitted safety floor. Scoring rule, disposition, disclosure/K values, source snapshot,
denominator, selection policy/quotas, evaluation schemas, and execution-contract class remain byte-
identical. A mere suite/history/fingerprint difference is not a correction. `decline` forbids the build
subject/change-evidence descriptor and submission-freeze authority state. Both action-specific payloads
and the HMAC input projection forbid
resulting/future history/auth/claim/report heads and any nested/copied self-HMAC. The root
authorization still requires the registered owner-remediation HMAC metadata/value; computation omits
only root `attestation.value`. The build subject contains no own digest;
`corrected_candidate_build_subject_sha256` is its external Canonical JSON v1 SHA-256. The later child
fingerprint contains that complete schema-valid subject as `remediation_build_subject` plus the exact
external digest. Every duplicated candidate-cycle/policy/contract/build field must match the subject
byte-for-byte; the only additional fields are the fingerprint schema's closed suite-commitment,
eligibility/reservation/history, storage-HMAC, governance, and fingerprint-specific attestations. A
digest-only assertion or a fingerprint that omits the complete subject is insufficient. Non-child
fingerprints forbid both remediation fields.

`$defs/corrected_candidate_change_evidence` is a private-history record at most 1,048,576 canonical
bytes with exactly evidence version, trigger kind, parent/child candidate-cycle identities, ordered
allowlisted changed-component paths with old/new byte identities, the exact authenticated parent
terminal/outcome/scoring cause descriptors/hashes, candidate-build compatibility results against every
frozen evaluation contract, owner evidence role/tick, and no candidate output, child truth, suppressed
detail, current/future head, or own digest. The authorization stores and HMAC-binds its complete
descriptor ID/schema/length/SHA-256; a bare digest is insufficient. The owner-remediation validator
streams this record, recomputes the build-resource manifest and changed-field set, verifies the trigger
branch, and checks that the public basis in the build subject equals the one inside the full private
child base byte-for-byte.

`$defs/candidate_cycle_resolution` is a strict action `oneOf`. Common fields are exactly version,
complete parent/child candidate-cycle identities, child-base/batch/allocation IDs, expected global and
human-governance predecessor heads, expected dormant-allocation state/generation, action, old/new
candidate-cycle, reserve-batch, and public `slot_state` values, zero truth/result-budget deltas,
observed tick, and the predecessor-
only private transition subject. `not_activated_parent_pass` requires the exact immediately preceding
parent `report_recorded` attestation/descriptor/hash with accepted disposition;
`not_activated_parent_burn` requires the exact parent pre-truth burn attestation/event/descriptor/hash.
`not_activated_parent_schedule_deadline` requires the exact immediately preceding parent
`scope_schedule_deadline_close` attestation/source, its private deadline transition and the matching
dormant child schedule ref/nonmembership proofs; it writes child state
`closed_parent_schedule_deadline`. These three mechanical parent branches forbid owner authorization.
`not_activated_parent_withdrawal` requires the exact invalidated
parent's `adjudicated_target_report_receipt_ref`; it forbids a
corrected successor from that adjudication, owner authorization, and child build data.
`owner_declined_nonpass` requires the exact fully reported parent
head plus owner-authorization descriptor/commitment with action `decline`.
`owner_resolution_expired_nonpass` requires the exact fully reported invalidated parent and fixed-
schedule parent audit closure, null owner authorization/action winner, the child's matching schedule
entry, authoritative `observed_tick >= owner_resolution_deadline_tick`, and the current dormant child/
allocation/nonmembership proofs. It has no owner HMAC or synthetic approval. Owner activation/decline
instead require `observed_tick < owner_resolution_deadline_tick`; an unprovable or equal tick cannot be
grandfathered. Expiry, activate, decline and authority-close compare-and-swap the same dormant child/
human/slot/allocation heads so exactly one wins.
Every nonactivation branch proves the child's public slot `free -> closing_unused_conditional` in its
resolution revision; the direct zero-channel audit revision alone writes
`closing_unused_conditional -> closed_unused_conditional`, all inside the same multi-revision CAS as
the cycle/batch/allocation close. `owner_activated_remediation` preserves public slot
`free -> free`, changes only the cycle/batch authorization gate to `activation_authorized`, and is
immediately followed by the reservation/claim revision that alone writes the slot and cycle `active`.
`owner_activated_remediation` requires that same parent ancestry, an authorization with action
`activate`, the corrected-build subject/change evidence, the exact active dormant allocation/batch
proofs, an unexpired approved request, and the complete freshly read/locked
`submission_freeze_authority_state`. That fresh state and its three current-resource read-lock receipt
are private fields of the predecessor-independent resolution source and HMAC-protected private append;
they are forbidden from the public resolution and from the earlier owner HMAC. The branch forbids every
destruction field and is followed in the same all-or-none transaction
by child suite reservation and claim. The unused-child close branches instead require an
irreversible logical `terminal_unused_tombstone` transition for the private-control allocation and
`terminal_close_pending_audit` for the paired private-history allocation; the direct zero-channel
audit successor consumes the pre-reserved final append and alone changes the latter to
`terminal_archive_sealed`. Both states forbid a suite reservation, claim, run, token, or ingress. They
bind allocation IDs/tombstone/close subjects,
not a future physical-reclamation receipt. Every nested projection and the resolution entry exclude
their own/resulting global, human, allocation, reservation, claim, audit, or future head. Parent pass/
burn, owner action, or parent identity substitution therefore changes the exact canonical bytes.
Owner actions insert and consume the exact one-use remediation-authorization leaf.

The public `candidate_cycle_resolution` history projection contains only the complete public candidate-
cycle identity, action, old/new public cycle/batch/slot state, zero budget deltas, opaque owner-remediation
commitment and exact HMAC metadata when applicable, plus the ordinary secret-backed private-registry
commitment. It forbids the raw authorization/base/build subject, descriptors, stable-person proof,
private trigger evidence, transient authority state/read receipts, allocation/store metadata, and
suppressed parent detail. Its HMAC-protected private append binds the complete branch projection,
proofs and, only for activation, the complete fresh authority state/read-lock receipt. For a
nonactivation action its new
public slot state is exactly `closing_unused_conditional`; the immediately following public
`slot_private_audit_closed` projection carries the only transition to `closed_unused_conditional`.

After a close CAS, a bounded reaper may physically reclaim the already tombstoned unused control
allocation and append a non-input audit confirmation; that confirmation cannot authorize reuse and is
not part of the resolution or scope-completion hash. Closing an unused child permanently preserves its
case/truth/equivalence reuse indexes, storage-reservation/slot-preparation tombstones, and private-
history audit records and never makes its suite available elsewhere.

The candidate-cycle state machine is total. Organizer creation first writes ordinal 0 as `free` with
null batch/gate `unbound` and ordinal 1 as `dormant_conditional` with null batch/gate `unbound`.
`reserve_batch` is the sole same-label writer: ordinal 0
`free/unbound/no-batch -> free/active-gate/batched`, and ordinal 1
`dormant_conditional/unbound/no-batch -> dormant_conditional/dormant-gate/batched`. After those edges,
ordinal 0 is `free -> active -> reported_pass |
reported_invalidated | burned`, with the guarded preclaim-only edge
`free/unbound/prepared/no-batch | free/batched -> closed_authority_conflict` and the distinct timed edge
`free/unbound/prepared/no-batch | free/batched -> closed_schedule_deadline`; ordinal 1 is
`dormant_conditional -> closed_parent_pass | closed_parent_burn | closed_parent_withdrawal |
closed_owner_decline | closed_owner_resolution_expired | closed_parent_authority_conflict |
closed_parent_schedule_deadline | activation_authorized -> active`, followed, only from
`active`, by
`reported_pass | reported_invalidated | burned`. Parent pass or pre-truth burn atomically closes the
child. A parent preclaim authority close atomically writes `closed_authority_conflict` plus
`closed_parent_authority_conflict` and both zero-channel audit closures. A reported parent invalidation leaves the scope incomplete until the distinct owner chooses
activate or decline. Activation is one atomic resolution + child suite-reservation + claim transaction
against the already allocated slot/batch; it mints no slot or budget and makes execution/report-or-
burn mandatory. Each unused-child close action also creates the zero-channel audit closure described
below, and only that closure permits scope completion. Decline is permanent cumulative non-PASS. No
third candidate cycle, alternate child, replacement, reset, post-pass reopening, or reuse is legal.

Those arrows are not descriptive labels. `reserve_batch` is the sole same-state batch/gate writer for
every locked/sealed slot leaf and, for sealed lanes, its paired candidate-cycle leaf. Ordinal 0's paired suite-reservation/claim is the sole
`free/batched -> active` writer; a sealed `report_recorded` is the sole `active -> reported_pass |
reported_invalidated` writer; and a sealed `consumption_claim_burn` is the sole `active -> burned`
writer. `authority_conflict_preclaim_close` is the sole preclaim writer of
`closed_authority_conflict`/`closed_parent_authority_conflict`; `scope_schedule_deadline_close` is the
sole writer of ordinal-0 `closed_schedule_deadline`, and
`candidate_cycle_resolution(action=not_activated_parent_schedule_deadline)` is the sole writer of the
dormant child's `closed_parent_schedule_deadline`. Each transition checks the old cycle sequence/state, increments sequence exactly once, and
stores the branch's complete source descriptor/hash in the new leaf. Ordinal 1 uses the same
report/burn rules after its owner-resolution/claim CAS has written `active`. Parent remediation,
readiness, and archive validation consume these exact authenticated leaves rather than caller-supplied
state labels.

Construction order is one-way and exact. For a parent pass or pre-truth burn, compute the parent
report/burn revision first, compute the direct `candidate_cycle_resolution` successor from its hash
and predecessor-only global/human/allocation guards, compute the zero-channel audit successor from the
resolution hash, then derive human completion from the audit head; one transaction persists the whole
ordered suffix or none. A parent preclaim schedule expiry uses
`scope_schedule_deadline_close -> not_activated_parent_schedule_deadline -> child
never_activated_conditional zero-channel audit -> parent never_claimed_preclaim_close zero-channel
audit -> human completion`. The child resolution is the direct successor of the parent close, its
audit directly consumes `closing_unused_conditional`, the later parent audit source-binds the earlier
parent close while leaving the child closed, and completion binds both audit heads; all global/human/
allocation/sink mutations commit in one CAS. Omission or permutation is invalid. A withdrawal-only parent adjudication uses the same order:
`post_adjudication(correction_expected: false)` -> `not_activated_parent_withdrawal` -> zero-channel
audit -> completion, all-or-none. For owner decline, the already durable parent invalidated report/audit closure
precedes the head-independent owner-remediation HMAC, then resolution -> zero-channel audit -> human
completion is one multi-store CAS. For activation, the durable parent invalidated report/audit closure
precedes the corrected-build subject and owner-remediation HMAC; the transaction then computes the
resolution revision/hash, suite-reservation revision/hash, complete manifest/fingerprint as the exact
fieldwise build-subject extension, and claim revision, and atomically persists all three global
revisions plus claim artifacts. The resolution writes only `activation_authorized`; the final claim
writes `active` and exhausts the batch. Activation creates
no human completion. No authorization or resolution projection contains a head that this order has
not already produced.

`$defs/history_transition_source` is the sole predecessor-independent source object used by typed
mutable and receipt-identity index leaves. It is one strict `oneOf` over every non-genesis public
attestation kind (`reserve_batch`, `suite_reservation`, `consumption_claim`,
`consumption_claim_transfer`, `consumption_claim_burn`, `authority_conflict_preclaim_close`,
`scope_schedule_deadline_close`,
`truth_release_commit`, `post_outcome`,
`report_recorded`, `post_adjudication`, `corrected_report_recorded`,
`slot_private_audit_closed`, `candidate_cycle_resolution`, or `registry_continuity`). Common fields are
exactly source version/ID, registry/genesis, target revision, kind, expected predecessor revision/head,
the branch's complete public subject with private-registry HMAC/resulting counters/roots/resulting head
removed, ordered pre-existing or head-independent private record descriptors, and at most sixteen
ordered touched-index entries. Each touched entry has exact index name/key SHA-256 and the complete new
logical value with only its `source_transition_kind/descriptor/hash` fields omitted. The source forbids
the proof-bundle manifest/chunks, old/new index roots, resulting registry state, private-history or
public-attestation HMAC/value, public attestation bytes/hash/head, its own descriptor/digest, and any
future lifecycle/report/human head. It is a private-history record capped at 16,384 canonical bytes.

The `scope_schedule_deadline_close` public subject contains only registry/slot/suite-or-candidate
identity, schedule offset-profile ID/version, old/new public slot/cycle labels, zero truth/result/
disclosure deltas and the ordinary `private_registry_commitment` HMAC metadata. It forbids the private
schedule descriptor/hash/ticks, `evaluation_scope_deadline_transition`, scope/principal identity and
stage-specific evidence. Its HMAC-protected private source embeds the complete deadline transition and
no-claim/dispatch/run/token/ingress/truth/result proofs. This reuses the existing private-registry HMAC
formula; it adds no HMAC purpose/domain. Locked slots and sealed ordinal 0 share this strict cause-
neutral public non-PASS shape, while their typed private slot/cycle old/new states remain distinct.

Construction is mandatory: build and content-address the source bytes/descriptor first; insert that
exact kind/descriptor/hash into each touched full leaf value; compute leaf hashes and Sparse-Merkle
proofs/roots; build the proof-bundle manifest; then build the later `appended_private_record`, resulting
state, HMAC and public attestation/head. A source cannot be the generic appended record because that
later record contains the proof manifest. Every non-genesis private-history reservation includes
exactly one source-record occurrence per history transition, and the generated max-shape/record-count/
byte formula proves these 16,384-byte records fit the fixed allowance. `HistoryRecordReader` resolves
the source by descriptor and validators rederive every branch/touched value before accepting a proof.
Missing, extra, reordered, wrong-kind or reused source entries fail closed.

The strict `$defs/index_values/candidate_cycle_id` is the immutable complete candidate-cycle identity.
`$defs/index_values/candidate_cycle_state` has exactly that identity, state sequence, closed state,
nullable reserve-batch ID/size, claim-gate state (`unbound`, `active`, `dormant_conditional`, or the
branch terminal gate), next reserve ordinal, exhausted boolean, nullable consumed owner-
remediation commitment, and the exact predecessor-independent source record descriptor/hash for the
latest transition. It excludes the resulting registry head/root. The only no-batch values are the
organizer-created ordinal-0 `{free, unbound, null batch, next: 0, exhausted: false}` and ordinal-1
`{dormant_conditional, unbound, null batch, next: 0, exhausted: false}`. Their unique `reserve_batch`
successors preserve state/next/exhausted while installing the exact batch ID/size and respectively
gate `active` or `dormant_conditional`. For ordinal 1, every close action
requires old `{state: dormant_conditional, gate: dormant_conditional, next: 0, exhausted: false}` and
new `{state: closed_parent_pass|closed_parent_burn|closed_parent_withdrawal|closed_owner_decline|
closed_owner_resolution_expired|closed_parent_authority_conflict|closed_parent_schedule_deadline,
gate: terminal_unused,
next: 0, exhausted: true}`. Activation requires that same old value; its resolution writes
`{state: activation_authorized, gate: active, next: 0, exhausted: false}`, and the immediately
following atomic reservation/claim alone writes
`{state: active, gate: active, next: 1, exhausted: true}`. No
intermediate value is externally visible. `$defs/index_values/remediation_authorization` has exactly
parent/child identities, child-base SHA-256, action, owner-remediation commitment and descriptor/hash,
and consumed-at tick; it is append-only and excludes current/resulting heads. Any other state/counter
combination or caller-selected transition label fails the old-leaf proof before CAS.

`$defs/index_values/slot_state` is a strict lane/state `oneOf`. Every branch has exactly state version,
global slot ID, lane/checkpoint, nullable complete candidate-cycle identity (required sealed, forbidden
locked), monotonic state sequence, state, reserve-batch ID/size/gate/next ordinal/exhausted values,
retired-token-ledger commitment and HMAC metadata, exact predecessor-independent source transition
kind/descriptor/hash, and no resulting registry root/head. `free` requires null owner/run/claim/truth/
outcome/report fields. Its `free` branch is itself a strict `oneOf`: organizer/genesis-created
`unbound` has null batch ID/size, next 0 and not exhausted; `reserve_batch` alone preserves
`state: free` while installing the exact batch ID/size and either active gate (locked or sealed ordinal
0) or dormant gate (sealed ordinal 1), next 0 and not exhausted. `active` requires one owner suite/run, the already durable paired suite-
reservation head, fence epoch, and active batch gate; its current-writer field is the predecessor-
independent claim source descriptor/hash, never the
claim revision's resulting head, and it forbids truth/outcome/report closure fields.
`authority_closed_preclaim` requires the exact preparation predecessor, terminal-unused
allocation/scope-closure identities and `authority_conflict_preclaim_close` source; it forbids owner/
run/claim/truth/outcome/report fields and is permanent. Its strict old-state `oneOf` is either the
prepared `free/unbound/null-batch` row plus reserve nonmembership or the exact prepared `free/batched`
row plus reserve membership; its terminal value preserves the preparation identity and carries the
nullable reserve identity accordingly. `scope_deadline_closed_preclaim` has the same old-state and
no-claim/dispatch/run/token/ingress/truth/result proofs but requires the exact
`scope_schedule_deadline_close` source and matching schedule deadline transition instead of authority
evidence; it is permanent and cannot be substituted for `authority_closed_preclaim`.
`consumed_burned` requires burn reason class,
terminal fence state, the already durable prior claim/
transfer head, and the burn source descriptor/hash, never the burn revision's resulting head; it
forbids owner/truth/report fields. `truth_committed/outcome_pending` requires consumed counters, the
already durable prior claim/transfer head, and the truth-commit source descriptor/hash, never the
truth-commit resulting head. `truth_committed/report_pending` additionally binds the already durable
truth-commit attestation head and current post-outcome source descriptor/hash, never the post-outcome
resulting head. `truth_committed/reported` binds the already durable post-outcome head and current
report source descriptor/hash, never the report revision's resulting head.
`closed_unused_conditional` is sealed ordinal 1 only and requires terminal-unused batch gate,
unclaimed/no-channel proof, the already durable prior candidate-cycle-resolution attestation head,
and the current zero-channel-audit source descriptor/hash, never the audit revision's resulting head;
it forbids every owner/run/claim/truth/outcome/report field. The transaction-local
`closing_unused_conditional` branch is also sealed ordinal 1 only: it contains the predecessor-
independent resolution source descriptor/hash, terminal-unused batch gate, and exact zero-channel-
audit successor subject, never the resolution's resulting head; it forbids claim/channel/truth/result
fields and may be consumed only by that direct
audit revision to produce `closed_unused_conditional`. Because the complete suffix is one atomic
multi-head transaction, it is never a valid externally observable current state. Batch/gate/counter
fields that do not apply are explicit nulls, never omitted.
A guarded `authority_conflict_preclaim_close` is the only legal
`free|batched -> authority_closed_preclaim` writer; the timed
`scope_schedule_deadline_close` is the only legal
`free|batched -> scope_deadline_closed_preclaim` writer. A nonactivation resolution is the only legal
`free -> closing_unused_conditional` writer and its
direct zero-channel audit is the only legal `closing_unused_conditional -> closed_unused_conditional`
writer; the child
claim is the only legal `free/batched -> active` writer after `activation_authorized`. Both terminal states are
permanent. The generated lock carries an exact mapping table:
`free/unbound -> free/batched(active gate)`,
`dormant_conditional/unbound -> dormant_conditional/batched(dormant gate)`,
`dormant_conditional|activation_authorized -> slot free/batched`, `active -> slot active`,
`reported_pass|reported_invalidated -> slot truth_committed/reported`, and
`authority_closed_preclaim -> slot authority_closed_preclaim`,
`closed_schedule_deadline -> slot scope_deadline_closed_preclaim`,
`burned -> slot consumed_burned`; each row fixes the matching gate/counters/closure fields. An unused
child maps `closed_parent_pass|closed_parent_burn|closed_parent_withdrawal|closed_owner_decline|
closed_owner_resolution_expired|closed_parent_authority_conflict|closed_parent_schedule_deadline`
first to the resolution's
`closing_unused_conditional` slot revision and then requires the direct audit descendant
`closed_unused_conditional`; its final slot and cycle leaves intentionally have different source
revisions but exact resolution-to-audit ancestry. All other mapped leaves reproduce candidate identity,
batch/gate/next/exhausted values, transition source, and history revision. Locked slots forbid a
candidate-cycle leaf. The generated lock carries every allowed old/new edge and max-shaped fixture.
Candidate-cycle, reserve-batch, and
slot proofs are verified from the same transition witness and cannot come from different revisions.

`$defs/index_values/report_lineage` is a strict state object with exactly report ID, lineage sequence,
current revision, current complete public-report SHA-256, private-report commitment plus registered
HMAC metadata, outbox descriptor/hash, state (`current_original`, `correction_pending`,
`current_corrected`, or `withdrawn`), nullable predecessor revision/public hash, correction-used
boolean, and the exact predecessor-independent history-transition source kind/descriptor/hash. It
forbids a registry root, private/public history HMAC, public attestation hash or resulting receipt/head.
The only edges are empty -> `current_original` by `report_recorded`; current original/corrected ->
`withdrawn` by `post_adjudication(correction_expected: false)`; current original -> transaction-local
`correction_pending` by `post_adjudication(correction_expected: true)`; and that exact pending value ->
revision + 1 `current_corrected` by the direct `corrected_report_recorded` source. The true pair is one
all-or-none transaction, so pending is never externally current; no second true correction is legal.

`$defs/index_values/receipt_identity` is append-only and has exactly receipt kind, deterministic receipt
ID, source-subject SHA-256, status `durable`, and the same predecessor-independent transition-source
kind/descriptor/hash. Its closed kinds are `post_outcome`, `report_recorded`, `post_adjudication`, and
`corrected_report_recorded`. The exact closed receipt-ID projection is
`{receipt_identity_version: "1", receipt_kind, guarded_subject}` where `guarded_subject` is a strict
kind-discriminated `oneOf`: respectively the sole truth-release-commit head, sole post-outcome head,
exact current report ID/revision/complete-public-report hash, or sole post-adjudication head. The
external ID is
`SHA256(b"FinProof/HistoryReceiptIdentity/v1\x00" || canonical_bytes(projection))`; the projection
forbids its own ID and alternate delimiter/string encodings. It also forbids any resulting public attestation/head,
registry root/HMAC, or caller-selected random ID. Thus an alternate report/outcome under the same
guarded subject collides with the occupied key rather than creating a second receipt.

`current_report_receipt_ref` is a validation-time composition, never a stored leaf value. Its report/
commitment/outbox/source fields are recomputed from the authenticated `report_lineage` and matching
`receipt_identity` leaves; its receipt descriptor/hash/resulting head comes separately from the
verified public history attestation/transition receipt after that writer completed. The resulting head
must authenticate those exact leaves, but neither leaf may contain it. The same rule applies to every
current/corrected report reference and remediation public/private predecessor projection.

The governance lock also contains exactly two head-independent
`locked_slot_genesis_subject` entries, one per named locked checkpoint, with policy/checkpoint/slot
IDs, `state: free`, zero counters, empty batch/owner/truth/report values, and the empty retired-token
ledger commitment. Each subject excludes history roots, attestation/HMAC values, and its own digest;
its external digest is
`SHA256(b"FinProof/LockedSlotGenesisSubject/v1\x00" || canonical_bytes(locked_slot_genesis_subject))`;
that subject forbids its own digest and the lock-entry descriptor binds the resulting value as the
genesis slot leaf's source kind/descriptor/hash. No later leaf may use that source kind or another tag/
encoding.

An organizer release-cycle successor requires zero active claims and preserves the exact slot-owner/
attempt and retired-token ledgers. A key/custodian-resource change during or outside a claim is never a
continuity successor: rotation, revocation, compromise or transfer stops this immutable-manifest
history pending a new frozen design and may not re-HMAC any projection. No
continuity append is permitted from `truth_release_commit` until its matching `report_recorded` is
durable, nor while an adjudication/correction receipt is pending. A new organizer opportunity creates
exactly two distinct sealed `RELEASE_CANDIDATE` candidate-cycle slots—ordinal 0 and dormant
conditional ordinal 1—and never clears the prior ledger. The two locked-checkpoint
slot identities, counters, and histories are competition-global and remain byte-for-byte continuous;
organizer release-cycle authorization never resets them. Public event hashes and attempt IDs are opaque
non-truth metadata, never questions, expected values, case IDs, or failure details.

Before any locked/sealed suite manifest is committed, Phase 4 creates the immutable release dossier
`release/evaluation-history-genesis.json`, containing the competition-global
`history_registry_id`, the complete schema-valid revision-1 `registry_genesis` attestation, and its
Canonical JSON v1 SHA-256 as
`history_genesis_attestation_sha256`. The genesis has null suite/checkpoint/reserve fields and zero
consumption counters and forbids `history_genesis_attestation_sha256`, so the dossier's digest is
acyclic. The custodian records the same dossier in its append-only audit store and the repository
release record before implementation can observe a result. Revision 1 alone has
`prior_attestation_sha256: null`, and its complete hash must equal that externally pinned genesis
value. Every later revision increments by exactly one and
points to the Canonical JSON v1 SHA-256 of the complete preceding schema-valid attestation,
including its HMAC value. Only a new organizer release cycle appends a typed continuity successor under
the same global registry/genesis and unchanged deployment manifest. No path may create another null
genesis.

The custodian registry maintains an atomic current-head record plus one bounded, HMAC-authenticated
`history_registry_state`. Human review/exclusion evidence is durable private input, but no non-open
preclaim lifecycle event is published before the winning claim transaction. Creating a suite precomputes a
`suite_reservation` attestation whose predecessor is the exact current head, stores that predicted
hash as `eligibility_history_head_sha256` in the immutable suite manifest and freeze fingerprint, and
precomputes the directly following `consumption_claim`. One registry/custodian transaction durably appends both
ordered private/public revisions, compare-and-swaps the external head from the old predecessor to the
claim head, advances the sole batch member to exhausted, and changes the exact slot from free to
active. From the predicted reservation hash it also builds the manifest/fingerprint, then the complete
candidate-fingerprint-bound lifecycle chain from draft initialization through human review,
exclusion approval, lane lock/seal and sealed eligibility as applicable, ending with the consuming
event that one-way binds the claim head. The same transaction writes that consuming-event hash as
`lifecycle_current_head_sha256` in the generation-zero private-control snapshot named by the signed
pointer and persists
the reservation, manifest, fingerprint, claim, and every
ordered lifecycle event. Neither registry revision nor any lifecycle/object member is visible or
durable without all the others. A failed/stale CAS publishes none of them; retry predicts the new
reservation hash and rebuilds the fingerprint/event bytes from the same immutable human-reviewed
suite rather than rewriting an append-only event. The pair
rejects every registry state
with a truth-committed slot whose closure substate is not `reported` or with a pending adjudication/
correction receipt. The private one-member reserve batch is precommitted before results. Its sole
suite manifest/reservation/claim pair must reproduce the committed case-set/checkpoint facts exactly,
and the pair permanently exhausts the slot batch. Genesis-complete continuity is established by the
externally pinned genesis/head, the validated predecessor state, and each atomic transition; a normal
append never materializes the complete chain. A fork, gap, duplicate revision,
registry/genesis substitution, non-genesis null, stale-head CAS, missing eligibility ancestor,
reservation without its paired claim, claim without its immediate reservation, or suite reservation
inconsistent with its active batch/next ordinal fails closed.

That schema also exposes non-root `$defs/history_genesis_anchor`, `$defs/history_registry_state`,
`$defs/history_transition`, `$defs/history_transition_source`, `$defs/history_archive_manifest`,
`$defs/history_archive_descriptor`,
`$defs/history_proof_chunk`, `$defs/history_proof_bundle_manifest`,
`$defs/deployment_trust_anchor_manifest`, `$defs/deployment_trust_anchor_pin_receipt`,
`$defs/checkpoint_candidate_provenance_subject`, `$defs/checkpoint_candidate_pin_receipt`,
`$defs/checkpoint_candidate_pre_execution_order_witness`,
`$defs/checkpoint_candidate_final_repository_order_witness`,
`$defs/evaluation_control_plane_public_role_attestation`,
`$defs/evaluation_control_plane_resource_manifest`,
`$defs/evaluation_scorer_resource_manifest`, `$defs/scoring_rule_manifest`,
`$defs/reference_executor_manifest`, `$defs/reference_truth_execution_request`,
`$defs/reference_truth_execution_result`, `$defs/reference_truth_derivation_receipt`,
`$defs/reference_executor_disjointness_receipt`, `$defs/reference_truth_suite_witness`,
`$defs/evaluation_scope_schedule_offset_profile`,
`$defs/evaluation_scope_terminal_schedule_projection`,
`$defs/evaluation_scope_terminal_schedule_ref`, `$defs/evaluation_scope_deadline_transition`,
`$defs/evaluation_scope_deadline_stage_witness`,
`$defs/postfreeze_incomplete_scope_fence`,
`$defs/revoked_public_id_plan`,
`$defs/human_stable_identity_attestation`, `$defs/owner_curator_non_alias_proof`,
`$defs/identity_authority_current_attestation_projection`,
`$defs/identity_authority_current_attestation`, `$defs/identity_authority_current_witness`,
`$defs/registry_current_pointer_attestation`, `$defs/current_registry_witness_set`,
`$defs/slot_preparation_registry_witness`, `$defs/aead_nonce_registry_state`,
`$defs/aead_nonce_registry_witness`,
`$defs/organizer_cycle_authorization`, `$defs/owner_remediation_authorization`,
`$defs/owner_remediation_public_decision_request`,
`$defs/owner_remediation_public_approval_attestation`,
`$defs/owner_remediation_private_join_commitment_projection`,
`$defs/owner_remediation_private_join`,
`$defs/owner_remediation_signer_state`, `$defs/owner_remediation_signer_current_attestation`,
`$defs/owner_remediation_signer_state_witness`,
`$defs/owner_remediation_blind_signer_result`,
`$defs/owner_remediation_signer_consumption_receipt`,
`$defs/owner_remediation_authorization_preclaim_basis_projection`,
`$defs/activation_authority_read_attestation`,
`$defs/activation_authority_transition_manifest`, `$defs/trusted_clock_current_witness`,
`$defs/official_instruction_snapshot`, `$defs/official_instruction_record`,
`$defs/official_instruction_applicability_manifest`,
`$defs/official_instruction_semantic_review_record`,
`$defs/non_open_irreversible_action_subject`,
`$defs/non_open_irreversible_action_authority_state`,
`$defs/non_open_irreversible_action_authority_guard`,
`$defs/irreversible_action_authority_binding`, `$defs/authority_conflict_preclaim_close`,
`$defs/submission_freeze_basis`,
`$defs/submission_freeze_authority_state`, `$defs/current_report_receipt_ref`,
`$defs/remediation_predecessor_public_ref`, `$defs/remediation_predecessor_private_witness`,
`$defs/adjudicated_target_report_receipt_ref`,
`$defs/conditional_child_selection_comparability_projection`,
`$defs/conditional_child_public_build_basis`, `$defs/conditional_child_base`,
`$defs/corrected_candidate_build_subject`, `$defs/corrected_candidate_change_evidence`,
`$defs/corrected_disclosure_aggregate_projection`, `$defs/correction_disclosure_delta`,
`$defs/cumulative_disclosure_archive_manifest`, `$defs/cumulative_disclosure_archive_witness`,
`$defs/release_report_validation_entry`, `$defs/release_report_validation_entry_shard`,
`$defs/release_report_validation_entry_manifest`, `$defs/release_report_validation_dossier`,
`$defs/verified_published_report_receipt`,
`$defs/release_authority_validation_projection`, `$defs/release_action_completion_basis`,
`$defs/release_action_store_reservation_plan`, `$defs/release_action_store_reservation_receipt`,
`$defs/release_action_branch_result`,
`$defs/release_action_state`, `$defs/release_action_current_attestation`,
`$defs/release_action_current_witness`,
`$defs/release_action_receipt`,
`$defs/release_action_execution_result`,
`$defs/disclosure_outbox_read_context`,
`$defs/candidate_cycle_resolution`, and
`$defs/private_history_record` contracts for validation
only; no private-registry instance may be committed. The genesis anchor contains exactly the registry
ID, complete revision-1 attestation, and pinned hash. Registry state contains that identity, current
revision and a preallocated external audit-record identifier, closed counters/slot/report/sink state,
and a closed map of authenticated index roots. It explicitly forbids the current/resulting public
attestation hash or registry-head value. The authoritative current head exists only in the external
atomic CAS record and the transition witness/receipt, after the state/HMAC/attestation bytes are
constructed. It never embeds a complete prior chain, case, evidence
package, report, or truth payload.

`$defs/registry_current_pointer_attestation` is the independently read currentness anchor for exactly
five private resources: `suite_history`, `human_governance`, `sink_registry`, `slot_preparation`, or
`aead_nonce_registry`.
Every branch has
literal resource kind, pinned pointer resource/genesis/store IDs, CAS generation, current registry
revision/sequence, current head SHA-256, current canonical-state SHA-256, store-monotonic epoch/version,
`prior_complete_pointer_attestation_sha256` (null only at pinned generation zero), scheme/version
`ED25519_STORE_ATTESTATION_V1`, pinned public-key resource/key ID, and canonical base64 64-byte
signature. The exact signature tags are respectively
`b"FinProof/SuiteHistoryCurrent/v1\x00"`,
`b"FinProof/HumanGovernanceCurrent/v1\x00"`, or
`b"FinProof/SinkRegistryCurrent/v1\x00"`,
`b"FinProof/SlotPreparationCurrent/v1\x00"`, or
`b"FinProof/AeadNonceRegistryCurrent/v1\x00"`; the signed message is exactly the selected literal tag
concatenated with Canonical JSON v1 bytes of the complete branch with only the signature removed.
Complete-object SHA-256 is external. This asymmetric store attestation is
outside the 27 HMAC domains and never enters a public report/history projection.

`$defs/current_registry_witness_set` is a strict resource-keyed set of those independently obtained
complete pointer/attestation bytes and current-store read receipts plus one common linearizable
`current_set_snapshot_receipt`. The receipt has exactly transaction/snapshot ID, the ordered five
resource/genesis IDs and observed CAS generations/store versions/complete-attestation SHA-256 values,
acquired-at trusted-clock identity/tick, lease/recheck mode and expiry. It is obtained by one atomic
multi-resource read snapshot, or by a documented double-collect followed by one atomic compare/read-
lock of all five generation tuples; five unrelated point reads are invalid. Each entry is `read_current` or
`transition_current`. The read branch forbids a candidate successor. The transition branch additionally
contains exactly one candidate pointer whose resource/genesis/epoch/key are unchanged, generation and
store version advance contiguously, prior-attestation digest equals the observed complete pointer, and
revision/sequence/head/state digest equal the newly constructed registry successor. Construction is
acyclic: registry source/proofs/state/HMAC/public-or-private head first, candidate pointer/signature
second, then one atomic CAS of the observed pointer generation plus all branch stores. The pointer is
never an input to the head it points at. A read-only authorization, public outbox visibility decision,
readiness decision or submission action must occur while the common snapshot lease remains valid or
after an atomic final recheck of all five observed tuples; a writer compare-and-swaps every applicable
tuple. No interposed withdrawal/correction, human exposure, late sink receipt, slot insertion or nonce
claim can leave a previously read branch authoritative.

Each pointer resource has a pinned genesis and permits no reset/delete/fork/rollback or alternate key.
`CurrentRegistryResourceReader.read_current_set()` obtains that coherent five-resource snapshot by
pinned resource IDs, never by caller-chosen descriptors, and returns the exact common snapshot receipt.
Pure validation compares those independent bytes to the witness, recomputes state/head/complete-object
digests and requires every supplied history/human/sink/slot-preparation/nonce lineage terminate exactly
there; Phase 4 verifies Ed25519 and the real current-store lease/read/CAS. Every non-open owner/
evaluation/publication/readiness path supplies all five current branches; a transition supplies
the applicable candidate branches. Open-only validation supplies both witness/reader as null. A valid
ancestor before a later withdrawal/correction, exposure grant, late-output receipt, child result or
audit closure or nonce claim is therefore historical evidence, never current-state authorization.

The slot-preparation entry additionally contains a strict descriptor-only
`$defs/slot_preparation_registry_witness`. A read branch contains the complete bounded current state
plus one requested-key row/source/receipt/proof descriptor set. The combined transition branch contains
old and final candidate state plus one strict `slot_preparation_transition_manifest` with one through
four ordinal-ordered entries; each entry has exactly ordinal, source, row, old-root nonmembership proof,
new-root membership proof and receipt descriptors/lengths/SHA-256, and the manifest carries the exact
ordered descriptor-list root. Its entry projection is exactly
`{scope_entry_ordinal, source_descriptor_tuple, row_descriptor_tuple,
old_nonmembership_proof_descriptor_tuple, new_membership_proof_descriptor_tuple,
receipt_descriptor_tuple}` and its root is
`slot_preparation_transition_list_sha256 =
SHA256(b"FinProof/SlotPreparationTransitionList/v1\x00" ||
canonical_bytes(exact_ordinal_ordered_transition_tuple_array))`. The manifest also reproduces the
`slot_preparation_source_list_sha256` recomputed from the source tuples, and the candidate human
transition must carry that same value. Pair flattening, tag change, tuple omission or mixing roots from
different manifests is invalid. No complete source, row, receipt or proof is inlined in this witness.
`SlotPreparationRecordReader` streams those records under 524,288-byte source, 1,048,576-byte row,
1,048,576-byte receipt, 1,048,576-byte proof and 33,554,432-byte aggregate caps before parse; the
524,288-byte current-registry witness cap therefore applies only to state and descriptors. The reader
recomputes the sequential root/count/sequence/receipt-head chain and the final state digest/root must
equal the signed slot-preparation current pointer. A fifth entry, duplicate/permuted ordinal,
same-old-root proof reuse, missing source binding, or historical insertion receipt without current-root
membership is invalid and cannot authorize allocation, rebase or claim.

The nonce-registry entry analogously contains strict `$defs/aead_nonce_registry_witness`: complete
current nonce-registry state bytes, every requested claim-receipt descriptor/hash, both occupied leaf
values and current-root membership proofs. A transition additionally carries the predecessor state,
two old-root nonmembership proofs, candidate receipt/leaves, two new-root membership proofs and
resulting state. The nonce-evidence methods of `CurrentRegistryResourceReader` resolve only the
descriptor-bound state/receipt/proof bytes under the generated caps. The state digest/roots/sequence
must equal the signed nonce current pointer;
an old receipt chain without current-root membership, an omitted occupied leaf or a candidate state
without both uniqueness updates is invalid. The reader and witness are required for every truth-commit,
redemption and non-open control/report validation that references an AEAD receipt.

That schema also exposes closed validation-only `$defs/sink_registry_genesis`,
`$defs/sink_registry_state`, `$defs/sink_registry_transition_receipt`,
`$defs/human_governance_genesis`,
`$defs/human_governance_state`, `$defs/human_review_approval`,
the shared `$defs/conditional_child_base` record, `$defs/human_curation_scope_entry`,
`$defs/human_curation_scope`,
`$defs/human_scope_completion`, `$defs/human_output_exposure`,
`$defs/human_governance_transition_receipt`, `$defs/authenticated_access_subject_context`,
`$defs/authenticated_human_review_session`, `$defs/human_review_session_state`,
`$defs/human_review_session_proof_bundle`, `$defs/human_review_authority_interval_receipt`,
`$defs/review_authority_conflict_tombstone`, and
`$defs/human_governance_witness`. The approval record contains exact registry/principal/suite/case-
set/evidence/exclusion/reviewer-role identities, approval tick, immutable completed-review result, and
one exact `human_review_authority_interval_receipt` descriptor/length/SHA-256. That strict private
receipt contains interval version/ID, authenticated review-session digest, stable-principal and suite/
case-set identities, first/last `review_access` subject/state/guard bindings, start/end official-
snapshot descriptors/generations/ticks, and an ordered complete authority-transition-chain descriptor/
hash proving every successor between them. It is accepted only when both endpoints are `allowed`, the
same session/principal/case set was continuously fenced, and no matching prohibition was effective at
any interval point even if later retracted. It forbids hidden truth/evidence bytes, review result,
scope/preparation/resulting human head and every public field. A losing or mid-review conflict creates
only a private permanent `review_authority_conflict_tombstone` for that principal/case-set revision and
no approval/scope; already read bytes are treated as a control incident and the same reviewed revision
cannot later be revived after retraction.
The strict private `$defs/authenticated_access_subject_context` is a closed `oneOf` obtained only from
the deployment-pinned `AuthenticatedSessionReader`. Common fields are context/session version and ID,
transport-session-binding SHA-256, pinned reader-service/image/config identity, issued tick, expiry tick
and live-session generation, plus deployment-pinned trusted-clock resource/genesis/epoch and literal
tick unit `monotonic_nanoseconds`. The reader/gate byte-compares that tuple to the independently current
clock witness used by the action guard; cross-epoch or unit substitution fails before any read. The human branch has role `repository_owner|curation_principal` and the
complete current stable-identity-attestation descriptor/hash; the service branch has role
`implementer_service` and the deployment-pinned mTLS/OS-peer service-attestation descriptor/hash; the
anonymous branch has only role `anonymous_repository` and forbids human/service identity fields. The
reader takes no caller argument and derives the context from the live OS-peer/mTLS/transport channel;
the deployment trust manifest pins its `access-context-reader` service role, image/config digest and
accepted OS-peer/mTLS roots. No serialized caller-provided signature or bearer context is accepted.
Expiry, transport rebinding, reader/service drift or identity-authority nonmembership invalidates the
context. Its complete canonical digest is retained in every action subject that used it.

The strict `$defs/authenticated_human_review_session` contains that complete human context, exact
stable-principal/suite/case-set/revision and review-session IDs, and the current
`$defs/human_review_session_state`. The latter is keyed by
`{human_principal_attestation_sha256, suite_id, suite_version, case_set_revision}` and has one-way states
`active|completed|authority_conflict_tombstoned|expired_aborted`. `start_review()` first runs the fresh
`review_access` guard and atomically inserts `active` with the complete start authority binding and
context before returning any hidden byte. Every later read must observe that exact current active row,
the same live context/session and a fresh allowed guard. `finish_review()` alone may change active to
`completed`, atomically storing the complete interval receipt; a current prohibition, identity/session
loss or expiry instead writes the matching permanent tombstone/expired branch. No terminal branch can
return to active. Once the key was occupied, a crash resumes only the same session/start binding; it
may never create a fresh interval that omits an earlier hidden read. The final approval binds the
completed terminal row and interval receipt, not a transient session result.

`HumanReviewAccessGate` is the sole Phase-4 path to any non-open GoldenCase/evidence/reference-truth
bytes. It obtains the live context through `AuthenticatedSessionReader.read_current()` and builds the
complete `review_access` subject internally, acquires/rechecks the three current authority resources
plus identity/human-governance generations for each bounded byte read, and returns bytes only while
the durable active row remains current and the guard is allowed. It accepts no caller role/context/
current-state/proof/allowed boolean. It may not hold a clock/store lock for the human-duration review;
instead every read is freshly fenced and final approval streams the complete start-to-end transition
chain into the interval receipt. Lease/session expiry, successor generation, alias/revocation or any
interval conflict denies the next read and terminalizes the occupied session key. Each start/terminal
transition receipt, interval/tombstone and approval is capped at 1,048,576 bytes. Session state and the
complete access context are embedded in the applicable transition/index value rather than counted as
separate records; the exact 32-record occurrence table below reserves all four review lineages.
The approval record additionally contains
for non-open suites the complete reference-truth-suite-witness descriptor/hash, authored/excluded/
eligible counts and receipt-descriptor-list digest copied from that witness; open approvals forbid
those fields. Validation streams the witness to prove every per-case receipt/fingerprint equality.
The scope has one immutable `scope_batch_id`, the complete private schedule-record descriptor/length/
SHA-256 and offset-profile ref, one through four ordered unique entries and exact
entry-list SHA-256; it also binds the authenticated basis global head and exact omitted-prefix terminal-
closure proof descriptors. The entry-list value is exactly
`human_curation_scope_entry_list_sha256 =
SHA256(b"FinProof/HumanCurationScopeEntryList/v1\x00" ||
canonical_bytes(complete_entries_in_contiguous_execution_ordinal_order))`; the complete entry objects,
not descriptor concatenation or a reordered projection, are hashed. Each entry reproduces that
`scope_batch_id` and binds its contiguous zero-based execution ordinal, lane/checkpoint, the matching complete
approval-record descriptor/hash, exact `global_budget_slot_id`, and a closed obligation `oneOf`:
`must_execute` or, only for sealed
candidate-cycle ordinal 1, `conditional_remediation_child` with parent/child identity and base SHA-
256. Locked entries bind their exact named competition-global slot and forbid candidate-cycle fields;
sealed entries require the byte-identical complete ordinal-0 or ordinal-1 `candidate_cycle_identity`,
including its distinct slot. The conditional child's actual `{scope_batch_id, execution_ordinal}` must
byte-equal the prospective pair frozen in `conditional_child_base`, and the approval, child base, slot
source and row all reproduce that pair; cross-batch/ordinal replay is invalid. The approval/child-base/
slot source must otherwise reproduce the complete candidate identity. The only durable scope edge is `scope_and_slot_prepare_commit`: after all approval records and the
optional bounded child-base are immutable, it holds the trusted clock/current predecessors, builds and
content-addresses the head-independent schedule, computes and content-addresses the scope record that
contains its exact ref, and finalizes
each complete `suite_preclaim_basis` with that exact scope SHA; computes the two reservation plans and
plan hashes per entry; then builds the strict head-independent
`scope_and_slot_prepare_basis_projection` and derives the typed subject/state/guard/binding. It next
builds every ordered entry's head-independent slot source, candidate human transition, sequential permanent slot-
preparation row/receipt, both prepared storage receipts/allocations and one final candidate slot-
preparation current pointer, and commits the human/slot-preparation/storage states under one authority-
guarded multi-store CAS. A scope therefore never becomes current without prepared capacity for every
obligation and its fail-closed terminal/audit suffix; a guard conflict or capacity failure writes no
scope. For a scope containing the conditional child, the action persists the already hashed child-base
before the scope and the scope entry binds its descriptor/SHA. The child-base/scope/governance records
count inside the fixed 32-record/33,554,432-byte human-governance allowance; suite allocations price
their own later history/control bytes. If the common CAS loses, no authoritative scope/human row,
slot row/current pointer or `prepared_scoped` state becomes visible. The only permitted loser bytes are
unreachable provisional `prepared` allocation/receipt objects; the reaper must prove combined-
transaction nonmembership before abort-tombstoning/reclaiming them. Exposure binds the
scope record and completed-scope record, grant surface, and grant tick. The scope-completion record
binds the complete ordered obligation-resolution proof descriptors for every entry, the guarded global
head, completion tick, and literal `all_scope_obligations_resolved: true`. The conditional proof must
be exactly one of parent-pass closure, parent-pretruth-burn closure, parent-withdrawal-only closure,
owner-decline closure, owner-resolution-expired closure, activated-child report/burn closure, an exact
`scope_schedule_deadline_close` plus direct zero-channel audit for any unclaimed affected entry, or an
exact `authority_conflict_preclaim_close` suffix covering this entry. The authority branch requires the
typed close source plus every direct zero-channel audit through the final affected entry and can only
complete the whole remaining contiguous scope suffix permanent non-PASS. The withdrawal branch binds the exact
`adjudicated_target_report_receipt_ref`, direct `not_activated_parent_withdrawal` resolution and
immediately following zero-channel audit head. No record contains candidate/
output bytes. Every object is strict, canonical, bounded
to 1,048,576 bytes, and private; one scope lineage has at most 32 records and 33,554,432 total bytes.
The generated maximum-occurrence table is exact: each of four successful reviews uses one session-
start transition receipt, one interval record, one combined session-completed/approval transition
receipt and one approval record (16); shared child base, schedule, scope, scope-transition receipt,
completion, completion-transition receipt, exposure and exposure-transition receipt use eight more;
and strict `$defs/human_review_session_proof_bundle` contributes exactly one `start` and one `terminal`
proof-bundle record per review (eight). That proof bundle contains only its session key, old/new root
proofs, branch role and `session_transition_basis_sha256`, where the latter is exactly
`SHA256(b"FinProof/HumanReviewSessionTransitionBasis/v1\x00" || canonical_bytes({session_key,
prior_state_descriptor, candidate_state_descriptor, branch_role}))`; that projection forbids roots,
proofs, bundle/receipt descriptors, heads and its own digest. The bundle is capped at 1,048,576 bytes and cannot be
used by scope/completion/exposure branches. Those three shared transitions instead embed their bounded
complete proof arrays inside their own transition receipts; they may not allocate another proof record.
No other auxiliary/descriptor record kind exists. Active/terminal session state and
the authenticated access context are embedded in the applicable transition receipt/index value, not
extra records. A conflict/expiry terminal substitutes for that entry's interval/completed/approval
slots and cannot coexist with an approval. The max-shaped four-entry witness proves both 32 records and
33,554,432 canonical bytes; a 33rd occurrence or separate duplicate context/state is invalid.
The private governance store preallocates that fixed allowance before review and rejects over-cap
bytes before parsing, so suite execution cannot exhaust it after output exists.

Human-governance genesis is
`SHA256(b"FinProof/HumanGovernanceGenesis/v1\x00" || canonical_bytes({registry_id, version: 1}))`.
A transition receipt contains exactly registry/genesis, contiguous sequence, prior head, transition
kind (`review_approved` for open-only review, `review_session_started`,
`review_session_completed_and_approved`, `review_session_authority_conflict_tombstoned`,
`review_session_expired_aborted`, `scope_committed`, `scope_completed`, or
`output_exposure_granted`), stable
principal, ordered new-record descriptors/hashes, old/new index roots, branch-exact proof evidence,
branch-typed expected/resulting authoritative global heads when scope or terminal-closure proofs apply,
observed clock/tick, and resulting head. For `scope_completed`, those global heads are the exact
multi-revision transaction's initial guarded predecessor and final obligation-closure head. An unused
conditional child requires ordered parent report/burn when applicable, `candidate_cycle_resolution`,
and `slot_private_audit_closed`, so the final head is that zero-channel audit closure; an authority-
conflict suffix instead requires the exact preclaim-close transition and ordered zero-channel audits
for every affected entry, ending at that suffix's final audit head. An activated
child uses its report/burn closure head. The receipt carries every intermediate attestation descriptor/
hash so none can be skipped or substituted. A review-session start/terminal branch requires exactly
one external `human_review_session_proof_bundle` descriptor/hash plus byte-identical
`session_transition_basis_sha256` with matching role and forbids inline
proofs; scope/completion/exposure require their complete bounded proof array inline and forbid an
external human-governance proof-bundle record. For
`scope_committed` and `output_exposure_granted`, both equal the same unchanged current global head.
Other transition kinds
forbid them. The resulting-head
field is excluded from its entry projection; the head is
`SHA256(b"FinProof/HumanGovernanceTransition/v1\x00" || prior_head_32_bytes ||
canonical_bytes(entry_projection))`. Genesis alone has sequence zero/null prior. The witness carries
the pinned current-state receipt plus exactly the bounded records/proofs needed for approval/scope/
completion/exposure membership or nonmembership. Reset/fork/delete, wrong prior/sequence, record/
proof omission,
or a caller-selected ancestor fails before slot preparation or access.

The authenticated index map uses Sparse Merkle Map v1. Each map key is
`SHA256(index_name_ascii || b"\x00" || canonical_bytes(key_object))`; the key object is the exact
closed Canonical JSON v1 object in the table below, never delimiter-joined text. An occupied leaf is
`SHA256(b"FinProof/HistoryIndexLeaf/v1\x00" || key_sha256 || value_record_sha256)`; an empty leaf is
`SHA256(b"FinProof/HistoryIndexEmpty/v1\x00")`; and each of the 256 parent levels is
`SHA256(b"FinProof/HistoryIndexNode/v1\x00" || left_32_bytes || right_32_bytes)`. Bit order is most-
significant first. Membership/non-membership proofs contain exactly 256 ordered sibling hashes and
the prior leaf state. A transition validates the old proof, exact new private record, and recomputed
new root before the global CAS. Every value uses the exact absolute `$ref`
`https://finproof.local/schemas/evaluation_suite_history_attestation.schema.json#/$defs/index_values/<name>`.
The closed registry is:

| ASCII index name | Exact key-object fields | Mutation rule |
|---|---|---|
| `case_content` | `case_content_sha256` | append-only |
| `normalized_question` | `normalized_question_sha256` | append-only |
| `truth_fingerprint` | `truth_fingerprint_sha256` | append-only |
| `disjointness_public_handle` | `disjointness_receipt_public_handle` | append-only |
| `semantic_equivalence` | `semantic_equivalence_class_id` | append-only |
| `case_registration` | `registration_ordinal` | append-only |
| `derivation_edge` | `parent_case_record_sha256`, `child_case_record_sha256` | append-only |
| `suite_version` | `suite_id`, `suite_version` | append-only |
| `suite_disclosure` | `suite_id`, `suite_version` | append-only |
| `slot_state` | `global_budget_slot_id` | typed mutable |
| `opportunity_id` | `opportunity_id` | append-only |
| `organizer_evidence` | `authority_method`, `authority_object_id`, `source_artifact_sha256`, `organizer_ordinal` | append-only |
| `release_cycle_id` | `release_cycle_id` | append-only |
| `candidate_cycle_id` | `candidate_cycle_id` | append-only |
| `candidate_cycle_state` | `release_cycle_id`, `candidate_cycle_ordinal` | typed mutable |
| `remediation_authorization` | `parent_release_cycle_id`, `child_release_cycle_id`, `parent_candidate_cycle_id`, `child_candidate_cycle_id` | append-only |
| `report_lineage` | `report_id` | typed mutable |
| `disclosure_dependency` | `source_report_id`, `source_report_revision`, `source_complete_public_report_sha256`, `target_report_id`, `target_report_revision`, `target_complete_public_report_sha256`, `dependency_kind` | append-only |
| `bound_sink_state` | `global_budget_slot_id` | typed mutable |
| `receipt_identity` | `receipt_kind`, `receipt_id` | append-only |

The `disjointness_public_handle` value contains exactly suite ID/version and the lane-conditional
complete candidate-cycle/checkpoint identity. The same fingerprint/claim CAS proves the 64-lowercase-
hex handle absent under the observed old root, inserts exactly that value, and binds the old/new proof
plus private receipt descriptor/hash/handle in the HMAC-authenticated history transition source. An
occupied handle, missing proof/value, alternate identity or insertion outside that CAS rejects. The
generated history occurrence table charges exactly one index value and one 256-sibling proof for each
non-open disjointness receipt under the existing per-transition/suite record, proof and byte caps.

For `remediation_authorization`, the key is not merely well typed: its
`parent_release_cycle_id` equals both the complete parent identity's release cycle and the child
identity's `parent_release_cycle_id`; its `child_release_cycle_id` equals the complete child identity's
release cycle; and both candidate-cycle IDs equal their respective complete identities. Parent/child
release-cycle or candidate-ID substitution changes the key and is rejected against the authorization
value and current parent/child leaves.

The separate private sink registry uses the same frozen Sparse Merkle algorithm but a distinct closed
three-index table: append-only `sink_coalescing_key` keyed by `{global_budget_slot_id, token_sha256,
fence_epoch}`, append-only `sink_receipt_identity` keyed by `{receipt_id}`, and typed mutable
`sink_current_state` keyed by `{global_budget_slot_id}`. Its values and proofs remain private-history
records. The global `receipt_identity` index excludes sink receipts; the global `bound_sink_state`
value records only the last private sink head/watermark already consumed by a required global
successor. Index-name domain separation prevents a proof from one registry/table being replayed in
the other.

Private sink-registry genesis is
`SHA256(b"FinProof/OutputSinkRegistryGenesis/v1\x00" || canonical_bytes({sink_registry_id,
history_registry_id, version: 1}))`. Its transition receipt contains exactly sink registry/genesis,
history registry/slot/suite, `audit_subject_kind` (`claimed_run`, `never_activated_conditional`, or
`never_claimed_preclaim_close`), branch-conditional run, complete candidate-cycle/conditional-child-
base identity, or preclaim-close source identity, contiguous registry and per-slot receipt sequences, prior registry
head, transition kind (`receipt_appended` or `slot_audit_closed`), exact content-free receipt/ledger-
step descriptor hashes when applicable, old/new three-index roots, proof-bundle descriptor/hash,
prior/new per-slot watermark and ledger HMAC, clock/tick, and resulting registry head. The resulting-
head field is excluded from its entry projection; the head is
`SHA256(b"FinProof/OutputSinkRegistryTransition/v1\x00" || prior_head_32_bytes ||
canonical_bytes(entry_projection))`. Genesis alone has sequence zero/null prior. A receipt transition
atomically stores the private sink receipt/ledger step/proofs and advances all applicable indexes/
heads or none. `audit_subject_kind: claimed_run` requires a non-null run and the ordinary destruction
proof. `never_activated_conditional` requires null run, zero receipt sequences/watermarks, null ledger
HMAC, nonmembership-to-closed `sink_current_state` proof, the exact resolution head, and no channel/
destruction fields. `never_claimed_preclaim_close` requires the typed authority-or-schedule close
source, matching preparation/allocation/nonmembership proofs, null run/conditional-child/lifecycle/
channel fields, zero sequences/watermarks, null ledger HMAC, and the same nonmembership-to-closed sink
proof. The two zero-channel branches are mutually exclusive and neither may carry a lifecycle event.
An audit-closure transition additionally proves every applicable channel closed
and forbids a later receipt. The history reader/witness streams these strict bounded records; an opaque sink HMAC
alone cannot establish registry continuity.

The separate private human-governance registry also uses that algorithm under its own pinned ID/
genesis/current-head and closed append-only indexes: `human_review_approval` keyed by
`{human_principal_attestation_sha256, suite_id, suite_version}`, `human_curation_scope` keyed by
`{human_principal_attestation_sha256}`, `human_scope_completion` keyed by
`{human_principal_attestation_sha256, scope_record_sha256}`, and `human_output_exposure` keyed by
`{human_principal_attestation_sha256}`. It additionally has one typed mutable
`human_review_session` index keyed by
`{human_principal_attestation_sha256, suite_id, suite_version, case_set_revision}`. Its only edges are
nonmembership to `active`, then that exact active value to one immutable terminal
`completed|authority_conflict_tombstoned|expired_aborted`; no replacement, second active value or reset
is legal. Each start/terminal human-governance transition receipt and witness carries the exact old/new
root proofs and complete session-state descriptor/hash, and the current signed human-governance state
authenticates the resulting root before any hidden read or approval. Reset, fork, deletion, any other occupied-leaf rewrite, or registry-domain
replay is invalid. A scope value contains one immutable batch ID and the complete ordered set of
approved slot/suite/case-set/reserve-subject entries; each entry names a pre-exposure completed review-
approval receipt, the case-set commitment that already binds every ordered evidence-package
descriptor/commitment, exclusion commitment, approval tick, and
an exact obligation kind. The first three canonical entries use `must_execute`; the fourth is
`conditional_remediation_child` and binds the pre-output reviewed child case-set/reserve subject,
parent/child candidate-cycle IDs and ordinals 0/1, and its closed activation predicate. Ordinals are
contiguous. Dispatch of ordinal `k > 0` requires every earlier unconditional entry to have reached its
immutable `report_recorded` or burn closure; the conditional child additionally requires its unique
activation transition.

The governance-locked order is exactly one nonempty suffix of
`[POST_PHASE_2_DETERMINISTIC_ENGINE, POST_PHASE_3_HCX_PLANNER_API,
RELEASE_CANDIDATE(candidate_cycle_ordinal=0),
RELEASE_CANDIDATE(candidate_cycle_ordinal=1, conditional_remediation_child)]`. The two sealed entries
belong to the same organizer opportunity, are disjoint, and the child is fully curated/reviewed and
storage-reserved while the combined human remains blind, before any parent dispatch. No entry may be
duplicated, permuted, moved backward, or omitted after output exists. The scope must include every
required entry not already terminal in the authenticated basis global state; a shorter suffix is legal
only when each omitted prefix closure proof resolves against that exact state. At the initial
competition state the only legal scope is all four entries. The parent claim is forbidden until the
child's permanent slot preparation, one-member dormant reserve batch, case/truth reuse indexes, and
full private-control/history capacity are already durable. The single
`scope_and_slot_prepare_commit` transaction read-locks the basis global head unchanged and atomically
advances the human-governance head, the sequential slot-preparation registry and every prepared-
allocation generation, so a closure/read/slot race loses. Only later scope-completion and exposure
transactions compete on that resulting authoritative human-governance head. Scope completion occurs exactly
when the child has resolved by one exhaustive terminal path: parent pass closes it
`not_activated_parent_pass`; parent pre-truth burn closes it `not_activated_parent_burn`; an owner
withdrawal-only parent adjudication closes it `not_activated_parent_withdrawal`; an owner decline
closes it `owner_declined_nonpass`; owner-decision expiry closes it
`owner_resolution_expired_nonpass`; a parent schedule close writes
`not_activated_parent_schedule_deadline`/`closed_parent_schedule_deadline`; an authority-preclaim suffix writes
`closed_parent_authority_conflict`; or an activated child reaches its own report/burn closure.
For any nonactivation path, the transaction computes the branch-exact resolution successor and
then its immediate zero-channel audit-closure successor; only then does it derive the completion record
from that audit head and all prior closure proofs. The parent schedule-deadline branch additionally
requires the parent's later `never_claimed_preclaim_close` audit and derives completion only from both
ordered audit heads. The activated-child path derives completion from its
ordinary report/burn closure. The applicable transaction atomically advances the guarded global, sink,
allocation, and human-governance heads or none. Exposure later conditionally read-locks the exact global current head
`expected == observed`, leaves it byte-for-byte unchanged with no public revision/event, and advances
only the human-governance head. A concurrent global append makes either transaction lose. Every slot-
preparation receipt binds the exact predecessor human head, the one candidate human head containing
the scope, and exact scope/approval/exposure proofs; the combined CAS advances predecessor to candidate
once. No separate slot-preparation action may leave the human head unchanged.
The next already-
required global successor privately binds that head under its ordinary `private_registry_commitment`;
no public event discloses review or exposure timing.

Each key object has exactly the listed properties with `additionalProperties: false`; SHA fields are
lowercase 64-hex, ordinals are nonnegative integers, and other fields use their registered bounded ID/
code types. Missing/extra index names, an inline/alternate value shape, delimiter-joined encoding, or
a caller-chosen root fails closed.

Genesis inserts exactly the two competition-global locked-checkpoint `slot_state: free` leaves, their
zero counters, and empty retired-token ledgers. It inserts no organizer opportunity/evidence,
release-cycle, sealed candidate-cycle, or sealed slot leaf. The first competition opportunity must
use the same authenticated `organizer_opportunity` successor as every later opportunity; no
bootstrap exception may reference a dangling or unverified organizer object. Each such successor
atomically proves empty-to-occupied updates for `opportunity_id`, `organizer_evidence`, the new
two distinct candidate-specific `release_cycle_id` leaves/states, and exactly two fresh candidate-
cycle IDs/states/slot leaves with those same
ordinals/statuses: ordinal 0 is `free`, ordinal 1 is `dormant_conditional`, and both corresponding
public sealed slots begin `free`. `organizer_evidence.authority_object_id` is
the immutable organizer-signed opportunity ID, authenticated official-API object ID, or archived
channel/message ID selected by the method discriminator; `organizer_ordinal` is zero unless that same
authoritative object explicitly grants multiple numbered opportunities. The evidence value binds the
opportunity, source projection/hash, nullable prior organizer-opportunity ID, and the exact ordered two-
entry complete `candidate_cycle_identity` array for ordinals 0 and 1, including each byte-identical
`global_budget_slot_id`.
Its `prior_organizer_opportunity_id` follows the same first-null/later-current rule as the
authorization. A reused opportunity, release-cycle or candidate-cycle ID or
the same authority object/artifact/ordinal under a fresh human-chosen opportunity ID therefore fails
normal transition validation before any new slot/counter can exist; this is not deferred to full
archive audit.

Proof order is exact: descent consumes key bits `0..255` from most- to least-significant, and
`siblings[i]` is the opposite child at depth `i`. Reconstruction starts with the proven leaf and loops
`i = 255..0`; when key bit `i` is zero it hashes `(accumulator, siblings[i])`, otherwise
`(siblings[i], accumulator)`, using the node domain above. Contract fixtures freeze lowercase-hex
roots/proofs for the empty map, one leaf, and two leaves with different first-divergence depths; a bit,
sibling-order, left/right, or domain mutation fails.

Proofs are content-addressed streamed records, never one giant transition field. One
`history_proof_chunk` contains at most 512 proof entries and fits the 16,777,216-byte record cap. The
closed `history_proof_bundle_manifest` binds transition ID, initial/final root map, total proof count,
and ordered chunk descriptors. Proof entries are sorted by the index table ordinal above and then
`key_sha256`; within one index, each entry's `expected_prior_root` must equal the preceding entry's
computed `resulting_root`, so every update is applied sequentially rather than pretending all proofs
share one old root. The first/last values equal the transition's old/new root maps. Duplicate/reordered
keys, wrong intermediate roots, extra chunks, or a proof absent from the manifest fail closed.
At maximum suite size, the registration witness has five base inserts per case plus, for each of at
most eight parents, one parent membership proof, one origin-suite-disclosure proof, and one edge
insert: `10000 * (5 + 8 * 3) = 290000`. At most 10,000 suite-level proofs leave the closed 300,000-
proof registration-transition cap. A separate generated state-machine table accounts for every later
proof, including three private-sink-registry proofs for each of 10,001 one-at-a-time sink receipts and
the bounded global `bound_sink_state` updates, and must keep the full suite at or below 400,000. The
generator rejects any schema/state change that raises either count
rather than silently truncating proofs.

Case-content, normalized-question, truth-fingerprint, semantic-equivalence, case-registration,
derivation-edge, suite, suite-disclosure, opportunity, organizer-evidence, release-cycle,
candidate-cycle-ID, remediation-authorization, disclosure-dependency, and receipt-identity indexes are append-
only: only proven empty-to-occupied
transitions are legal, and overwrite/delete is forbidden. Slot, report-lineage, and bound-sink-state indexes
plus candidate-cycle-state are typed mutable indexes: the old occupied leaf/value hash must match the authenticated predecessor
state and the new record must be one allowed state-machine successor. Occupied-to-empty is forbidden
for every index. A copied new root without the exact old proof, touched record, and legal transition
never establishes continuity.

Derivation acyclicity is incrementally checkable rather than inferred from one absent edge. Registry
state has a monotonic `next_case_registration_ordinal`. Every private case record has one immutable
ordinal, a complete `derivation_parent_ids` array of at most eight unique IDs, and
`has_disclosed_ancestor`. New ordinals
are contiguous in deterministic batch order. Every declared parent must already exist or precede the
child in that same atomic batch, and every edge requires `parent.ordinal < child.ordinal`.
Every case record also binds its origin suite ID/version and lane. The original `report_recorded` CAS
alone atomically inserts that suite's empty-to-occupied `suite_disclosure` leaf; a corrected receipt
must prove and preserve the existing value byte-for-byte and never reinserts/replaces it.
`has_disclosed_ancestor` is exactly OR over each parent's
stored flag, whether its origin suite has a disclosure leaf, and whether its lane is repository-visible
open; a parentless independently curated case sets false. The transition supplies old/new proofs for
the ordinal, case, every parent, edge, and origin-suite disclosure leaf. Locked/sealed admission
requires false. This prevents A-to-B then B-to-A cycles and a disclosed ancestor from being hidden by
an otherwise valid leaf insertion; undeclared human semantic equivalence remains subject to the
independent review attestation and full archive audit.

Actual private cases/evidence packages, derived fingerprints, equivalence assignments, DAG edges,
history appends, reports, and receipts are immutable Canonical JSON v1 records in a content-addressed
custodian archive. Each ordinary record is at most 16,777,216 bytes and has an exact kind/schema/
length/SHA-256 descriptor; the one preclaim `reference_truth_suite_witness` artifact is the sole
dedicated-cap exception at 268,435,456 bytes and is never accepted as a transition-local ordinary
record. Archive manifests are append-only shards of at most 134,217,728 bytes and 200,000
descriptors, linked by predecessor-manifest SHA-256; there is no single ever-growing manifest or
in-memory list. The atomic registry transition stores the new records/descriptors, streams the exact
proof-bundle chunks, advances the exact roots/counters/head, and HMACs the resulting bounded
state. It accepts the complete new suite case/evidence records, never fingerprint-only claims.

Before `reserve_batch` is committed, the archive store streams the complete new suite's private case/
evidence/history records under its head-independent subject and emits an acyclic suite-archive
receipt. The staging-only `$defs/bootstrap_descriptor_manifest` is not an archive shard/head. Its
closed formula-version-1 record table permits, for `N <= 10,000`, at most `N` each of private
GoldenCase (whose expected fields are the truth object), evidence package, private-case fingerprint,
evidence fingerprint, case-set entry, reference-truth-execution request, reference-truth-execution
result, reference-truth-derivation receipt and combined human-approved semantic-equivalence/
derivation-source declaration, plus exactly one reference-executor manifest, one case-set index and
one complete reference-truth-suite-witness artifact.
Thus the schema-derived simultaneous maximum is `9*N + 3 <= 90,003`; the fixed 100,000-record cap is
not a caller-selected allowance and no unnamed bootstrap kind is legal. It explicitly excludes registration ordinals/value records, every
Sparse-Merkle proof/proof-bundle, both storage plans/receipts,
`evaluation_storage_reservation_commitment`, the `reserve_batch` transition subject/private append/
public attestation, and every value derived from that transition. The suite-archive receipt hashes
this staging manifest. After the storage HMAC exists, the winning CAS derives the current-head
registration values/proofs, stores them with the two receipt records and transition subject under the
generated later-record allowance, and emits exactly one actual archive-manifest shard. Thus neither
receipt nor storage HMAC can feed the staging manifest that the receipt hashes, and the one-manifest-
per-transition cap applies only to the actual shard. One private
history record is at most 16,777,216 bytes. The initial case/evidence set is at most 100,000 records and
4,294,967,296 canonical bytes. `compute_private_history_reservation` validates the staging-only
bootstrap descriptor manifest against those caps but reserves the fixed 100,000-record/
4,294,967,296-byte initial allowance,
not an amount derived from private content size. It combines that allowance with a closed generated
table of every later history record kind, exact schema-derived
`max_canonical_record_bytes`, and state-machine `max_occurrences(N)` (including at most 10,001
incremental sink receipts/checkpoints, terminal branches, two reports, one correction, and—for the
conditional child allocation—one owner-remediation authorization, one change-evidence record, one
candidate-cycle resolution, and one zero-channel audit closure, plus exactly one claim-time
reference-executor-disjointness receipt for every non-open suite). Each
max-shaped record witness must fit the per-record cap; unknown/unbounded kinds invalidate the lock.
The plan is rejected before claim if its total exceeds 400,000 records or 34,359,738,368 bytes. The
proof table additionally proves registration needs at most 300,000 and the complete suite needs at
most 400,000 proof entries, 512 per proof chunk, under the eight-parent/10,000-case caps. A separate
generated simultaneous-transition witness includes the maximum 100,000 bootstrap records, 50,000
registration value records, `ceil(300000 / 512)` proof chunks, proof-bundle, receipt, transition, and
manifest descriptors. The lock is invalid unless that witness fits every transition and archive-
manifest record/count/byte cap; proving only the suite-wide total is insufficient.

The store reserves the exact stable accepted plan and emits a private receipt binding receipt/store/
allocation IDs, `slot_preparation_id`, slot-preparation receipt ID/SHA-256, literal
`allocation_kind: private_history`, suite/case-set IDs,
`reserve_batch_subject_sha256`, formula version/plan SHA-256, zero-based `preparation_generation`,
actual staged initial record count/bytes, total reserved count/bytes, remaining count/bytes, ordered
bootstrap descriptor-manifest SHA-256,
`expected_registry_predecessor_attestation_sha256`, predecessor archive-manifest SHA-256, and
allocation timestamp, but no future resulting registry head. Together with the complete private-
control plan/receipt, it is
an input to the secret-backed `evaluation_storage_reservation_commitment`; public reserve-batch,
suite-reservation, fingerprint, claim, and later public objects bind only that commitment and HMAC metadata, never this
receipt ID/SHA, plan SHA, actual count/bytes, manifest SHA, or store metadata. Each later append
atomically decrements the remaining allowance. Exceeding an
initial/generated/total cap stops before claim, so a legal terminal/history/report record cannot fail
for storage exhaustion. A
single transition reads at most 160,000 new records, 17,179,869,184 logical bytes, and one
134,217,728-byte archive-manifest shard with at most 200,000 descriptors; readers count descriptors/
bytes and stop before parsing the first value
past a cap. A parser never materializes the suite total.

Normal transition validation needs only the pinned genesis identity, current authenticated state,
predecessor attestation, candidate append/attestation, touched archive records, and their proofs. An
independent full audit streams archive shards and public attestations from genesis one record at a
time, verifying descriptor hashes, predecessor links, every transition, and final state/head without
materializing the archive. Exact hashes detect byte/canonical reuse; the pre-result human equivalence
classes and derivation edges make declared paraphrased or truth-equivalent reuse mechanically
rejectable across open, locked, sealed, and reserve suites. Review attests declaration completeness;
the machine cannot discover an omitted semantic relationship. Repository handoff checks reject any private-history
record, manifest, proof, or truth-bearing child under registered evaluation-asset roots.

Repository-visible seed cases are permanently `open_regression`. A visible seed ID or payload may
not appear in a locked or sealed truth package, and later human review cannot restore independence
to a case already visible to implementers.

Locked and sealed suites are mutually disjoint across all versions, not merely disjoint from visible
seeds. Before any locked/sealed result disclosure, the independent human must curate, review, and
HMAC-commit exactly one private suite/case-set commitment for each registered global slot. That
one-member reserve batch is the slot's complete hidden denominator; its suite manifest/reservation is
activated later from the unchanged commitment. It is never replaced or replenished. Output- or
truth-informed case selection, abort-and-advance, rewriting, difficulty adjustment, or truth repair
is prohibited.

Each named locked checkpoint likewise permits exactly one result-bearing disclosure. At most one
pre-commit, HMAC-attested and transport-fenced infrastructure retry per suite/version is exempt, but
a successful truth-release commit cannot be followed by another suite at the same checkpoint. The
initial attempt for each invocation has `attempt_ordinal: 0`; the sole suite-wide retry has ordinal 1
for exactly one invocation. Tuning after the first locked checkpoint is
evaluated only at the next named checkpoint with its precommitted disjoint suite.

The sealed stopping rule is stricter than reserve availability. Once one actual organizer-defined
competition opportunity is authenticated, a separate owner-approved FROZEN repository remediation
policy internally preallocates exactly two sealed-evaluation candidate-cycle identities/slots under
it: ordinal 0 and the sole dormant conditional ordinal 1. The organizer artifact proves the external
opportunity exists; it does not assert that the organizer granted two submissions or authored this
internal remediation budget. Before creating the pair, Phase 4 must inspect the first-ranked official
notice/answer and verify the authorization's exact
`official_remediation_compatibility_review`; an absent review or explicit one-attempt, no-correction,
or no-internal-retest conflict stops under AGENTS.md precedence. Each candidate cycle permits at most one result-bearing sealed truth release;
the opportunity counter is their sum and can never exceed two. The one permitted pre-commit, HMAC-
attested and transport-fenced infrastructure retry within a suite does not increment either counter;
every successful sealed `truth_release_commit` increments exactly its candidate-cycle counter and the
opportunity counter, even if a later crash prevents a normal outcome. Any per-invocation attempt
ordinal above 1 is illegal, and at most one invocation may use ordinal 1 across that suite/version.
Opportunity creation does not grandfather any later non-open action against a newer official
instruction or the submission freeze. The first ordinal-0 reserve/claim, as well as opportunity
creation, repeats the same fresh authority validation and holds the three authority resources with the
human/storage/global CAS; a newer conflict stops before selection, review, claim or dispatch. Immediately before owner activation, the activation CAS must read-lock and
verify the complete `submission_freeze_authority_state` against the current first-ranked official-
instruction archive pointer and trusted-clock snapshot. Its activation/checked/current ticks must be
equal. Before the freeze, that tick must precede the effective tick; after it, the tick must lie within
the bound organizer exception and every changed build-resource path must be allowed. A newer conflict,
stale authority snapshot, or owner-only permission loses/stops and can only lead to decline/permanent
non-PASS; it never activates the child.

Ordinal 1 is not a general retry. It is claimable only when its exact suite/case set, selection quotas,
storage, scope entry, and dormant batch were fixed before ordinal-0 output; ordinal 0 is fully reported
invalidated and audit-closed; the distinct owner-remediation authorization passes the cause-typed
build-change rule; and its one-use activation transaction wins. Parent pass or pre-truth burn closes
the child without truth release. Parent invalidation plus owner decline closes it permanently non-
PASS. A withdrawal-only adjudication of the current invalidated parent likewise closes the dormant child
through `not_activated_parent_withdrawal` and is permanently non-PASS; it cannot wait indefinitely for
or race into a later owner activation.
Once activated, the child is mandatory report-or-burn. A later post-pass defect, withdrawal,
adjudication, code/prompt/model/config/schema/artifact/image change, or owner preference cannot reopen
the child, reset either counter, add a third cycle, substitute another child, or hide the ordinal-0
report. A genuinely new organizer opportunity is still required after both preallocated candidate
cycles resolve; the owner-remediation HMAC never mints another slot or organizer opportunity.

This implements the governing remediation design's “newly sealed set” as a different, previously
unconsumed, disjoint, non-derived case/truth set that the corrected candidate first consumes. It does
not mean result-informed selection or sealing after ordinal-0 output: the child case/truth commitment,
review, quotas, reserve subject, and storage are immutable before parent dispatch.

Every sealed report candidate includes only the registry-global
`prior_sealed_disclosure_history_head_sha256` and positive/zero predecessor count, never a copied
ever-growing array. The genesis head is
`SHA256(b"FinProof/SealedDisclosureHistoryGenesis/v1\x00" ||
canonical_bytes({"history_registry_id": id, "projection_version": "1"}))`, using the already chosen
registry ID and no genesis-attestation hash or future value.
After an original/corrected report is durably recorded, the same atomic CAS computes
`SHA256(b"FinProof/SealedDisclosureHistoryEntry/v1\x00" || previous_head_32_bytes ||
canonical_bytes(entry))`, where `entry` has exactly sequence, release-cycle ID, suite/report ID and
revision, the complete candidate-cycle identity, complete public-report SHA-256, private-report
commitment, terminal disposition, and the
exact pre-CAS predecessor history head (`post_outcome` for an original or `post_adjudication` for a
correction). It never contains the future report-receipt head/hash. The resulting head/count live in
bounded authenticated
registry state and in the receipt, not in the report whose hash is the new entry. Per-candidate-cycle
and per-organizer-opportunity caps remain separate counters. A newly authorized organizer opportunity
must start from the latest resulting head/count
and may not hide an earlier failed, revoked, superseded, or corrected report. Full audit streams the
content-addressed history archive. The checker rejects a missing predecessor, wrong sequence/head,
candidate-cycle counter above one, opportunity counter above two, skipped failed report, or “latest
attempt only” projection. This prevents an
arbitrarily large reserve from becoming a run-until-pass stream without making each report grow with
all prior history.

The report schema also exposes validation-only
`$defs/organizer_opportunity_disclosure_summary_v1`, built only after the referenced report receipts
exist. It has exactly the organizer opportunity ID and one or two ordinal-ordered entries; it has no
singular top-level release-cycle ID. Each entry contains its distinct candidate-specific release-cycle
ID through the complete candidate-cycle identity, report ID/revision, complete public-
report SHA-256, public private-report commitment, exact `current_report_receipt_ref`,
terminal disposition, separate eligible/attempted/pass/failure/error/`truth_not_delivered` totals, freeze-fingerprint SHA-
256, and the public candidate/version component hashes already present in that report. The validator
requires every duplicated report/revision/hash/commitment/outbox field equal the receipt ref byte-for-
byte and streams and revalidates every referenced repository-readable public report/outbox.
For a report whose public truth terminal is `revoked_without_delivery`, the summary requires
`eligible == attempted == truth_not_delivered` and pass/failure/error plus every terminal breakdown/
cause token and `not_attempted` to be zero or absent exactly as the report projection requires. For every other branch
`truth_not_delivered == 0` and the ordinary totals byte-reconcile with that public report. Deadline and
authority-conflict revocation therefore produce byte-identical non-opaque summary fields, and no
private cause counter may be copied into this summary. If ordinal 1 ran,
the summary requires both ordinal-0 and ordinal-1 entries and the child `report_recorded` transaction
inserts an append-only `disclosure_dependency`. Its key is exactly the registry table's seven public
fields: parent and child report IDs, revisions, complete public-report SHA-256 values, and literal
`remediation_predecessor`. The strict private leaf value additionally binds the exact
`remediation_predecessor_public_ref` and matching private-witness components; neither is part of the
public key. Report ID
alone is insufficient. Release readiness is derived only from the ordinal-1 result and its own
denominator while retaining ordinal-0 invalidation as visible historical evidence. Version 1 forbids
any combined denominator, numerator, pass rate, breakdown total, or latest-only projection; parent
pass uses its one-entry report and a closed unused child, while parent burn, owner decline, child burn,
or child invalidation is cumulative non-PASS. Any later parent adjudication, correction,
supersession, or withdrawal makes readiness permanently non-PASS and never rewrites the summary,
reauthorizes the child, or revives another cycle.

The same report schema exposes strict validation-only `$defs/cumulative_disclosure_archive_manifest`
and `$defs/cumulative_disclosure_archive_witness`. One append-only content-addressed manifest shard has
manifest version, nullable prior-manifest digest, first/last global disclosure sequence, entry count/
byte count and an ordered finite descriptor array. Every descriptor resolves one exact sealed-
disclosure-history entry plus its public report/receipt/outbox identities and terminal disposition;
originals, corrections, later-withdrawn historical reports and failures remain present forever. The
witness contains the registry/genesis, independently current sealed-disclosure head/count, authenticated
aggregate manifest/entry/byte totals and ordered shard descriptors from genesis. Validation streams all
shards/entries and recomputes the exact chained head/count. Every predecessor result-bearing report
must remain repository-discoverable/readable. Only for `enable_outbox` may the one target entry be the
durable receipted canonical embargoed outbox that this same transaction makes readable; an absent or
already divergent target is invalid. The current one-or-two-entry opportunity summary is only a checked
subprojection and can never hide an earlier opportunity.

The strict private `$defs/release_report_validation_dossier` is a small action-discriminated root, not
an inline array. It contains exactly dossier/schema versions, action identity/nonce/kind/expiry,
branch-fixed target/opportunity/cycle identities, one complete
`release_report_validation_entry_manifest` descriptor/hash, aggregate entry/shard/canonical-byte
counts, and the branch-conditional current archive head/count. It contains no secret key, caller
success boolean, entry array, proof bytes, resulting state/head or action receipt and is capped at
134,217,728 bytes before parsing.

The strict validation-only `$defs/release_report_validation_entry` is descriptor-only. Common fields
are ordinal, exact current/historical lineage status and candidate-cycle identity plus bounded exact
descriptor/hash references for suite manifest, freeze fingerprint, public report, closure receipt and
outbox. `already_readable` requires its immutable verified-publication-receipt descriptor/hash. The
sole `pending_target` branch instead requires the exact current unsuperseded lineage state
(`current_original` or `current_corrected`), complete private-report HMAC reference and bounded
descriptor/hash references for the private report, private-control predecessor pointer/attestation/
snapshot, checkpoint provenance when applicable, reference-truth witness/dependencies and mutable
lineage/scope/audit/sink proof bundle. For a revoked target it additionally requires the exact private
`revoked_publication_not_before_tick` from the HMAC-verified terminal receipt/report; every other entry
forbids that field. A pending target forbids any verified-publication receipt/signature/publication
tick/resulting pointer/snapshot/visibility result. The complete referenced bytes are streamed and
validated; the compact entry never inlines them.

`$defs/release_report_validation_entry_shard` contains exactly shard version, zero-based shard ordinal,
first global entry ordinal, 1..512 ordinal-contiguous complete entries, its entry count/byte count and
`shard_entry_list_sha256 = SHA256(b"FinProof/ReleaseReportValidationEntryShard/v1\x00" ||
canonical_bytes(complete_entries_array))`; that digest is not over the enclosing shard.
`$defs/release_report_validation_entry_manifest` contains exactly version, action identity/kind,
aggregate entry/shard/canonical-byte counts, 1..196 ordinal-ordered content-addressed shard descriptors
plus their entry counts/list digests, and
`shard_descriptor_list_sha256 =
SHA256(b"FinProof/ReleaseReportValidationShardList/v1\x00" ||
canonical_bytes(ordinal_ordered_{shard_ordinal, shard_descriptor, entry_count,
shard_entry_list_sha256}_array))`. The manifest/root/shards forbid
their own descriptors/hashes, future action/current heads and release-action receipts. Validation
streams each shard, rejects gaps/duplicates/permutations, recomputes every descriptor/list root and
requires aggregate entries <= 100,002 and aggregate canonical shard bytes <= 137,438,953,472 before
resolving referenced reports/proofs. Each shard is capped at 67,108,864 bytes before parsing. The
generated simultaneous maximum witness proves exactly two locked entries plus 100,000 cumulative sealed
entries (100,002 total) fit 196 shards and all four caps; entry 100,003, shard 197, 513 entries in one shard or any cap plus one
byte rejects.

For `enable_outbox`, the manifest has exactly one `pending_target` plus any `already_readable`
predecessors needed by that target. For `release_readiness` and `submission`, it contains exactly one
current unsuperseded entry for each named locked checkpoint in policy order and exactly one
`already_readable` entry for every cumulative sealed disclosure; a pending-target variant is illegal.
The verified receipt—not the dossier entry—binds the complete private report, its pre-enable private-
control pointer/attestation/snapshot, provenance/reference dependencies and complete private-report
HMAC reference. These content-addressed validation objects live only in the bounded custodian
prevalidation workspace, are not authoritative records or action outputs, and may be reaped after the
call; the request/dossier hash binds the complete root/manifest/shards. Every branch binds the action
identity/nonce, requested action kind and expiry; only the final transaction supplies the freshly read
authority/registry lease and generations.
The strict custodian-private `$defs/verified_published_report_receipt` contains exactly receipt/
validator/projection versions, report/suite/checkpoint/candidate identities, action nonce, complete public/private
report and outbox hashes, private-report HMAC reference, fingerprint and immutable bundle/snapshot/
reference-suite/provenance descriptor digests, publication-time lineage/current-pointer tuples,
publication tick, branch-conditional private `revoked_publication_not_before_tick`, verifier service/
image/config identity, literal signing purpose
`verified-published-report-signer`, signing controller, key-resource ID, key ID, immutable public-key
fingerprint, signature scheme/version `ED25519_VERIFIED_PUBLICATION_V1`, and exactly one canonical
base64 encoding of a 64-byte Ed25519 signature. Every signing field equals the one exact immutable
deployment-trust row; owner/store/identity/signer keys and cross-purpose reuse are forbidden. The
publication-time pointer tuple is exactly the independently read pre-enable private-control pointer,
attestation and snapshot. It excludes its signature from the signed projection and excludes its own
descriptor/digest, the same-action resulting snapshot/pointer/attestation, every future readiness/
action/store receipt or resulting head and every secret from the object. The
signature message is
`b"FinProof/VerifiedPublishedReport/v1\x00" || canonical_bytes(receipt_without_signature)` and its
public-key fingerprint/role is independently pinned in the immutable deployment trust manifest.
For a revoked report the private not-before tick is required and byte-equal to the terminal/report;
for every redeemed/open report it is null/absent. It never appears in the public report, outbox or
branch result.
`VerifiedPublishedReportReceiptReader` resolves the receipt by exact descriptor/length/SHA-256 and
Phase 4 verifies its signature; key/resource rotation stops this design. The reader is never called
for an enable branch's pending target. `ReleaseReportDependencyReader.read_validation_manifest()` and
`read_validation_shard()` first stream the dossier-bound manifest/shards under the per-object,
entry/shard and 137,438,953,472-byte aggregate caps; its dependency methods then resolve only the
bounded current mutable lineage/scope/audit/sink proofs and public immutable
artifacts needed to join each receipt to the final guard. `PrivateReportHmacVerifier` is used only by
the target `enable_outbox` branch to secret-verify the exact private projection/reference; neither
protocol may return a caller-authored boolean.

Release actions have one independently current, deployment-global, custodian-private no-reset store.
The strict `$defs/release_action_state` contains exactly state version, pinned resource/genesis/store/
allocation IDs, complete reservation-plan/receipt descriptors/hashes, zero-based state sequence,
occupied action count, used/remaining reserved entries/bytes, Sparse-Merkle action-identity root and
immutable empty-root formula version. Its generation-zero state has sequence/count zero,
used logical bytes 3,162,112, remaining entries 100,256, remaining logical bytes
2,199,020,093,440, and
the exact 256-level Sparse Merkle Map v1 root recursively derived from
`SHA256(b"FinProof/HistoryIndexEmpty/v1\x00")` and
`SHA256(b"FinProof/HistoryIndexNode/v1\x00" || left_32_bytes || right_32_bytes)`. The registered
ASCII index name is `release_action_identity`; its closed key object is a strict branch `oneOf` whose
members are derived from authenticated history, never caller IDs. `enable_outbox` is exactly
`{action_kind:"enable_outbox", report_id, report_revision}` for both locked and sealed lanes.
`release_readiness` and internal `submission` are exactly `{action_kind,
organizer_opportunity_id, release_cycle_id, candidate_cycle_ordinal}` with action kind fixed to the
selected branch and no report/artifact member. The key/action-
identity digest is exactly
`SHA256(b"release_action_identity\x00" || canonical_bytes(key_object))`; its 256-bit path uses MSB-
first order. Occupied leaf and parent formulas are the same
`FinProof/HistoryIndexLeaf/v1` and `FinProof/HistoryIndexNode/v1` formulas above, and every membership/
nonmembership proof has exactly 256 ordered siblings plus prior leaf state. Genesis is
`SHA256(b"FinProof/ReleaseActionGenesis/v1\x00" || canonical_bytes({resource_id, store_id,
state_version:"1"}))`; neither genesis nor the
generation-zero state/attestation contains its own/future digest or either deployment-manifest digest.
The externally built deployment manifest pins that already complete generation-zero tuple; later
completion bases/leaves bind the complete manifest digest without feeding it back into genesis. An occupied leaf is immutable
and contains exactly action identity/nonce, action kind, request/dossier digest, strict
`release_action_completion_basis_sha256`, status `completed`, and the content-addressed branch-result
record descriptor/hash. Branch results are exactly `enable_outbox` (verified-publication receipt and
visibility target), `release_readiness` (the complete immutable readiness payload), or `submission`
(the complete internal submission package/intention payload). They contain no secret key or future state/attestation/store
receipt. The prepared deployment reserves 100,256 leaves and 2,199,023,255,552 archive bytes; a full
store stops before accepting another action rather than stranding a report.

Before generation zero, the store builds strict head-independent
`$defs/release_action_store_reservation_plan` with formula version `1`, pinned resource/genesis/store/
allocation IDs, exactly `100000 + (64 * 2 * 2) = 100256` maximum actions, the 16,777,216-byte maximum
branch-result-record size, 1,048,576-byte state, 1,048,576-byte action-receipt and 16,384-byte current-
attestation slots. The fixed logical `per_action_charge_bytes` is therefore `18,890,752`; with the two
1,048,576-byte plan/receipt objects and one generation-zero state/attestation slot, the exact maximum is
`100256 * 18890752 + 2 * 1048576 + 1048576 + 16384 = 1893914394624`, no greater than the fixed
2,199,023,255,552 reserved archive bytes. Its generated simultaneous max witness proves that exact
integer sum; averages, compression and caller margins are forbidden. The strict
`$defs/release_action_store_reservation_receipt` binds only that plan descriptor/hash, allocation,
reserved counts/bytes, creation tick and store enforcement version; it forbids generation-zero state/
attestation, deployment-manifest digest, future action/result/head or own digest. The store durably
reserves the allocation before constructing generation zero. The immutable deployment manifest then
pins only the release-action generation-zero attestation/checkpoint tuple: resource/genesis/generation/
store version, complete attestation bytes and digest, and the signed state digest. It never contains
the complete custodian-private generation-zero state, reservation plan or reservation receipt. The
`ReleaseActionCurrentResourceReader` resolves the exact state authenticated by that digest, and the
`ReleaseActionStoreReservationReader` separately resolves the plan/receipt descriptors and hashes
committed by the state. Complete plan/receipt/allocation IDs, creation ticks, store-enforcement values
and state bytes are forbidden from the deployment manifest, report, outbox and every public artifact;
only the complete manifest digest and public-safe generation-zero checkpoint commitments may cross
that boundary. Every winning action CAS inserts exactly one
bounded result record, increments used/occupied counts and decrements remaining entries by one and
remaining logical bytes by exactly 18,890,752. Actual object lengths are separately audited and may
not alter that same-transition charge; insufficient or inconsistent allowance loses before any branch
write. At every generation `used_logical_bytes + remaining_logical_bytes == 2199023255552`; the
generated g0, maximum-action and one-action-over witnesses prove this equality and the entry cap.
`ReleaseActionStoreReservationReader.read_prepared_allocation(resource_id, genesis_sha256,
allocation_id)` independently returns the bounded plan/receipt bytes and backend allocation/capacity/
enforcement evidence. The deployment-pinned release-action-store attestor must recompute the plan,
verify that exact real allocation and enforcement version, and only then sign generation zero; the g0
current attestation is the sole authenticated wrapper and no new signature purpose is invented for the
private preparation receipt. Task-3 validation checks all bytes/cross-bindings; Phase 4 verifies the
real allocation and attestor signature. A caller-authored/fabricated/undersized/wrong-allocation/stale-
enforcement receipt cannot establish g0.

The strict `$defs/release_action_branch_result` is the complete prepaid immutable artifact and is a
closed `oneOf`. `enable_outbox` contains only action/target report ID/revision, outbox descriptor/hash,
verified-publication-receipt descriptor/hash and literal `visibility_class: controlled_review`.
`release_readiness` contains the complete deterministic public-safe readiness payload: payload/policy/
schema/deployment versions, opportunity/release-cycle/candidate-cycle identity, exact public report/
outbox hashes, permitted public history commitments/heads, disclosure head/count and terminal readiness
decision. It expressly forbids every private dossier/receipt/proof/plan/pointer descriptor or digest;
the private request/completion basis/action leaf alone binds the exact cumulative and two-locked dossier
hashes. `submission` contains
the complete internal package/intention payload: payload/contract versions, the same stable cycle
identity, completed readiness-action identity/result hash and the finite ordered canonical package-
entry descriptors/hashes. It is not an external organizer-send receipt. Every branch forbids copied
private payload, secret, future release-action state/attestation/store receipt, full action receipt or
its own descriptor/digest. The branch-result record's own kind/schema/length/SHA-256 descriptor is
external, computed only after canonical serialization, and appears only in the completion basis/action
leaf. No separately stored readiness artifact or submission package exists. The complete result is
capped and prepaid at 16,777,216 bytes before parse and resolved only through
`ReleaseActionBranchResultReader`.

The strict `$defs/release_action_completion_basis` contains exactly basis version, deterministic
action identity/nonce, action kind, governance/deployment/policy versions and digests, request/dossier
hashes, target/artifact hashes, observed authority/registry/identity/private-resource tuples and tick/
expiry, branch-conditional private `revoked_publication_not_before_tick`, plus the intended branch-
result descriptor/hash. That field is required and byte-equal across the terminal receipt, private
report, dossier and verified-publication receipt only for a revoked `enable_outbox`; it is forbidden in
every other action. The basis expressly forbids candidate/resulting
release-action state/root/generation/attestation, resulting private-control pointer/snapshot, branch-
store receipt, complete release-action receipt and every own/future digest. The strict
`$defs/release_action_current_attestation` signs exactly literal kind `release_action_current`, pinned
resource/genesis/store IDs, CAS generation, state sequence/count/root, complete canonical-state SHA-
256, prior complete-attestation SHA-256, store-monotonic epoch/version, scheme
`ED25519_STORE_ATTESTATION_V1`, deployment role `release-action-store-attestor`, key-resource/key IDs
and public-key fingerprint. It removes only its canonical base64 64-byte signature from the signed
projection and signs
`b"FinProof/ReleaseActionCurrent/v1\x00" || canonical_bytes(attestation_without_signature)`.
Generation/store version advances contiguously; reset, fork, delete, occupied replacement and alternate
genesis/key are invalid. Lane/checkpoint/opportunity/cycle/outbox/artifact and governance/deployment/
policy digests remain in the request, completion basis and occupied value, never in the enable key, so
drift cannot create a second enable key for the same globally unique report/revision. Generated locked-
enable, sealed-enable, readiness/package, empty-root, first-insert, membership/nonmembership, bit-order and
sibling-mutation vectors are mandatory.

The strict `$defs/release_action_current_witness` contains the independently read current state/
attestation/store-read receipt and exactly the action-key membership or nonmembership proof plus, for
a completed replay, the immutable historical candidate state/attestation and leaf-bound branch-result
descriptor/hash. It never contains a branch-store receipt. `ReleaseActionCurrentResourceReader`
provides four closed methods: `read_current()` returns only the current state/attestation/store-read
receipt; `read_current_action(action_identity)` atomically returns that same current tuple plus a proof
against that exact current root and the leaf-bound branch-result bytes;
`read_current_actions(action_identities)` accepts only the gate-internally derived ordered tuple of one
or two identities and atomically returns one current tuple/root plus the corresponding one or two
proofs and leaf-bound results against that same root; and
`read_action(action_identity)` returns the immutable historical candidate tuple/proof/result used only
for completed replay. They return only canonical bounded bytes from the pinned resource and never
accept a caller-selected current state. Phase 4 verifies the deployment-pinned signatures,
proofs and real CAS. For a new action the construction order is completion basis/branch result -> leaf
and candidate state -> candidate current attestation -> one multi-resource CAS; the returned
`release_action_receipt` is assembled afterward and is absent from the candidate state. The CAS
advances this release-action resource and, only for `enable_outbox`, the prepaid private-control
receipt/snapshot/pointer while the authority/current guards remain held. No separate outbox-access or
visibility state exists; the completed current-root action leaf is the sole readability authority.
Readiness/submission create no separate secondary resource.

Pure `published_report_errors` and `release_readiness_errors` return diagnostics only and do not
authorize a later action. The only authorizing Phase-4 boundary is `ReleaseActionTransaction.execute`.
Within that one call, before taking any mutable-resource lock, the transaction resolves and fully
validates all immutable target/report/reference/provenance bytes and performs exact private-HMAC
verification. The successful result remains an in-process, nonserializable, nonce/request-bound
callback context; it is never returned, persisted or accepted on a later call. The transaction then
atomically acquires the fresh three-authority and five-registry guard plus the independently current
identity-authority and release-action generations and every relevant private-control/ingress generation, rechecks the
exact immutable descriptors from that context, validates only current mutable joins and executes a
strict action `oneOf`. Thus a 1-TiB reference stream never runs while the clock/current resources are
locked, while a successor between prevalidation and the final guard still makes the action lose.
For `enable_outbox`, the short guarded suffix requires the pending target remain the exact current
unsuperseded lineage revision. For either revoked cause it also independently reads the current trusted
clock under the same guard, requires `observed_tick >= revoked_publication_not_before_tick`, and
byte-compares that private tick across the terminal receipt, private report and dossier; a caller cannot
select or omit this branch. It then constructs/signs the verified-publication receipt from the observed
pre-enable pointer and current tick, hashes its descriptor, then constructs the descriptor-appending
same-stage snapshot and resulting signed pointer last. One CAS writes that prepaid record/snapshot/
pointer and inserts the one immutable completed enable-action leaf, and enables only the controlled
review path described below. Readability is derived only by an access reader verifying that leaf's membership under the
independently current release-action attestation, its matching verified-publication receipt and exact
outbox descriptor; there is no separate or caller-controlled visibility leaf/ACL state. None of those writes
may precede the CAS. Later scope obligations may remain incomplete.
The only Phase-4 byte path is the gate-owned
`DisclosureOutboxReadTransaction.read_exact(report_id, revision, outbox_descriptor)`. Its strict
private `$defs/disclosure_outbox_read_context` is produced only by the deployment-pinned
`DisclosureReadinessContextReader.resolve_current(...)` from the held current suite-history lineage.
It contains the exact report/revision/public-report hash/outbox descriptor, stable enable-action
identity and a closed access branch. `controlled_history` proves the requested enabled report is an
authenticated history ancestor and has null readiness identity. `anonymous_current` proves the
requested revision is the exact current nonwithdrawn report-lineage value, derives the current
organizer opportunity and its terminal candidate-specific release cycle from authenticated history,
contains that deterministic release-readiness action identity, and binds the current opportunity
summary/dossier coverage proof showing the readiness payload covers this report. Thus a remediation
parent report derives the child cycle's final readiness identity without any caller-supplied cycle or
hidden lookup key.

The transaction obtains `AuthenticatedAccessSubjectContextModel` only through
`AuthenticatedSessionReader.read_current()`, then takes one coherent read fence over official-
instruction, trusted-clock and submission-state authority resources, the complete independently
current five-registry set (suite history, human governance, sink, slot preparation and nonce), identity-
authority and release-action resources, plus the live transport context. Only history/human proofs
carry disclosure semantics, but all five registry generations from
`CurrentRegistryResourceReader.read_current_set()` are held/rechecked so a late sink/slot/nonce
successor cannot interpose. It
internally derives the complete `outbox_read` subject/state/guard and calls the ordinary typed
authority validator; any current `disclosure_forbidden`/`stop_all_non_open`, stale authority tuple or
ambiguous official instruction denies. It invokes
`ReleaseActionCurrentResourceReader.read_current_actions(...)` with exactly the enable identity for a
controlled branch or the enable and derived readiness identities for an anonymous branch, verifies all
proofs against that one returned current root, and byte-compares the enable result, verified-
publication receipt, outbox descriptor and branch-conditional readiness coverage. Sequential proofs
from different roots are invalid.

Pinned repository-owner and implementer-service contexts may use `controlled_history` before scope
completion, except that a revoked report remains denied before its common private publication-not-
before tick. The read transaction independently rechecks the current trusted-clock tuple and the exact
private tick from the enable receipt/completion basis on every revoked read; missing, early, cross-epoch
or unequal values return the same fixed denial. The curation principal and every current alias/successor are denied until current same-
subject `human_output_exposure` membership exists. Anonymous/repository access requires
`anonymous_current`, current completion for every covered scope, current exposure membership for each
scope's curation principal, and the same-root readiness leaf. `release_readiness` itself rejects unless
those exact completion/exposure memberships are already current; exposure is a prior guarded human-
governance transition, never inferred from readiness. A correction, withdrawal, supersession,
readiness mismatch, identity revocation or authority successor therefore denies a new anonymous read.

The transaction first loads at most `max_public_report_bytes` of immutable descriptor-matched bytes,
then atomically rechecks every held generation/context immediately before the authorization
linearization and returns only those canonical bytes or one fixed denial. It accepts no caller context,
role, current state, proof, receipt, authority witness, opportunity/cycle ID or readiness identity and
exposes no private action/identity/proof metadata or timing-distinct reason. Raw outbox storage is
reachable externally only through this transaction. A prohibition or withdrawal after one authorized
return cannot recall bytes already disclosed; it denies only later reads, while immutable audit ancestry
remains available through controlled review and any current cumulative superseding report.
Accordingly, `repository_disclosure` before scope completion means a controlled owner/implementer
review channel, not an unrestricted repository publication.
`release_readiness` and `submission` additionally resolve the complete cumulative witness and both-
locked-plus-sealed dossier, verify every immutable publication receipt/hash, recheck only current mutable
lineage/authority/identity/sink/audit state and call `release_readiness_errors`. The transaction
performs the exact branch write and only then
returns a strict `$defs/release_action_receipt` bound to the action/artifact hashes, observed generations/
tick, guard/nonce and winning release-action current attestation. The complete receipt and its external digest are
custodian-ACL-private and never enter a UI, repository artifact or public response; it records an
already completed action and is never a bearer token. Before the write, the transaction embeds only a
strict `release_action_completion_basis` containing the action/artifact identity, observed predecessor
tuples and intended branch-result hash; that basis expressly excludes every resulting store receipt,
complete release-action receipt and either digest. The CAS writes the basis plus branch state, then the
returned `release_action_receipt` is assembled as the exact basis plus the winning candidate release-
action current attestation, action-leaf membership proof and leaf-bound branch-result descriptor/hash.
No branch-store receipt or post-write digest is embedded or later required. A replay resolves the
historical candidate attestation/proof/result by deterministic action identity and reconstructs byte-
identical receipt bytes, so neither an unregistered signing purpose, separate unpriced payload nor
a state -> store receipt -> state fixed point exists. The lock generator constructs the maximum 256-
sibling `release_action_receipt`, proves its canonical bytes fit 1,048,576 and rejects
that max shape plus one byte. Before the action, the transaction builds strict
head-independent `$defs/release_authority_validation_projection` containing action kind/nonce, exact
artifact hashes, authority and registry resource/genesis/generation/tick tuples and expiry, while
forbidding resulting history/action/store receipts and every future head. The projection is a transient
custodian/HSM validation message only; its external digest may be bound by the post-write private action
receipt, but it creates no history transition or public commitment. A public readiness artifact carries
no authority-validation digest, tick, generation, guard or action-receipt field. Any successor, lease expiry, crash before the action write, missing historical
entry or stale/revision-substituted dossier causes the transaction to lose; an earlier empty diagnostic
tuple cannot be replayed. `release_action_identity_sha256` and `action_nonce` are the exact same
`release_action_identity` Sparse-Merkle key digest over the selected closed branch key above;
lane/checkpoint/opportunity/cycle/outbox/artifact/governance/deployment digests remain bound in the occupied value and
completion basis but are never part of this uniqueness key. Neither digest is
caller-selectable. The authoritative release-action store permits exactly one absent-to-completed value for
that identity. Before any expensive validation, the transaction first reads the authoritative action
leaf. A matching completed identity plus byte-identical request/dossier digest returns the same
reconstructed receipt without reauthorizing, revalidating a now-historical target or performing a new
public action. Only an absent leaf follows full prevalidation and CAS; an occupied mismatch rejects. A
different nonce, artifact, revision or action for an occupied identity rejects. Under this Task-3
contract, action kind `submission` means only an internal immutable submission-
package/intention write after readiness; it never sends to an organizer endpoint and never fabricates
the actual submission event/receipt required for `submitted_frozen`. Phase 4 may perform a real send
only after a separately frozen adapter proves an authenticated provider query/idempotency capability,
or through an explicit manual handoff. A non-idempotent or ambiguous send enters a fail-closed
`submission_status_unknown` operational stop outside this action contract: no retry, readiness claim,
new nonce or `submitted_frozen` transition is permitted until authenticated organizer/out-of-band
reconciliation supplies the actual receipt. The spec never claims generic exactly-once external I/O.
The strict `$defs/release_action_execution_result` is exactly one of
`{status: completed, receipt: <complete release_action_receipt>}` or
`{status: rejected, diagnostics: <nonempty sorted typed diagnostics>}`. The rejected branch forbids a
receipt/resulting store write and the completed branch forbids diagnostics; exceptions, partial action
claims and fabricated receipts after a stale guard/crash-before-write are not contract results.

Open manifests may enumerate visible case IDs. Locked/sealed manifests may not enumerate individual
case IDs, questions, or truth-bearing fields; they publish counts and the HMAC commitment only.
Failure and case identifiers remain custodian-private for every locked/sealed report. A suppressed
cell additionally exposes no reason/category/cell token, and no repository-visible token may be
stable across runs or reveal/reuse custodian case IDs.

### 8.3 Release-candidate fingerprint

Create `schemas/evaluation_freeze_fingerprint.schema.json`. Eligibility requires every component:

- non-resettable `release_cycle_id` and the lane-conditional complete `candidate_cycle_identity`;
- candidate-source `git_object_format`, native commit/tree OIDs and separately named code-content SHA-
  256; locked values must equal the pinned checkpoint subject, while open/sealed-current values bind
  their actual candidate source;
- selected execution kind/contract ID/version/content SHA-256 and common response-contract hash;
- branch-specific candidate identity: deterministic-core callable/adapter plus deterministic request/
  result fragment and QueryPlan schema hashes, or end-to-end HCX model/deployment/release/revision/
  capability plus prompt-manifest hash;
- exact static candidate-isolation-profile ID/version/content SHA-256 and resolved-attestation policy;
- complete schema-valid `candidate_build_resource_manifest` plus its externally recomputed
  `candidate_build_resource_manifest_sha256`; duplicated code/config/schema/artifact/dependency/image/
  resource fields must equal that manifest byte-for-byte;
- complete schema-valid `evaluation_control_plane_resource_manifest` plus its external SHA-256; its
  Git/image/artifact/store-reader identities are the current deployment-pinned Phase-4 controller and
  are distinct from the candidate source/build identities;
- for non-open lanes, only the exact fixed-length random `disjointness_receipt_public_handle`; the
  HMAC-protected same-CAS private history source binds that handle to the complete content-addressed
  `reference_executor_disjointness_receipt` descriptor/hash whose suite-wide reference-executor/scorer
  and exact candidate-build closure comparisons are both recomputed before claim. Open fingerprints
  forbid the handle and every fingerprint forbids the private descriptor/hash/length/record ID;
- for sealed candidate-cycle ordinal 1 only, the complete schema-valid
  `remediation_build_subject`, its external `corrected_candidate_build_subject_sha256`, and the exact
  `conditional_child_public_build_basis` subobject copied both from that subject and the privately
  verified conditional-child base; ordinal 0 and every locked/open fingerprint forbid these fields;
- config-manifest hash;
- schema-manifest hash;
- source-manifest hash;
- built-artifact manifest/logical hash;
- dependency-lock hash;
- container-image digest;
- deployment-pinned evaluation-scorer-resource-manifest and scoring-rule-manifest IDs/versions/
  descriptors/complete hashes;
- branch-specific deny-by-default egress/logging identity; only end-to-end carries API contract,
  origin/TLS/transport, provider-retention, and provider identity fields;
- timeout durations and durable clock service/version/instance/epoch identity (no future ticks);
- both non-secret storage-reservation formula versions and the
  `evaluation_storage_reservation_commitment` with the exact HMAC metadata defined in Section 8.5;
  the fingerprint forbids any of the five complete reservation objects, their IDs/SHAs, actual staged/reserved/used/
  remaining record counts or bytes, descriptor-
  manifest SHA, and store metadata;
- evaluation-suite commitment;
- `history_registry_id`, `history_genesis_attestation_sha256`, and
  `eligibility_history_head_sha256`; and
- governance-policy version; and
- disposition-policy ID/version/commitment and HMAC metadata.

The fingerprint schema is a closed `oneOf`. `deterministic_core` requires the local callable/input/
output/adapter/no-network identities and forbids prompt, HCX, API method/path/query, origin/TLS,
provider, cache, and retention fields. `end_to_end_api` requires every existing HCX/prompt/API/
transport/no-store/provider identity and forbids the precommitted-plan/callable fields. Common source,
artifact, dependency, image, scorer, clock, storage, history, suite, and disposition bindings remain
required in both branches.
Its sealed ordinal-1 remediation branch additionally forbids the full private child base or its SHA,
human approval/scope record/receipt/hash/head, stable principal, owner authorization, private trigger
evidence, and change-evidence bytes. Indirect equality through a suite commitment, a digest-only
assertion, or omission of the complete public build basis is invalid.

The fingerprint object does not contain its own digest. `freeze_fingerprint_sha256` is the
Canonical JSON v1 SHA-256 of the complete schema-valid object and is the value bound by lifecycle,
run-attestation, and report objects.

Provider aliases alone are not immutable model identity. The candidate is sealed-eligible only when
a stable provider revision/deployment identity or an official provider attestation makes drift
detectable for the evaluation window. If neither exists, the alias plus returned capability
metadata may support open/locked diagnostics, but sealed eligibility stops rather than treating an
undetectable floating alias as frozen.

Create `schemas/evaluation_runtime_attestation.schema.json`. Before the run binding and immediately
before every dispatch commit, a trusted deployment/local-invocation/egress controller—not a caller-
supplied runner mapping—emits one schema-valid, domain-separated attestation. Its common closed fields
are attestation version, opaque runtime-lease ID, nullable `scoring_lease_id`, selected execution kind/
contract ID/version/content SHA-256, common response-contract SHA-256, static candidate-isolation-
profile ID/version/content SHA-256, `candidate_build_resource_manifest_sha256`, the complete current
`evaluation_control_plane_resource_manifest_sha256`, the lane-conditional
complete `candidate_cycle_identity`, positive observation sequence, observed-at/valid-until,
`freeze_fingerprint_sha256`, exact observed candidate-source/build identities and separately exact
current control-plane Git/code/config/schema/artifact/dependency-lock/image identities, all bound
timeout values, monotonic-clock source/version/instance/epoch and
applicable persisted start/deadline ticks, scorer/rule and branch egress/logging identities, resolved-
candidate-isolation-state projection, attestor role/key ID, branch-conditional
`irreversible_action_authority_binding`, and HMAC metadata/value. All observation kinds except the two
scoring kinds forbid the binding. `scoring_start` requires action `scoring_start` with decision allowed.
Normal/objective-error/finalize-conflict `scoring_finalized` requires action `outcome_finalize`; a
start-conflict `scoring_finalized` instead carries action `scoring_start`, decision conflict, null lease/
ledger and no earlier scoring-start observation.

The schema is a closed execution-kind `oneOf`. `deterministic_core` permits only `run_start`,
`at_local_invoke`, `pre_truth_commit`, `scoring_start`, and `scoring_finalized`; it requires the exact
callable/adapter, deterministic request/result fragment and QueryPlan schema hashes, local process/
IPC identity, no-network policy, and the attested resolved mount/environment-name/secret-purpose/UID/
security-context/namespace/IPC sets. `at_local_invoke` additionally binds the private case-attempt and
head-independent prepared-dispatch-subject commitments, case/candidate invocation IDs, exact request/
plan input descriptor/hash, and local process instance. It is the pre-invocation gate and therefore
forbids a completed dispatch commitment or invocation result. The content-free invocation result is
recorded only by the later candidate-attempt seal. That branch forbids prompt, HCX/provider,
HTTP/API/origin/TLS/transport, provider-retention/cache, network-credential, and provider-payload
fields.

`end_to_end_api` permits `run_start`, `at_egress`, `provider_invocation`, `pre_truth_commit`,
`scoring_start`, and `scoring_finalized`; it requires the exact prompt, HCX provider/model/deployment/
revision/capability, API/origin/TLS/transport, logging/cache/provider-retention, egress-proxy, and
registered HCX-credential-purpose fields and forbids callable/plan/local-invocation fields. A
pre-send `at_egress` observation follows the same acyclic rule as `at_local_invoke`: it binds the
prepared-dispatch subject/input/transport ID and resolved isolation state but forbids the future
dispatch-receipt commitment, provider result, or response. A
`provider_invocation` additionally binds the private case-attempt/dispatch commitments, invocation
purpose (`planner` or `wording`), per-attempt provider sequence, exact destination/model/deployment/
revision, content-free transport result, and provider request/response payload commitments; it never
exposes the hidden question or response. Each private payload commitment has exactly byte length and
lowercase SHA-256 over the exact raw provider-protocol bytes; the response pair is null only when no
response bytes existed. The trusted egress controller computes them from the actual transport bytes
before signing the outer runtime-observation HMAC. Complete provider observations, their hashes, and
these inner digests remain custodian-private; public history/reports carry only aggregate secret-
backed candidate-set/runtime bindings. `scoring_lease_id` is null before scoring. It is required/equal
in the two scoring observations for complete, objective-error and finalize-conflict branches; the
start-conflict branch has no start observation and requires its sole authenticated `scoring_finalized`
observation to carry a null lease. The controller key is separate from the general custodian/history keys.
Only the end-to-end branch applies the rule that a provider alias without an observable immutable
revision cannot produce a sealed runtime attestation.
`runtime_observation_sha256` is SHA-256 over Canonical JSON v1 bytes of the complete schema-valid
attestation including `attestation.value`; it is not stored inside the attestation it hashes. Every
run/dispatch/candidate-set/truth-commit runtime-observation hash means this complete digest, never an
unsigned projection or the HMAC value alone.

The run binding records the initial `run_start` attestation hash and lease. The trusted controller
holds that immutable runtime lease continuously from `run_start` through every local invocation or
actual provider call, response terminal seal, the `pre_truth_commit` observation, and the truth-
release-commit CAS. It prevents image/config/isolation remount, process restart, credential/mount/IPC
injection, deployment/provider revision substitution, or lease discontinuity rather than only
sampling equal identities at the endpoints. Each case-dispatch receipt binds the same lease and a
fresh branch-matching observation: `at_local_invoke` for deterministic core or `at_egress` for end-to-
end. Only end-to-end has complete `provider_invocation` receipts under that lease; deterministic core
requires an empty provider-observation set and mechanically denied candidate network egress.
After all case seals and before `candidate_attempt_set_sealed`, the controller issues one
`pre_truth_commit` attestation;
the candidate-attempt set plus truth-release commit reproduce the complete ordered observation-hash
list. Validation receives the
actual attestation objects, checks every observed component against the fingerprint, checks lease and
sequence continuity, and rejects drift between cases or between the last dispatch and truth commit.
Lease loss, restart, an unverifiable interval, or A->B->A drift during response generation burns the
slot before truth access; later equal observations cannot heal a discontinuity.
After truth-session redemption, the controller first runs the fresh typed `scoring_start` authority
guard. An allowed branch atomically persists the `scoring_start` runtime observation with its complete
authority binding and acquires one externally enforced immutable `scoring_lease_id` before the scorer
can read the session. It later persists `scoring_finalized` with the fresh `outcome_finalize` binding
inside the atomic outcome-store CAS. Those observations bind the truth-session/work-ledger identities
and actual scorer/rule artifacts. Every work-ledger
entry and the final receipt bind that original lease. A complete branch requires the controller to
prevent remount/drift continuously through the atomic outcome-store CAS. A recovery worker may attach
only to the same durable lease and identical observation state. Lease loss, restart without
continuity, or mid-scoring A->B->A drift may enter the all-invocation evaluation-error branch only
through the trusted controller's authenticated final failure observation defined below. A missing or
unauthenticatable final observation blocks/stops; it never fabricates either completion branch. If
`scoring_start` conflicts, the finalization slot instead records stage `start`, the conflict binding,
null scoring-start observation/lease/ledger and no scorer read. If `outcome_finalize` conflicts after an
allowed start, it records stage `finalize`, the conflict binding and a sealed unusable ledger prefix.
The
outcome set and report carry the resulting extended sequence.

The scoring work ledger is a private append-only hash chain of one-record-per-invocation objects, not
an opaque head string or one monolithic array. Every entry
has exactly ledger version, suite/run, `truth_session_record_sha256`, `scoring_lease_id`, scorer/rule
identities, contiguous case ordinal, private case fingerprint, final candidate-attempt commitment,
the complete derived case-outcome object with evidence/claim-verification references, completion tick,
`previous_scoring_entry_sha256` (null only at ordinal zero), and `scoring_entry_sha256`. The entry hash
is SHA-256 over Canonical JSON v1 bytes with only its own hash removed. A complete scoring branch has
exactly `eligible` entries in case-ordinal order.

Each final case outcome is also one immutable `outcome_entry` control record, never an element copied
into a giant outcome/report object. It has exactly projection version, suite/run IDs, case ordinal,
private case fingerprint, final case-attempt/binding/candidate commitments, terminal outcome/reason
codes, scorer/rule versions, exact score components, and bounded claim/evidence-verification
references. Its descriptor length/hash covers the complete Canonical JSON v1 record. The original
`outcome_index` has exactly projection version, suite/run IDs, eligible count, contiguous ordered
entries of `{case_ordinal, record_id, byte_length, sha256}`, and no outcome values. A corrected index
has the same shape plus original-index SHA-256, correction-derivation-record SHA-256, and target
revision. Every entry descriptor resolves exactly once. Only the complete branch requires index order,
entry ordinal and scoring-ledger ordinal to agree one-to-one. Objective-error and authority-error
branches verify only their authenticated ledger prefix separately and deterministically synthesize a
full eligible-count uniform error index; no score or verdict is copied from that prefix. Index order and
eligible coverage remain exact in every branch. Each outcome-entry schema maximum is generated and proven
to fit the per-record cap before claim.

`outcome_descriptor_list_projection` has exactly `projection_version: "1"`, suite ID/version,
`run_attempt_id`, eligible count, and the same ordered descriptor tuples; it has no digest field.
`outcome_descriptor_list_sha256` is SHA-256 of its Canonical JSON v1 bytes. The analogous
`scoring_descriptor_list_projection` substitutes each scoring entry's ordinal/record ID/byte length/
SHA-256 and exact entry count, and its SHA-256 is computed identically. No bare array, concatenated
descriptor bytes, Merkle variant, or record-order-dependent alternative is accepted.

The canonical `outcome_set_content_projection` `$def` has exactly `projection_version: "1"`, suite
ID/version, `run_attempt_id`, eligible count, scoring-completion state, `outcome_index_sha256`, the
ordered descriptor-list SHA-256, and a closed `counters` object with exactly `attempted`, `scored`,
`passed`, `failed`, `runtime_error`, `timeout`, `malformed_output`, `evaluation_error`,
`evidence_verification_failures`, and `claim_verification_failures`. It contains no outcome array or
digest field. `outcome_set_content_sha256` is SHA-256 over Canonical JSON v1 bytes of that exact
object. Validation streams every indexed outcome record, recomputes the descriptor list/index/content
hashes and counters, and rejects array wrapping, concatenated bytes, omitted counters, alternate
members, unindexed outcomes, or a monolithic copied outcome array.

The `scoring_finalized` runtime observation is the independently authenticated finalization receipt.
It binds the original `scoring_lease_id`, scoring-work-ledger head and entry count,
`outcome_set_content_sha256`, scoring completion state, authoritative observed/deadline ticks,
`lease_continuity`, the complete applicable authority binding, and objective failure code when applicable.
A complete branch requires
`lease_continuity: true`, entry count equal to eligible, and exact reconstruction of every outcome/
counter. An `evaluation_error` branch requires `lease_continuity: false` or deadline expiry plus the
first authenticated failure tick and one closed code (`scoring_lease_lost`, `scoring_runtime_drift`,
`scoring_restart_discontinuity`, or `scoring_deadline_expired`); it may bind a strict ledger prefix.
The third strict `authority_restriction` branch requires code `AUTHORITY_RESTRICTION`, stage `start` or
`finalize`, first authenticated conflict tick and a byte-identical conflict binding whose action kind
is respectively `scoring_start` or `outcome_finalize`. Stage `start` requires null scoring-start
observation, lease and ledger and proves no scorer/session read occurred; stage `finalize` requires the
prior allowed scoring-start observation/lease and seals any strict ledger prefix unusable. It requires
neither lease discontinuity nor deadline expiry.
Its public outcome is the fixed all-invocation failure set and never exposes/selects that prefix.
Validation is branch-specific: `complete` derives the outcome array/content hash from all ledger
entries; `evaluation_error` verifies only the supplied prefix chain/head/count, independently derives
the uniform eligible-count error array/counters from the authenticated failure proof, and checks that
separate content hash in the final receipt. The authority branch independently derives the uniform
eligible-count `evaluation_error/AUTHORITY_RESTRICTION` array/counters and its content hash. It rejects a fabricated/omitted prefix, publication of a
prefix-derived score, or a receipt whose branch-specific content does not match.
Phase 4 performs the secret HMAC and real deployment/provider checks; copied equality without these
independent observations is not freeze evidence.

### 8.4 Lifecycle events and cross-object validator

Create `schemas/evaluation_lifecycle_event.schema.json` and a deterministic thin typed facade in
`tools/evaluation_control.py` with these public interfaces:

```python
load_unique_json_bytes(data: bytes) -> ParsedJsonValue
load_private_control_bundle_bytes(data: bytes) -> EvaluationPrivateControlBundleModel
compute_private_control_reservation(
    policy: EvaluationGovernancePolicyModel,
    suite_preclaim_basis: SuitePreclaimBasisModel,
) -> PrivateControlReservationPlanModel
compute_private_history_reservation(
    policy: EvaluationGovernancePolicyModel,
    suite_preclaim_basis: SuitePreclaimBasisModel,
    bootstrap_descriptor_manifest: BootstrapDescriptorManifestModel,
) -> PrivateHistoryReservationPlanModel
canonical_json_sha256(value: CanonicalJsonValue) -> Sha256Hex
canonical_domain_errors(value: UntrustedCanonicalInput) -> tuple[EvaluationDiagnostic, ...]
freeze_canonical_json(value: ParsedJsonValue) -> CanonicalJsonValue
build_private_case_fingerprints(
    case: GoldenCaseModel,
    evidence_package: EvidencePackageModel,
) -> PrivateCaseFingerprintsModel
reference_truth_derivation_errors(
    policy: EvaluationGovernancePolicyModel,
    case: GoldenCaseModel,
    evidence_package: EvidencePackageModel,
    case_set_entry: CaseSetEntryProjectionModel,
    private_case_fingerprints: PrivateCaseFingerprintsModel,
    executor_manifest: ReferenceExecutorManifestModel,
    execution_request: ReferenceTruthExecutionRequestModel,
    derivation_receipt: ReferenceTruthDerivationReceiptModel,
    artifact_reader: ReferenceTruthArtifactReader,
    source_reader: ReferenceTruthSourceReader,
    executor: ReferenceTruthExecutor,
) -> tuple[EvaluationDiagnostic, ...]
reference_executor_disjointness_errors(
    policy: EvaluationGovernancePolicyModel,
    executor_manifest: ReferenceExecutorManifestModel,
    scorer_manifest: EvaluationScorerResourceManifestModel,
    candidate_build_manifest: CandidateBuildResourceManifestModel,
    receipt: ReferenceExecutorDisjointnessReceiptModel,
) -> tuple[EvaluationDiagnostic, ...]
reference_truth_suite_errors(
    policy: EvaluationGovernancePolicyModel,
    suite_manifest: EvaluationSuiteManifestModel,
    case_set_index: CaseSetIndexProjectionModel,
    witness: ReferenceTruthSuiteWitnessModel,
    witness_reader: ReferenceTruthSuiteWitnessReader,
    human_review_approval: HumanReviewApprovalModel,
    artifact_reader: ReferenceTruthArtifactReader,
    source_reader: ReferenceTruthSourceReader,
    executor: ReferenceTruthExecutor,
) -> tuple[EvaluationDiagnostic, ...]
release_action_state_transition_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    observed_witness: ReleaseActionCurrentWitnessModel | None,
    candidate_state_bytes: bytes,
    candidate_attestation_bytes: bytes,
    completion_basis: ReleaseActionCompletionBasisModel | None,
    branch_result: ReleaseActionBranchResultModel | None,
    reservation_reader: ReleaseActionStoreReservationReader,
    branch_result_reader: ReleaseActionBranchResultReader,
    current_resource_reader: ReleaseActionCurrentResourceReader,
) -> tuple[EvaluationDiagnostic, ...]
private_control_pointer_transition_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    expected_pointer: PrivateControlCurrentPointerModel | None,
    expected_attestation_bytes: bytes | None,
    candidate_pointer: PrivateControlCurrentPointerModel,
    candidate_attestation_bytes: bytes,
    candidate_snapshot_bytes: bytes,
    snapshot_reader: PrivateControlSnapshotReader,
    current_resource_reader: PrivateControlCurrentResourceReader,
    candidate_ingress_current_witness: CandidateIngressCurrentWitnessModel | None,
    candidate_ingress_current_resource_reader: CandidateIngressCurrentResourceReader | None,
    irreversible_action_subject: NonOpenIrreversibleActionSubjectModel | None,
    irreversible_action_authority_state: NonOpenIrreversibleActionAuthorityStateModel | None,
    irreversible_action_authority_guard: NonOpenIrreversibleActionAuthorityGuardModel | None,
    irreversible_action_authority_witness: ActivationAuthorityWitnessModel | None,
    irreversible_action_transition_reader: ActivationAuthorityTransitionReader | None,
    irreversible_action_official_archive_reader: OfficialInstructionArchiveReader | None,
) -> tuple[EvaluationDiagnostic, ...]
candidate_ingress_transition_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    observed_witness: CandidateIngressCurrentWitnessModel | None,
    candidate_state_bytes: bytes,
    candidate_attestation_bytes: bytes,
    current_resource_reader: CandidateIngressCurrentResourceReader,
    private_control_pointer: PrivateControlCurrentPointerModel | None,
    private_control_current_resource_reader: PrivateControlCurrentResourceReader | None,
) -> tuple[EvaluationDiagnostic, ...]
evaluation_scope_deadline_transition_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    offset_profile: EvaluationScopeScheduleOffsetProfileModel,
    schedule: EvaluationScopeTerminalScheduleProjectionModel,
    schedule_ref: EvaluationScopeTerminalScheduleRefModel,
    transition: EvaluationScopeDeadlineTransitionModel,
    postfreeze_fence: PostfreezeIncompleteScopeFenceModel | None,
    stage_witness: EvaluationScopeDeadlineStageWitnessModel,
    stage_reader: EvaluationScopeDeadlineStageReader,
    human_governance_witness: HumanGovernanceWitnessModel,
    human_governance_record_reader: HumanGovernanceRecordReader,
    trusted_clock_witness: TrustedClockCurrentWitnessModel,
    trusted_clock_current_resource_reader: TrustedClockCurrentResourceReader,
    trusted_clock_transition_reader: TrustedClockTransitionReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
    history_transition_witness: HistoryTransitionWitnessModel,
    history_record_reader: HistoryRecordReader,
) -> tuple[EvaluationDiagnostic, ...]
human_governance_policy_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    genesis: HumanGovernanceGenesisModel,
    prior_state: HumanGovernanceStateModel,
    witness: HumanGovernanceWitnessModel,
    record_reader: HumanGovernanceRecordReader,
    authenticated_session_reader: AuthenticatedSessionReader | None,
    review_access_session: AuthenticatedHumanReviewSessionModel | None,
    review_session_state: HumanReviewSessionStateModel | None,
    review_authority_interval_receipt: HumanReviewAuthorityIntervalReceiptModel | None,
    principal_identity_attestation: HumanStableIdentityAttestationModel,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
    irreversible_action_subject: NonOpenIrreversibleActionSubjectModel | None,
    irreversible_action_authority_state: NonOpenIrreversibleActionAuthorityStateModel | None,
    irreversible_action_authority_guard: NonOpenIrreversibleActionAuthorityGuardModel | None,
    irreversible_action_authority_witness: ActivationAuthorityWitnessModel | None,
    activation_authority_transition_reader: ActivationAuthorityTransitionReader | None,
    official_instruction_archive_reader: OfficialInstructionArchiveReader | None,
) -> tuple[EvaluationDiagnostic, ...]
non_open_irreversible_action_authority_guard_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    action_subject: NonOpenIrreversibleActionSubjectModel,
    authority_state: NonOpenIrreversibleActionAuthorityStateModel,
    authority_guard: NonOpenIrreversibleActionAuthorityGuardModel,
    official_instruction_snapshot: OfficialInstructionSnapshotModel,
    semantic_reviewer_identity_attestation: HumanStableIdentityAttestationModel,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    activation_authority_witness: ActivationAuthorityWitnessModel,
    activation_authority_transition_reader: ActivationAuthorityTransitionReader,
    official_instruction_archive_reader: OfficialInstructionArchiveReader,
) -> tuple[EvaluationDiagnostic, ...]
owner_remediation_blind_signer_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    public_request: OwnerRemediationPublicDecisionRequestModel,
    owner_approval: OwnerRemediationPublicApprovalAttestationModel,
    private_join: OwnerRemediationPrivateJoinModel,
    signer_result: OwnerRemediationBlindSignerResultModel,
    signer_consumption_receipt: OwnerRemediationSignerConsumptionReceiptModel,
    signer_state_witness: OwnerRemediationSignerStateWitnessModel,
    signer_store_reader: OwnerRemediationSignerStoreReader,
    decision_input_reader: OwnerRemediationDecisionInputReader,
    owner_identity_attestation: HumanStableIdentityAttestationModel,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    trusted_clock_current_witness: TrustedClockCurrentWitnessModel,
    trusted_clock_current_resource_reader: TrustedClockCurrentResourceReader,
    trusted_clock_transition_reader: TrustedClockTransitionReader,
) -> tuple[EvaluationDiagnostic, ...]
owner_remediation_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    history_genesis_anchor: HistoryGenesisAnchorModel,
    prior_registry_state: HistoryRegistryStateModel,
    history_transition_witness: HistoryTransitionWitnessModel,
    history_record_reader: HistoryRecordReader,
    human_governance_witness: HumanGovernanceWitnessModel,
    human_governance_record_reader: HumanGovernanceRecordReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
    owner_identity_attestation: HumanStableIdentityAttestationModel,
    curator_identity_attestation: HumanStableIdentityAttestationModel,
    owner_curator_non_alias_proof: OwnerCuratorNonAliasProofModel,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    authorization: OwnerRemediationAuthorizationModel,
    public_decision_request: OwnerRemediationPublicDecisionRequestModel,
    owner_approval: OwnerRemediationPublicApprovalAttestationModel,
    private_join: OwnerRemediationPrivateJoinModel,
    signer_result: OwnerRemediationBlindSignerResultModel,
    signer_consumption_receipt: OwnerRemediationSignerConsumptionReceiptModel,
    signer_state_witness: OwnerRemediationSignerStateWitnessModel,
    signer_store_reader: OwnerRemediationSignerStoreReader,
    decision_input_reader: OwnerRemediationDecisionInputReader,
    signer_trusted_clock_witness: TrustedClockCurrentWitnessModel,
    trusted_clock_current_resource_reader: TrustedClockCurrentResourceReader,
    trusted_clock_transition_reader: TrustedClockTransitionReader,
    activation_authority_witness: ActivationAuthorityWitnessModel | None,
    activation_authority_transition_reader: ActivationAuthorityTransitionReader | None,
    official_instruction_archive_reader: OfficialInstructionArchiveReader | None,
    private_child_base: ConditionalChildBaseModel,
    build_subject: CorrectedCandidateBuildSubjectModel | None,
    change_evidence: CorrectedCandidateChangeEvidenceModel | None,
) -> tuple[EvaluationDiagnostic, ...]
child_fingerprint_extension_errors(
    policy: EvaluationGovernancePolicyModel,
    private_child_base: ConditionalChildBaseModel,
    build_subject: CorrectedCandidateBuildSubjectModel,
    change_evidence: CorrectedCandidateChangeEvidenceModel,
    child_fingerprint: EvaluationFreezeFingerprintModel,
) -> tuple[EvaluationDiagnostic, ...]
build_history_projection(history_append: PrivateHistoryAppendModel) -> HistoryProjectionModel
suite_history_policy_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    history_genesis_anchor: HistoryGenesisAnchorModel,
    prior_registry_state: HistoryRegistryStateModel,
    predecessor_attestation: SuiteHistoryAttestationModel,
    private_history_append: PrivateHistoryAppendModel,
    candidate_attestation: SuiteHistoryAttestationModel,
    checkpoint_candidate_provenance_subject: CheckpointCandidateProvenanceSubjectModel | None,
    checkpoint_candidate_pin_receipt: CheckpointCandidatePinReceiptModel | None,
    checkpoint_candidate_pre_execution_order_witness: CheckpointCandidatePreExecutionOrderWitnessModel | None,
    checkpoint_candidate_artifact_reader: CheckpointCandidateArtifactReader | None,
    checkpoint_candidate_git_object_reader: CheckpointCandidateGitObjectReader | None,
    reference_truth_suite_witness: ReferenceTruthSuiteWitnessModel | None,
    reference_truth_suite_witness_reader: ReferenceTruthSuiteWitnessReader | None,
    reference_truth_artifact_reader: ReferenceTruthArtifactReader | None,
    reference_truth_source_reader: ReferenceTruthSourceReader | None,
    reference_truth_executor: ReferenceTruthExecutor | None,
    history_record_reader: HistoryRecordReader,
    human_governance_witness: HumanGovernanceWitnessModel,
    human_governance_record_reader: HumanGovernanceRecordReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
    irreversible_action_subject: NonOpenIrreversibleActionSubjectModel | None,
    irreversible_action_authority_state: NonOpenIrreversibleActionAuthorityStateModel | None,
    irreversible_action_authority_guard: NonOpenIrreversibleActionAuthorityGuardModel | None,
    irreversible_action_authority_witness: ActivationAuthorityWitnessModel | None,
    irreversible_action_transition_reader: ActivationAuthorityTransitionReader | None,
    irreversible_action_official_archive_reader: OfficialInstructionArchiveReader | None,
) -> tuple[EvaluationDiagnostic, ...]
suite_history_archive_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    history_genesis_anchor: HistoryGenesisAnchorModel,
    archive_manifest_reader: ArchiveManifestReader,
    public_attestation_reader: PublicAttestationReader,
    history_record_reader: HistoryRecordReader,
    human_governance_witness: HumanGovernanceWitnessModel,
    expected_final_registry_state: HistoryRegistryStateModel,
    human_governance_record_reader: HumanGovernanceRecordReader,
    expected_final_human_governance_state: HumanGovernanceStateModel,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
) -> tuple[EvaluationDiagnostic, ...]
build_disclosure_payload(
    policy: EvaluationGovernancePolicyModel,
    private_report: PrivateEvaluationReportModel,
) -> RepositoryDisclosureReportModel
disclosure_policy_errors(
    policy: EvaluationGovernancePolicyModel,
    private_report: PrivateEvaluationReportModel | None,
    public_report: EvaluationReportModel,
    expected_private_report_commitment_value: HmacHex | None,
    open_evaluation_manifest: OpenEvaluationManifestModel | None,
    open_evaluation_record_reader: OpenEvaluationRecordReader | None,
) -> tuple[EvaluationDiagnostic, ...]
evaluation_control_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel | None,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader | None,
    disposition_policy: EvaluationDispositionPolicyModel | None,
    history_genesis_anchor: HistoryGenesisAnchorModel | None,
    suite_manifest: EvaluationSuiteManifestModel,
    checkpoint_candidate_provenance_subject: CheckpointCandidateProvenanceSubjectModel | None,
    checkpoint_candidate_pin_receipt: CheckpointCandidatePinReceiptModel | None,
    checkpoint_candidate_pre_execution_order_witness: CheckpointCandidatePreExecutionOrderWitnessModel | None,
    checkpoint_candidate_artifact_reader: CheckpointCandidateArtifactReader | None,
    checkpoint_candidate_git_object_reader: CheckpointCandidateGitObjectReader | None,
    reference_truth_suite_witness: ReferenceTruthSuiteWitnessModel | None,
    reference_truth_suite_witness_reader: ReferenceTruthSuiteWitnessReader | None,
    reference_truth_artifact_reader: ReferenceTruthArtifactReader | None,
    reference_truth_source_reader: ReferenceTruthSourceReader | None,
    reference_truth_executor: ReferenceTruthExecutor | None,
    history_registry_state: HistoryRegistryStateModel | None,
    history_transition_witness: HistoryTransitionWitnessModel | None,
    history_record_reader: HistoryRecordReader | None,
    human_governance_witness: HumanGovernanceWitnessModel | None,
    human_governance_record_reader: HumanGovernanceRecordReader | None,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel | None,
    identity_authority_reader: IdentityAuthorityReader | None,
    current_registry_witness_set: CurrentRegistryWitnessSetModel | None,
    current_registry_resource_reader: CurrentRegistryResourceReader | None,
    freeze_fingerprint: EvaluationFreezeFingerprintModel | None,
    private_control_current_pointer: PrivateControlCurrentPointerModel | None,
    private_control_current_attestation_bytes: bytes | None,
    private_control_bundle_bytes: bytes | None,
    private_control_snapshot_reader: PrivateControlSnapshotReader | None,
    private_control_current_resource_reader: PrivateControlCurrentResourceReader | None,
    private_control_record_reader: PrivateControlRecordReader | None,
    private_binary_blob_reader: PrivateBinaryBlobReader | None,
    candidate_ingress_current_witness: CandidateIngressCurrentWitnessModel | None,
    candidate_ingress_current_resource_reader: CandidateIngressCurrentResourceReader | None,
    irreversible_action_subject: NonOpenIrreversibleActionSubjectModel | None,
    irreversible_action_authority_state: NonOpenIrreversibleActionAuthorityStateModel | None,
    irreversible_action_authority_guard: NonOpenIrreversibleActionAuthorityGuardModel | None,
    irreversible_action_authority_witness: ActivationAuthorityWitnessModel | None,
    irreversible_action_transition_reader: ActivationAuthorityTransitionReader | None,
    irreversible_action_official_archive_reader: OfficialInstructionArchiveReader | None,
    open_evaluation_manifest_bytes: bytes | None,
    open_evaluation_record_reader: OpenEvaluationRecordReader | None,
    open_public_report_bytes: bytes | None,
    expected_private_report_commitment_value: HmacHex | None,
) -> tuple[EvaluationDiagnostic, ...]
published_report_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    disposition_policy: EvaluationDispositionPolicyModel,
    history_genesis_anchor: HistoryGenesisAnchorModel,
    suite_manifest: EvaluationSuiteManifestModel,
    checkpoint_candidate_provenance_subject: CheckpointCandidateProvenanceSubjectModel | None,
    checkpoint_candidate_pin_receipt: CheckpointCandidatePinReceiptModel | None,
    checkpoint_candidate_pre_execution_order_witness: CheckpointCandidatePreExecutionOrderWitnessModel | None,
    checkpoint_candidate_artifact_reader: CheckpointCandidateArtifactReader | None,
    checkpoint_candidate_git_object_reader: CheckpointCandidateGitObjectReader | None,
    reference_truth_suite_witness: ReferenceTruthSuiteWitnessModel,
    reference_truth_suite_witness_reader: ReferenceTruthSuiteWitnessReader,
    reference_truth_artifact_reader: ReferenceTruthArtifactReader,
    reference_truth_source_reader: ReferenceTruthSourceReader,
    reference_truth_executor: ReferenceTruthExecutor,
    history_registry_state: HistoryRegistryStateModel,
    history_transition_witness: HistoryTransitionWitnessModel,
    history_record_reader: HistoryRecordReader,
    human_governance_witness: HumanGovernanceWitnessModel,
    human_governance_record_reader: HumanGovernanceRecordReader,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
    release_authority_witness: ActivationAuthorityWitnessModel,
    activation_authority_transition_reader: ActivationAuthorityTransitionReader,
    official_instruction_archive_reader: OfficialInstructionArchiveReader,
    freeze_fingerprint: EvaluationFreezeFingerprintModel,
    private_control_current_pointer: PrivateControlCurrentPointerModel,
    private_control_current_attestation_bytes: bytes,
    private_control_bundle_bytes: bytes,
    private_control_snapshot_reader: PrivateControlSnapshotReader,
    private_control_current_resource_reader: PrivateControlCurrentResourceReader,
    private_control_record_reader: PrivateControlRecordReader,
    private_binary_blob_reader: PrivateBinaryBlobReader,
    candidate_ingress_current_witness: CandidateIngressCurrentWitnessModel,
    candidate_ingress_current_resource_reader: CandidateIngressCurrentResourceReader,
    expected_private_report_commitment_value: HmacHex,
) -> tuple[EvaluationDiagnostic, ...]
release_readiness_errors(
    policy: EvaluationGovernancePolicyModel,
    deployment_trust_anchor_manifest: DeploymentTrustAnchorManifestModel,
    deployment_trust_anchor_reader: DeploymentTrustAnchorReader,
    disposition_policy: EvaluationDispositionPolicyModel,
    history_genesis_anchor: HistoryGenesisAnchorModel,
    history_registry_state: HistoryRegistryStateModel,
    history_transition_witness: HistoryTransitionWitnessModel,
    history_record_reader: HistoryRecordReader,
    human_governance_witness: HumanGovernanceWitnessModel,
    human_governance_record_reader: HumanGovernanceRecordReader,
    identity_authority_witness: IdentityAuthorityCurrentWitnessModel,
    identity_authority_reader: IdentityAuthorityReader,
    current_registry_witness_set: CurrentRegistryWitnessSetModel,
    current_registry_resource_reader: CurrentRegistryResourceReader,
    release_authority_witness: ActivationAuthorityWitnessModel,
    activation_authority_transition_reader: ActivationAuthorityTransitionReader,
    official_instruction_archive_reader: OfficialInstructionArchiveReader,
    checkpoint_candidate_pre_execution_order_witnesses: tuple[
        CheckpointCandidatePreExecutionOrderWitnessModel,
        CheckpointCandidatePreExecutionOrderWitnessModel,
    ],
    checkpoint_candidate_final_repository_order_witnesses: tuple[
        CheckpointCandidateFinalRepositoryOrderWitnessModel,
        CheckpointCandidateFinalRepositoryOrderWitnessModel,
    ],
    checkpoint_candidate_artifact_reader: CheckpointCandidateArtifactReader,
    checkpoint_candidate_git_object_reader: CheckpointCandidateGitObjectReader,
    summary: OrganizerOpportunityDisclosureSummaryModel,
    artifact_reader: OrganizerOpportunityArtifactReader,
    cumulative_disclosure_archive_witness: CumulativeDisclosureArchiveWitnessModel,
    cumulative_disclosure_archive_reader: CumulativeDisclosureArchiveReader,
    report_validation_dossier: ReleaseReportValidationDossierModel,
    report_dependency_reader: ReleaseReportDependencyReader,
    verified_published_report_receipt_reader: VerifiedPublishedReportReceiptReader,
) -> tuple[EvaluationDiagnostic, ...]
execute_release_action(
    request: ReleaseActionValidationRequestModel,
    transaction: ReleaseActionTransaction,
) -> ReleaseActionExecutionResultModel
```

`tools/evaluation_models.py` defines every named model/type above, lowercase-hex constrained
`Sha256Hex`/`HmacHex`, strict `HmacMetadataModel`/`HmacReferenceModel`, `ParsedJsonValue`, immutable
`CanonicalJsonValue`, and reader `Protocol`s whose
methods accept one descriptor ID/hash and yield bounded byte chunks.
`PrivateControlCurrentPointerModel` carries the exact pinned resource/genesis/store/allocation,
suite/run, current snapshot sequence/SHA-256, snapshot-equal lifecycle-current-head SHA-256, CAS
generation, current-state-attestation SHA-256,
registered scheme, and opaque attestation key ID. `PrivateControlPointerAttestationModel` is the exact
strict signed projection/value wrapper above and is capped before parsing;
`PrivateControlSnapshotReader` resolves predecessor snapshots by complete hash;
`PrivateControlCurrentResourceReader` independently returns the real current pointer/attestation/current-
store receipt by pinned resource/genesis. `CandidateIngressCurrentStateModel`,
`CandidateIngressCurrentAttestationModel`, and `CandidateIngressCurrentWitnessModel` are strict frozen
counterparts of the closed ingress definitions; `CandidateIngressCurrentResourceReader` independently
returns their real current state/attestation/store receipt. Reader protocols never return parsed
dictionaries. `HumanGovernanceWitnessModel` carries the pinned registry/genesis/current
state plus bounded review-session start/terminal/interval, approval, conditional-child-base, complete
terminal-schedule, scope/completion/exposure transition descriptors/proofs. Its normal-transition
variant contains only the touched ordered descriptors and enforces the 32-record/33,554,432-byte
per-scope cap; its archive-audit variant contains the complete ordered transition/record/proof
descriptor inventory from genesis through the expected final head and instead enforces the distinct
competition-lifetime 64-scope/2,048-record/2,147,483,648-byte caps.
`HumanGovernanceRecordReader` resolves those private records under the applicable branch cap.
`AuthenticatedSessionReader` is a deployment-pinned `Protocol` whose sole
`read_current() -> AuthenticatedAccessSubjectContextModel` method takes no arguments, reads the live
OS-peer/mTLS/transport session owned by the gate, and returns strict canonical bounded bytes only; it
never accepts or echoes a caller role, identity, context or attestation. The manifest/reader verifier
checks its pinned service/image/config and accepted trust roots before any gate call.
`HumanReviewAccessGate.start_review()`, `.read_exact(descriptor)` and `.finish_review()` take no
caller role/current-state/authority arguments: the gate obtains `AuthenticatedHumanReviewSessionModel`
from that live session reader, runs the typed `review_access` guard, and commits the active human-
governance session row before the first read. Every read resolves that current active row; finish
returns only a typed completed interval receipt or private terminal tombstone. The
`OfficialInstructionArchiveReader` streams the complete bounded start-to-end successor range so a
temporarily effective then retracted prohibition cannot disappear. `HumanGovernanceRecordReader`
resolves the durable active/terminal row and interval receipt/tombstone, and every approval and
combined scope basis must bind the exact completed interval receipt descriptor/hash.
`EvaluationScopeDeadlineStageReader` is a deployment-owned `Protocol` facade over the already pinned
history/human/five-registry, private-control snapshot/record/blob, candidate-ingress, both allocation-
store, truth-capability/session, scoring/outcome/report and sink current-resource/read-record readers.
Its sole `read_current_stage(scope_batch_id) -> EvaluationScopeDeadlineStageWitnessModel` method takes
only the authenticated scope-batch key, returns strict canonical descriptor/current-attestation data,
and exposes one held fence over every generation touched by the selected branch. It is not a new trust
root: the deadline validator verifies every returned signed current object against the independently
loaded deployment manifest and byte-compares every referenced record through its existing bounded
reader.

`EvaluationScopeDeadlineTransaction` is constructed with the independently pinned
`DeploymentTrustAnchorReader`, `TrustedClockCurrentResourceReader`,
`TrustedClockTransitionReader`, `EvaluationScopeDeadlineStageReader`,
`CurrentRegistryResourceReader`, `HumanGovernanceRecordReader`, `HistoryRecordReader`, and the existing
branch readers composed by the stage reader. Its `recover_due(scope_batch_id)` method's only argument
is the authenticated scope-batch key. It independently obtains the clock and stage witness, recomputes
the earliest due ordinal/stage, builds and validates the strict deadline transition internally, holds
or rechecks the clock/stage/five-registry/allocation generations through the common CAS, and commits
only that deterministic branch. It accepts no caller witness, tick, stage, cause, old state or terminal
label. The exported `evaluation_scope_deadline_transition_errors` helper is pure validation evidence,
not an authorization result: it may be called by this transaction only after its supplied clock/stage
witnesses have been byte-compared to the independent reader returns and all manifest signatures/
lineages are verified. A caller invoking the helper with self-consistent bytes can never authorize a
write.
No due transition returns `None`; a completed/replayed transition returns the exact immutable
`EvaluationScopeDeadlineTransitionModel`. The sole exception is the explicit official-freeze stop
condition above, which first recovers/commits every required private
`postfreeze_incomplete_scope_fence`, then raises a typed stop diagnostic without any result/public
transition. Ambiguous transaction status is recovered from authoritative heads before retry and never
authorizes another branch.
`DeploymentTrustAnchorManifestModel`, `DeploymentTrustAnchorPinReceiptModel`,
`CheckpointCandidateProvenanceSubjectModel`, `CheckpointCandidatePinReceiptModel`,
`CheckpointCandidatePreExecutionOrderWitnessModel`,
`CheckpointCandidateFinalRepositoryOrderWitnessModel`,
`EvaluationControlPlanePublicRoleAttestationModel`, `EvaluationControlPlaneResourceManifestModel`,
`EvaluationScorerResourceManifestModel`, `ScoringRuleManifestModel`,
`ReferenceExecutorManifestModel`, `ReferenceTruthExecutionRequestModel`,
`ReferenceTruthExecutionResultModel`, `ReferenceTruthDerivationReceiptModel`,
`ReferenceExecutorDisjointnessReceiptModel`, `ReferenceTruthSuiteWitnessModel`,
`EvaluationScopeScheduleOffsetProfileModel`, `EvaluationScopeTerminalScheduleProjectionModel`,
`EvaluationScopeTerminalScheduleRefModel`, `EvaluationScopeDeadlineTransitionModel`,
`EvaluationScopeDeadlineStageWitnessModel`, `PostfreezeIncompleteScopeFenceModel`,
`RevokedPublicIdPlanModel`,
`HumanStableIdentityAttestationModel`, `OwnerCuratorNonAliasProofModel`,
`IdentityAuthorityCurrentAttestationProjectionModel`, `IdentityAuthorityCurrentAttestationModel`,
`IdentityAuthorityCurrentWitnessModel`,
`OwnerRemediationPrivateJoinCommitmentProjectionModel`,
`OwnerRemediationAuthorizationPreclaimBasisProjectionModel`,
`ConditionalChildBaseModel`, `ConditionalChildPublicBuildBasisModel`,
`CorrectedCandidateBuildSubjectModel`, `CorrectedCandidateChangeEvidenceModel`,
`OwnerRemediationAuthorizationModel`, `OwnerRemediationPublicDecisionRequestModel`,
`OwnerRemediationPublicApprovalAttestationModel`, `OwnerRemediationPrivateJoinModel`,
`OwnerRemediationBlindSignerResultModel`, `OwnerRemediationSignerConsumptionReceiptModel`,
`OwnerRemediationSignerStateModel`, `OwnerRemediationSignerCurrentAttestationModel`,
`OwnerRemediationSignerStateWitnessModel`,
`ActivationAuthorityWitnessModel`, `TrustedClockCurrentWitnessModel`,
`ActivationAuthorityReadAttestationModel`, `SubmissionFreezeBasisModel`,
`ActivationAuthorityTransitionManifestModel`, `OfficialInstructionSnapshotModel`,
`OfficialInstructionRecordModel`, `OfficialInstructionApplicabilityManifestModel`,
`OfficialInstructionSemanticReviewRecordModel`,
`NonOpenIrreversibleActionSubjectModel`, `NonOpenIrreversibleActionAuthorityStateModel`,
`NonOpenIrreversibleActionAuthorityGuardModel`, `IrreversibleActionAuthorityBindingModel`,
`AuthorityConflictPreclaimCloseModel`,
`RegistryCurrentPointerAttestationModel`,
`CurrentRegistryWitnessSetModel`, `ScopeAndSlotPrepareBasisProjectionModel`,
`AuthenticatedAccessSubjectContextModel`, `AuthenticatedHumanReviewSessionModel`,
`HumanReviewSessionStateModel`, `HumanReviewSessionProofBundleModel`,
`HumanReviewAuthorityIntervalReceiptModel`,
`ReviewAuthorityConflictTombstoneModel`,
`SlotPreparationSourceModel`, `SlotPreparationRegistryStateModel`,
`SlotPreparationRowModel`, `SlotPreparationReceiptModel`,
`SlotPreparationTransitionManifestModel`, `SlotPreparationRegistryWitnessModel`,
`AeadNonceRegistryWitnessModel`, `OrganizerOpportunityDisclosureSummaryModel`,
`CumulativeDisclosureArchiveManifestModel`, `CumulativeDisclosureArchiveWitnessModel`,
`ReleaseReportValidationEntryModel`, `ReleaseReportValidationEntryShardModel`,
`ReleaseReportValidationEntryManifestModel`, `ReleaseReportValidationDossierModel`,
`VerifiedPublishedReportReceiptModel`,
`ReleaseAuthorityValidationProjectionModel`,
`ReleaseActionCompletionBasisModel`, `ReleaseActionStoreReservationPlanModel`,
`ReleaseActionStoreReservationReceiptModel`, `ReleaseActionBranchResultModel`, `ReleaseActionStateModel`,
`ReleaseActionCurrentAttestationModel`, `ReleaseActionCurrentWitnessModel`,
`ReleaseActionValidationRequestModel`, and
`ReleaseActionReceiptModel`, `ReleaseActionExecutionResultModel`,
`DisclosureOutboxReadContextModel` are strict,
deep-frozen counterparts of the closed `$defs` above. `OrganizerOpportunityArtifactReader` resolves
bounded immutable suite-manifest, fingerprint, public-report, receipt, and outbox bytes only by their
descriptor/complete hash; it never returns a parsed mapping or selects a latest revision for the
caller.
`DeploymentTrustAnchorReader.read_pinned_manifest()` independently returns exactly bounded canonical
`DeploymentTrustAnchorPinReceiptModel` bytes and `DeploymentTrustAnchorManifestModel` bytes from the
Phase-4 release-dossier store. The adapter supplies the out-of-band deployment-approval public-key
fingerprint separately from both objects, checks the 1,048,576/16,777,216-byte caps before parsing,
and never accepts a caller-named manifest or the internal unsigned canonical digest as the external
complete digest.
`CheckpointCandidateArtifactReader.read_pinned_checkpoint()` independently streams the phase-gate pin
receipt, provenance subject, candidate-build manifest and reproducible artifact bytes by their exact
descriptor/length/SHA-256. Its two separate order-witness methods return the pre-execution or final
witness and never substitute one for the other. `CheckpointCandidateGitObjectReader` streams native
commit/tree/blob objects, recomputes their SHA-1 OIDs and verifies either the frozen candidate ->
immediate-provenance -> execution-checkout path or, only after `G0` exists, the checkout -> later-
implementation -> `phase4_evaluation_complete_candidate` path. Locked checkpoint claim/evaluation/report validation requires the
subject, pin and pre-execution witness plus both readers and requires the final witness null. Open and
sealed branches require all checkpoint inputs/readers null. Later `release_readiness`/submission
requires exact ordinal-ordered pairs of both witness kinds for the two locked checkpoints and both
readers; each final witness byte-compares its embedded pre-execution descriptor/hash and complete
candidate/provenance/checkout tuple. The 4,194,304-byte subject, 1,048,576-byte pin and two distinct
4,194,304-byte witness caps plus 1,073,741,824-byte artifact/Git stream caps are checked before every
parse/read. The supplied suite/fingerprint candidate identities equal the pinned subject byte-for-byte
while its control-plane identities equal the current deployment manifest.
`ReferenceTruthSuiteWitnessReader` independently resolves the complete approval/suite-bound witness
artifact by exact descriptor/length/SHA-256 under its dedicated preparse cap.
`ReferenceTruthArtifactReader` resolves only the witness-bound executor manifest, request, output,
receipt, GoldenCase and evidence records plus the fingerprint-bound
`reference_executor_disjointness_receipt`; `ReferenceTruthSourceReader` resolves only pinned
official snapshot/source-locator bytes; and `ReferenceTruthExecutor` executes the frozen request against
those bytes and returns `ReferenceTruthExecutionResultModel`. Their aggregate counts/bytes are checked
before the first read. Every non-open suite facade supplies the exact suite witness and these protocols;
open requires them null. The higher suite/history facade resolves the approval only through the
independently current `HumanGovernanceWitnessModel`/`HumanGovernanceRecordReader`, then passes that
exact approval model to `reference_truth_suite_errors`; the artifact reader never resolves approvals.
No stored equality flag or caller `recomputed` hash substitutes for execution.
`evaluation_control_errors` and the claim gate must resolve that exact disjointness receipt and invoke
`reference_executor_disjointness_errors` against the complete deployment-pinned scorer manifest and
fingerprint candidate-build manifest;
an unresolved or substituted descriptor is a preclaim error.
`CumulativeDisclosureArchiveReader` streams only the witness-bound manifest/entry/report/receipt/outbox
bytes. `ReleaseReportDependencyReader` exposes the two exact validation-manifest/shard methods above,
recomputes the shard/list roots and aggregate counts/bytes before following any entry, and resolves every dossier-bound publication/provenance/reference/
private-control dependency and exposes the corresponding independently current resource readers;
`VerifiedPublishedReportReceiptReader` resolves each dossier-bound receipt under the 1,048,576-byte
preparse cap and Phase 4 verifies its exact deployment-pinned signature/tag/version before any mutable
join;
`ReleaseActionCurrentResourceReader.read_current()` independently returns the pinned current release-
action state/attestation/store receipt; `read_current_action(action_identity)` returns that same held-
generation tuple plus the current-root proof, leaf and branch-result bytes;
`read_current_actions(action_identities)` returns one held tuple plus one or two ordered proofs/leaves/
results against its single root; and
`read_action(action_identity)` resolves only the immutable historical tuple needed for completed replay.
It enforces the 1,048,576/16,384/4,194,304-byte state/attestation/witness caps before parse and never
treats caller bytes or a historical proof as current; `ReleaseActionBranchResultReader` resolves only
the leaf-bound result descriptor under the
16,777,216-byte cap, and the reservation plan/receipt are capped at 1,048,576 bytes each before parse;
`ReleaseActionStoreReservationReader` independently resolves the prepared plan/receipt/backend
capacity evidence used by the g0 attestor;
`DisclosureReadinessContextReader.resolve_current(report_id, revision, outbox_descriptor)` streams the
current suite-history/report-lineage/opportunity-summary and dossier-coverage proofs and returns only
`DisclosureOutboxReadContextModel`; it never accepts a readiness/cycle/opportunity identity from the
caller. `DisclosureOutboxReadTransaction` owns that reader, `AuthenticatedSessionReader`, the three
authority readers, `CurrentRegistryResourceReader`/complete five-registry witness, identity/release-
action readers and raw
outbox adapter. Its `read_exact(report_id, revision, outbox_descriptor)` accepts no context, role,
authority witness, readiness identity, proof or current-state argument and returns only canonical
public bytes or the fixed denial after the coherent guard defined above;
`PrivateReportHmacVerifier.verify_exact(reference, canonical_projection, action_nonce)` resolves only
deployment-pinned HMAC roles and returns only a tuple of typed diagnostics during the same-call
immutable prevalidation before the current-resource guard; it exposes no serializable verification
record, boolean or reusable token.
`ReleaseActionValidationRequestModel`
contains the exact action branch/artifact descriptors, deterministic action identity/nonce and expiry.
The enable branch binds its pending-target dossier and forbids a target verified-receipt descriptor;
readiness/internal-submission-package branches bind the cumulative witness and receipt-complete
dossier. It contains no mutable store object, caller-chosen generation or success claim.
`ReleaseActionTransaction.execute(request, validation_callback)` first makes the callback perform the
branch-exact immutable/reference/HMAC work without holding current resources and retains its result
only as a nonserializable same-call context. It then obtains one linearizable guard covering the three
authority resources, five registries, identity-authority resource and every dossier-named private-
control/ingress pointer plus the independently read `release-action-current` resource/witness, supplies
their independently read bytes for the short mutable join, compare-and-swaps that exact observed
release-action generation together with every branch store, performs
the exact action before releasing the guard, and returns `ReleaseActionExecutionResultModel`. The
enable branch atomically stores the verified-publication receipt/private-control snapshot/pointer plus
its release-action branch-result record and completed leaf. Readiness and `submission` each store only
their complete prepaid branch-result record and completed leaf in this same release-action resource;
there is no unpriced secondary artifact store. A
callback result cannot escape as a bearer token.
`IdentityAuthorityReader.read_current()` returns the independently current identity-authority state/
attestation/store receipt and resolves only descriptor-bound stable-identity/non-alias proof bytes under
the 65,536/65,536/1,048,576-byte caps. Validators recompute membership/revocation/subject-uniqueness
proofs and hold or recheck that observed generation through the human or owner action; Task 3 never
receives a public person identifier.
`ActivationAuthorityWitnessModel` contains the independently obtained complete current official-
instruction, trusted-clock, and submission-state attestation bytes, their externally observed current
store handles, one common three-resource read-lock receipt, the complete bounded
`ActivationAuthorityTransitionManifestModel`, and
the exact deadline/source/mapping/submission-event records referenced by the embedded freeze basis.
`ActivationAuthorityTransitionReader` streams the manifest's checkpoint and intermediate canonical
attestation/transition bytes under the generated caps;
`TrustedClockTransitionReader` exposes the same bounded verification interface restricted to the one
trusted-clock branch and rejects every official-instruction/submission-state member;
`OfficialInstructionArchiveReader` resolves those immutable bounded records by descriptor/length/SHA-
256. Neither is derived from the owner authorization object. Pure validation parses/recomputes every
projection/digest, compares the independent current resources byte-for-byte to the fresh
`submission_freeze_authority_state` in the activation-resolution source, and requires the owner
authorization/request to contain only the matching immutable exception basis. It recomputes the
effective tick and branch decision and rejects stale/substituted input; Phase 4 then
verifies the pinned Ed25519 public keys, real store-current reads and organizer evidence before the CAS.
`CurrentRegistryResourceReader` is a typed aggregate protocol: `read_current_set()` returns one
linearizable five-resource snapshot/lease receipt for the pinned suite-history, human-governance, sink-
registry, slot-preparation and AEAD-nonce resources; its evidence methods stream the descriptor-bound
slot-preparation and nonce state/row/receipt/proof bytes from the corresponding strict witness. It never
resolves a caller-selected historical descriptor as current. All pointer, witness, manifest, state and
current-read-receipt byte caps are applied before parsing.
`OwnerRemediationSignerStoreReader` independently reads the deployment-pinned signer-state current
resource and descriptor-bound Sparse-Merkle proof bytes; the blind-signer validator requires its
observed root/sequence/pointer equal the witness and the consumed key become a current member. The
same reader's `read_consumption_receipt_and_result()` returns only the immutable receipt/result pair
for one consumed key. `OwnerRemediationDecisionInputReader` independently streams the retained public-
request, approval and private-join bytes by exact descriptor/length/SHA-256 so crash recovery can
reconstruct the authorization without trusting caller copies.
The
independently current `TrustedClockCurrentWitnessModel` supplies the signing tick/read receipt used for
expiry and its clock-only reader proves the attestation chain; Task 3 checks the exact tag/projection/key-reference and byte
equalities, while Phase 4 resolves the deployment-pinned public keys and performs real Ed25519/current-
store verification before signer use.
`UntrustedCanonicalInput` is the one explicitly named I/O-boundary alias wide enough to diagnose
finite float, runtime `Decimal`, non-string-key, and other unsupported values; it is never a core-
module contract. `freeze_canonical_json` is legal only when `canonical_domain_errors` is empty.
Model/schema parity tests cover every root and named `$def`, strict no-coercion, canonical round-trip,
and attempted nested mutation. I/O adapters perform byte caps, unique-key parsing, schema validation,
and model construction before passing a value to a core module.

`HistoryTransitionWitnessModel` is a bounded, descriptor-only witness for the exact candidate/
truth-commit/post-outcome/report-receipt path, the dedicated private sink-registry lineage, and any
private sink checkpoints needed by the requested bundle stage. It includes one
`PrivateHistoryAllowanceStateModel` with the authenticated current archive head, used/remaining
record count and bytes, reservation receipt/plan descriptors, and HMAC-protected registry-state
binding. Its old/new state roots, ordered public-attestation hashes, private-history/sink record
descriptors, and Sparse-Merkle proof-bundle descriptors must terminate at the supplied authenticated
`HistoryRegistryStateModel` and private sink head, and those termini must equal the independently read
suite-history/sink current-pointer branches. Both evaluation entry points
stream those records through `HistoryRecordReader`, recompute the private sink watermark/head,
last-bound sink state, allowance counters, and report ancestry, and reject omission, reordering, or a
stale state. These records are owned and charged only by the private-history archive; the private-
control snapshot chain binds the applicable resulting roots/heads and never duplicates their
descriptors or counters.
Open validation requires the history transition/reader, human-governance witness/reader, current-
registry witness/reader, private-control current-resource reader and candidate-ingress witness/reader
arguments to be null. Every non-open stage requires all applicable arguments, requires the supplied
private-control pointer byte-equal the independent current read, and requires the human witness terminus
equal the independent human-current pointer. The coherent registry snapshot and the private-control/
ingress current generations are held under one validation-action guard or atomically rechecked before
the authorized output/read/CAS; a set of individually current observations acquired at different
serialization points is not a valid guard.

`human_governance_policy_errors` streams the bounded records/proofs, recomputes the pinned genesis,
contiguous head chain and four index roots, enforces the one-to-four-entry/32-record/byte caps, and applies
the exact approval -> atomic scope-and-all-slot-preparation -> scope-completion -> exposure transition
rules. The scope/preparation witness is accepted only when it proves the exact predecessor human head,
the candidate human state/root containing the just-built scope and approvals, and exposure
nonmembership in the predecessor root. Every slot receipt must prove membership against that same
candidate scope root, resolve its exact slot source, and require that source's one byte-identical
`scope_and_slot_prepare_commit` authority binding; the human transition contains only the scope
descriptor/hash and ordered source-descriptor-list root, never any later slot-receipt
digest. One CAS advances the predecessor human head to that candidate scope head together with the
slot-preparation current pointer and all prepared allocation generations. A scope-completion transition is
accepted only when its complete ordered terminal-closure proofs match the scope against the same
atomically guarded global head; exposure requires membership of that exact completion record.
Scope commitment likewise verifies that every required named slot absent from the suffix already has
an authenticated terminal closure at its guarded basis global head; at the initial state the only
legal scope is the exact four-entry canonical order, and every shorter suffix is invalid without each
omitted prefix closure.
`evaluation_control_errors`, `published_report_errors`, and the relevant suite-history transition
route their non-open witness through this function; open validation requires both human-governance
arguments null. A commitment string or caller-asserted root cannot substitute for the records/proofs.

`owner_remediation_blind_signer_errors` validates the public-request action branch, exact owner-
signature message/tag/encoding/key-reference and stable-person-reference equality, nonce/expiry,
fixed-length join commitment, exact public-field equality,
private-join mechanics, one-use consume receipt and result/HMAC references; it rejects a caller boolean,
channel swap, replay or private-field/public-output leak. It does not claim to cryptographically verify
Ed25519 without the deployment boundary; Phase 4 resolves the independently pinned key and verifies the
signature before signer use. `owner_remediation_errors` first routes those
four objects through that validator, then streams and strictly validates the complete private child base and, for an
activate action, the one bounded change-evidence record and complete activation-time
`submission_freeze_authority_state`; recomputes their descriptors/digests, the
public comparability projection, and both case-set quota projections; verifies the distinct-owner
identity proof and exact current parent revision/terminal/outcome/audit cause; requires the official-
instruction archive pointer still equal the fresh resolution-bound authority snapshot, applies the pre-freeze or explicit
organizer-exception branch, requires the global/human/sink lineage termini equal their independent
current pointers, and enforces the action-specific required/forbidden fields. A caller
boolean, repository-owner permission alone, or an opportunity-creation-time compatibility review
cannot substitute for that activation-time state. `child_fingerprint_extension_errors` then requires the
fingerprint's complete public basis and remediation build subject to equal those verified objects
field-for-field, recomputes both external digests and the build-resource manifest, permits only the
closed fingerprint-specific suite/reservation/history/storage/governance additions, and rejects every
missing, extra, indirect, private-governance, or unsupported changed field. The owner-resolution,
suite-reservation/claim, `evaluation_control_errors`, and child report paths route through these
functions; a bare digest or already computed boolean is never accepted.

The facade owns only argument routing, stable diagnostic aggregation, and its CLI. Focused modules
under `tools/evaluation_control_core/` own the behavior: `canonical_io.py` owns strict JSON,
Canonical JSON v1, bounded descriptor/blob readers, and hashes; `storage_reservations.py` owns both
preclaim planners, receipt/allowance transitions, and generated witnesses; `history_registry.py` owns
private fingerprints, Sparse-Merkle proofs, incremental history transitions, and streamed archive
audit; `runtime_lifecycle.py` owns runtime/dispatch/ingress/truth-capability/scoring state validation;
`remediation.py` owns conditional-child comparability, owner-authorization, change-evidence, and
fingerprint-extension validation; and `reporting.py` owns disclosure projection, candidate/published
report validation, correction lineage, and opportunity-summary/readiness validation. `__init__.py`
exports only the facade-facing typed symbols. No module may duplicate another
module's canonical projection, schema authority, or state transition, and no domain implementation is
placed back into the facade.

`disposition_policy` is null only for `open_regression`. Locked/sealed validation requires the
complete schema-valid private policy, checks its precommitted public reference everywhere, and
recomputes the terminal retirement/invalidation event from the supplied private outcome set. The
function does not authenticate its HMAC; Phase 4 performs that secret verification first.

`evaluation_control_errors` first independently reads, size-checks and strictly loads the current
private-control and ingress resources, requires the supplied pointer/attestation/state bytes equal
those real current reads, requires the private-control attestation's signed projection/complete hash
to equal the snapshot's complete hash/sequence, and streams the
bounded predecessor chain to sequence zero. It validates every snapshot, stage/delta transition,
cumulative counter, and reconstructed descriptor before streaming each referenced private record/
blob. Its non-open behavior is closed by `bundle_stage`, and an empty diagnostic tuple is legal for a
schema-valid deterministic crash prefix:

- `claimed` validates the exact current partial attempt/dispatch prefix plus the branch-exact ingress
  state. Before dispatch it requires `idle`; after dispatch it requires `receiving` or the sole
  `pending_burn` state and rejects a stale zero-buffer ancestor. It forbids a
  candidate-set seal or any truth, scoring, outcome, report, or outbox record;
- `candidate_sealed` requires the complete immutable candidate-attempt set, ingress
  `terminal_consumed` cross-bound to the exact response/control snapshot, and forbids truth release
  and every later record;
- `truth_committed` requires the exact recovery record, nonce/ciphertext, capability, and history
  successor while forbidding a terminal receipt/session, scoring, outcome, report, or outbox;
- `terminalized` requires exactly one capability-terminal branch and permits only its deterministic
  scoring-ledger prefix, while forbidding an outcome/report/outbox before finalization;
- `outcome_recorded` requires branch-complete scoring finalization, outcome index/root, and
  `post_outcome` ancestry while forbidding report/outbox records;
- `report_candidate` requires the exact embargoed private/public report pair and outbox record/blob
  but forbids a report receipt or external-read assertion;
- `published`, `corrected`, and `withdrawn` require exactly their applicable immutable predecessor
  report/correction/withdrawal records and authenticated history lineage, without deleting an
  earlier valid revision; and
- `burned` requires the exact private burn/buffer/sink/history evidence, requires any dispatched
  ingress resource be `terminal_consumed` by that exact burn snapshot, and forbids truth, outcome,
  report, correction, and outbox records.

For `report_candidate` and every later report-bearing stage, the function derives the non-open
private/public pair only from the applicable report record and outbox descriptor/blob. It treats that
pair as an embargoed candidate, validates both schemas, recomputes every private projection/hash
chain, independently supplied HMAC commitment, disclosure projection, disposition decision,
lifecycle ancestry, and non-secret cross-binding, but does not itself authorize external read.
`published_report_errors` supplies that later authorization check. An open run instead requires null
private-control pointer/snapshot/readers, parses the sole `open_public_report_bytes`, size-checks the
open manifest/readers, resolves every visible case/truth/evidence/run record, and recomputes every
outcome and report field.

`published_report_errors` first reruns all candidate checks over the byte-identical bundle report
record/outbox blob and the
complete supplied `freeze_fingerprint` object, rather than trusting only copied hashes, and then
requires the unique matching `report_recorded` (or, for a correction,
`corrected_report_recorded`) attestation plus its exact report-lineage membership proof in the
supplied authenticated current registry state. It also recomputes the
bundle's HMAC-protected private-append report hashes/commitments and closed disclosure-outbox record.
For an original locked-checkpoint publication it streams the exact scope-entry, exposure-
nonmembership, and prior-ordinal closure proofs at the exact human-governance head bound by
`report_recorded`; scope completion is not required and the report remains historical checkpoint
evidence only. Later revalidation resolves that report-time head as an authenticated ancestor and
requires the supplied current human head to equal or descend through only legal scope-completion/
exposure successors; it does not require the old exposure-nonmembership proof to remain true at the
new current root. Exact head equality is required only inside the report CAS. For a sealed
ordinal-0 invalidated report it applies the same report-time membership/exposure ancestry rule and
does not require completion; that report is historical remediation evidence and never readiness. A
sealed ordinal-0 pass requires the exact completion created after its direct child-resolution/zero-
channel-audit suffix and proves the completion's resulting global head equals that audit head. A
sealed ordinal-1 report requires its exact parent report/dependency proof and the completion whose
resulting global head equals the child's `report_recorded` head. Both completed branches verify the
authenticated current human-governance state descends from the resulting human head. An incomplete or
abandoned scope is a stable non-PASS
diagnostic for cumulative/release/submission claims even when an earlier locked member has a valid
published report.
It reconstructs
`canonical_bytes(complete schema-valid public_report)` and requires the durable outbox record bytes
to equal those bytes exactly. This is a content validator only; an empty tuple cannot authorize an
outbox read. `ReleaseActionTransaction.execute` reruns it plus secret-HMAC verification under the final
same-call immutable prevalidation before acquiring the final guard, then rechecks only its exact
content-addressed hashes and current mutable joins under that guard and performs `enable_outbox`
itself. The receipt cannot be an input to
the report hash it receipts.
This second interface is for locked/sealed reports only; repository-visible `OPEN_FULL` reports never
enter the private outbox/history receipt protocol.

Immediately before any locked/sealed outbox becomes externally readable and again before any release-
readiness/submission claim, `published_report_errors` or `release_readiness_errors` validates the
independently current three-resource official-instruction/clock/submission-state witness from the
governance-lock checkpoints through `ActivationAuthorityTransitionReader` and
`OfficialInstructionArchiveReader`. The witness is not taken from an earlier owner authorization. Its
current official snapshot must have no first-ranked disclosure/submission/one-attempt/no-correction
restriction that conflicts with the requested public action. If submission is already frozen, every
referenced candidate build/fingerprint/report/outbox must descend from bytes fixed no later than the
authenticated event, or the exact current organizer exception must authorize the changed paths. The
three current generations/clock tick and coherent five-registry snapshot are held or atomically
rechecked through external-read enablement/readiness/submission. A newer restriction/retraction,
omitted submission event, stale pre-freeze witness or point-in-time read released before the action
returns a stable non-PASS. No public readiness artifact exposes the private authority transition
manifest/source review, validation projection, current generations/tick or post-action receipt.

`release_readiness_errors` is the sole Task-3 readiness content validator used inside the authorizing
transaction; it cannot authorize a sealed release-readiness, cumulative, organizer-cycle-closure, or
submission claim by its return value. It strictly validates the supplied
`OrganizerOpportunityDisclosureSummaryModel`, streams every referenced manifest/fingerprint/public
report/current receipt/outbox through `OrganizerOpportunityArtifactReader`, checks their immutable
public/hash/receipt equality, and recomputes the current report-lineage, candidate-cycle, slot,
scope-completion, disclosure-dependency, and audit-closure proofs from the authenticated history and
human-governance witnesses. It additionally requires both unconditional locked checkpoint ordinals to
resolve to current unsuperseded original/corrected `report_recorded` lineages that independently pass
full publication validation; any locked burn, withdrawal without a current corrected report, missing
report, or failed checkpoint is cumulative non-PASS even if the sealed report passes. It accepts the
sealed portion exactly as either (a) one current unsuperseded ordinal-0 pass plus
the child's `closed_parent_pass`/zero-channel closure, or (b) ordinal-0 invalidated plus a current
unsuperseded ordinal-1 pass, with two separately preserved reports and the exact revision/hash-keyed
remediation dependency. For branch (b), the parent revision bound by owner authorization must still
be the current lineage revision byte-for-byte; any later parent adjudication, correction,
supersession, or withdrawal is a permanent non-PASS. Parent burn, owner decline, child burn/failure,
missing scope completion, blended totals, latest-only input, a noncurrent original/corrected receipt,
or a caller-selected ancestor returns a stable diagnostic and cannot yield a readiness object.
Every claimed locked/sealed slot referenced by readiness must also have its ordinary fixed-schedule
`slot_private_audit_closed` proof; the immediate zero-channel unused-child audit is separate and does
not stand in for a claimed parent/child slot audit.
It consumes the cumulative witness/dossier/readers, verifies every deployment-pinned immutable
verified-publication receipt/hash, and under the short final guard reruns only current lineage,
authority, identity, sink and audit joins. Full private-control/reference/provenance/private-HMAC
validation occurs only once for each target's earlier `enable_outbox` same-call prevalidation, never
for the cumulative archive while locks are held. `ReleaseActionTransaction.execute` then performs the selected action before releasing any currentness
guard; neither an earlier diagnostic tuple nor a caller-supplied success boolean substitutes for this
composite execution.
For locked/sealed validation, a missing current pointer/snapshot/predecessor, a caller-selected
ancestor, or a bundle stage inconsistent with the latest supplied global/lifecycle head is a stable
error. The validator never substitutes an opaque commitment for an
absent terminal receipt, session record, scoring entry, outcome projection, history append, report
append, sink projection, or outbox record.

`load_unique_json_bytes` performs strict UTF-8 decoding with no BOM, rejects duplicate object-member
names at every depth before constructing a mapping, rejects `NaN`/`Infinity`/`-Infinity`, and rejects
trailing non-whitespace data. Every repository JSON fixture and every external JSON object entering a
schema/HMAC path uses this loader or an implementation proven byte-equivalent; a generic parser that
silently keeps the first or last duplicate is forbidden. Full YAML loading for the governance and
coverage generators likewise uses a duplicate-mapping-key-rejecting safe loader and forbids anchors,
aliases, merge keys, and custom tags before lock generation. Bootstrap verification relies on the
committed byte hash/lock and never claims to parse
arbitrary YAML without its dependency.
`load_private_control_bundle_bytes` first rejects a snapshot above 65,536 bytes, then applies the same
unique-JSON rules. Pointer attestation bytes are separately rejected above 16,384 bytes before the
same strict/canonical validation. The validation entry points accept only those original current-
snapshot and attestation bytes,
stream at most `max_private_control_manifest_snapshots_per_run - 1 = 210013` predecessors of the same
cap through `PrivateControlSnapshotReader`, and invoke
the record/blob readers in reconstructed descriptor order. Each control record is capped before parsing, must
itself be canonical unique JSON matching its absolute `$ref`, and is released before the next record.
Each binary blob is length/hash checked incrementally. The validator reconciles descriptor counts,
candidate/outbox byte totals, actual used/remaining reservation bytes, and the independently
recomputed preclaim reservation. A caller-parsed mapping, missing reader object, short/extra stream,
or storage counter cannot bypass these checks.

Canonical JSON v1 accepts only null, booleans, integers, Unicode-scalar-value strings, lists, and
objects whose keys are Unicode-scalar-value strings. A string or key containing any lone surrogate
code point U+D800 through U+DFFF is outside the domain even though generic JSON Schema may call it a
string. Canonical JSON v1 rejects floats. It preserves accepted strings exactly without Unicode
normalization, sorts object keys by Unicode code point, preserves list order, and emits UTF-8 with
`ensure_ascii=False`, separators `(',', ':')`, no trailing newline, and no insignificant
whitespace. Exact decimals are strings. Hashes use SHA-256 over those bytes.

Schema validity alone does not establish hash eligibility because the existing canonical QueryPlan
permits generic JSON-number filter values and EvidenceRecord permits generic normalized values.
Before any golden, locked, or sealed case/evidence/fingerprint object reaches canonical hashing,
`canonical_domain_errors` recursively checks the entire object graph. It accepts only null,
booleans, integers, Unicode-scalar-value strings, lists, and Unicode-scalar-value-string-keyed
objects; it rejects every Python `float`, `Decimal`, non-string key, string value or key containing
U+D800 through U+DFFF, non-finite number, and unsupported runtime type with stable JSON-pointer
diagnostics. A rejected string value uses its ordinary JSON-pointer path. A rejected key diagnostic
uses the containing object's JSON-pointer path plus numeric `key_ordinal` (zero-based after sorting
only the object's string keys by their Unicode code-point tuples) and `surrogate_index`; it never
repeats the invalid key, so the diagnostic itself is UTF-8 encodable and deterministic. If an object
contains any non-string key, one aggregate diagnostic at the containing-object path records only the
total plus the sorted `(runtime_type_name, count)` multiset; traversal skips values reachable solely
through those invalid keys but continues through every valid string key. This avoids trying to sort,
stringify, or JSON-pointer-encode an arbitrary invalid key. Every non-integral
financial/filter/evidence value in this evaluation plane must be a
non-exponent exact-decimal string; an integral count may remain an integer. This is an evaluation
eligibility overlay and does not broaden Task 3 scope to modify the canonical QueryPlan or existing
EvidenceRecord semantics.
When and only when that diagnostic tuple is empty, `freeze_canonical_json` recursively converts arrays
to tuples and objects to `FrozenMap` without coercion or normalization. `canonical_json_sha256` accepts
only the resulting immutable `CanonicalJsonValue`; mutating the original parsed container afterward
cannot change the frozen value or any derived digest.

`build_private_case_fingerprints` first requires both inputs to be schema-valid and
canonical-domain-valid, ignores every caller-supplied digest, and recomputes three exact values.
`QUESTION_NORMALIZATION_V1` replaces CRLF/CR with LF, applies Unicode 15.0.0 NFC, maps each
non-empty run of ASCII space/tab/LF/vertical-tab/form-feed to one U+0020, and strips leading/trailing
U+0020. `normalized_question_sha256` hashes the resulting UTF-8 bytes.
`evidence_package_content_sha256` is the Canonical JSON v1 SHA-256 of the complete schema-valid and
canonical-domain-valid private evidence package. `truth_sha256` hashes Canonical JSON v1 of exact
keys `expected_plan`,
`expected_result`, `expected_answer`, and `evidence_package_content_sha256`.
`case_content_sha256` hashes Canonical JSON v1 of exact keys `question`, those three truth objects,
`evidence_package_content_sha256`, and `provenance`. The normalization/producer version is stored in
each private entry; unknown versions fail closed. Phase 4 separately verifies that the
domain-separated public `evidence_package_commitment` covers the same package bytes before signing history.

The history genesis/state/transition inputs are absent only for `open_regression`. Normal locked/
sealed validation receives the externally pinned genesis identity, authenticated current state,
exact predecessor/candidate attestations, touched content-addressed records, and old/new Sparse-
Merkle proof-bundle descriptors/chunks. The pure function requires Phase 4 to have secret-verified the
state HMAC and itself
rejects malformed/mismatched commitment metadata, a stale predecessor, missing proof/record, illegal leaf
transition, revision gap, genesis/registry substitution, or head substitution without loading prior
untouched records. Separately, `suite_history_archive_errors` first validates authenticated lifetime
opportunity, scope, revision, manifest, descriptor and byte totals against the global caps without
opening a record; creation of the next opportunity stops before any bound would be exceeded. It then
uses the archive-audit human witness to discover and stream the complete ordered human-governance
chain, and streams the complete ordered public/private history archive from pinned revision 1 to the
externally supplied final states. It
recomputes every attestation/state transition for full audit; a bare final root plus a lookup-only
reader is insufficient. A manifest and fingerprint require their
`eligibility_history_head_sha256` to be the exact matching
`suite_reservation` ancestor. A published truth-committed report requires its
`truth_release_commit_history_head_sha256` to be the matching commit ancestor and its
`post_outcome_history_head_sha256` to be the later matching outcome-receipt ancestor; the current
chain must additionally contain the unique matching `report_recorded` receipt for an original report
or `corrected_report_recorded` receipt for a correction, and the externally supplied current head
must equal or descend from that receipt. Exact equality is required only inside the atomic
append/CAS transaction that issues a successor; later verification
must not invalidate an older report merely because a later valid reservation, adjudication,
continuity event, or outcome advanced the same chain.
An embargoed candidate is validated only through its post-outcome ancestry and deliberately fails
`published_report_errors` until the receipt CAS and outbox write both exist.

Events are append-only and contain event ID/type, suite ID/version, prior and next state,
checkpoint, candidate fingerprint, actor role ID, timestamp, truth-release state, reason code,
`previous_event_sha256`, and `event_sha256`. The genesis previous hash is null. Every later
`previous_event_sha256` equals the preceding `event_sha256`; each `event_sha256` is SHA-256 over
Canonical JSON v1 of the complete event with only root `event_sha256` removed. Event type is one of
`state_transition`, `exclusion_approval`, `run_binding_attestation`,
`candidate_attempt_set_sealed`, `attempt_transport_closed`, `private_audit_closed`,
`truth_release_authorized`, `truth_capability_terminalized`, `outcome`,
`infrastructure_attestation`, `disclosure_authorized`, `invalidation`, `retirement`, or
`adjudication`. An
`exclusion_approval` is a
self-state event on
`human_reviewed` before lock/seal; it binds an HMAC commitment to the private exclusion list. An open
event may expose reason/count/applicability totals. A non-open public event exposes only total
excluded count and the commitment; reason codes and fine applicability counts remain private unless
the same predeclared all-or-none K5 cell/complement rule later authorizes them. A
`run_binding_attestation` follows the atomic consuming
claim/transfer but precedes the global truth-release commit and binds the exact candidate fingerprint
to the suite/history commitments and eligible invocation-set commitment without exposing per-case
metadata. A `candidate_attempt_set_sealed` event is required before a truth-release commit and binds
the eligible count and secret-backed candidate-attempt-set commitment without exposing invocation
IDs, per-case terminal states, accepted-output flags, or response content. An
`attempt_transport_closed` event contains the exact domain-separated
`attempt_transport_close_commitment` and the
closed dispatched-infrastructure or undispatched-token aggregate transport/fence commitment defined
below; its per-case/request fields remain in the HMAC-protected private record. An
`infrastructure_attestation` public event likewise exposes only suite-run identity and its HMAC, never
invocation identity or a case outcome. `private_audit_closed` occurs exactly once for every claimed
terminal slot at its fixed policy schedule, whether the private sink has zero or many receipts. It binds only
the matching `slot_private_audit_closed` attestation, public-safe
`schedule_offset_profile_id`/version and existing suite-specific storage HMAC reference; it forbids the
per-scope schedule ID/ref/descriptor/hash/ticks and a private event
kind, late-byte boolean/count/watermark/head, invocation/attempt identity, candidate content, content
hash, length, or any conditional marker. Receipt/checkpoint audit records exist only in the private
sink/history stores and never create a lifecycle event when observed. A never-activated conditional
child has no lifecycle head; its strict zero-channel audit branch is validated from the candidate-
cycle resolution and sink-registry proof and expressly forbids fabricating this lifecycle event.
The same no-event rule applies to every `never_claimed_preclaim_close` locked/P3/ordinal-0 audit; only
the typed close source and zero-channel sink transition establish continuity.
`truth_release_authorized` mirrors the winning global commit but does not claim that a truth session
exists and keeps `truth_released: false`. `truth_capability_terminalized` follows the store
transaction, binds exactly one terminal state and non-null receipt commitment, sets
`truth_released: true` only for `redeemed_with_durable_truth_session` and false for revocation, and
precedes every outcome. Its public `reason_code` is exactly `TRUTH_DELIVERED` for redemption and the
single invariant `TRUTH_NOT_DELIVERED` for either private revocation cause. It never exposes whether
deadline expiry or an authority conflict won; that exact cause exists only in the HMAC-protected
terminal receipt and private outcome/report join. For either revoked cause, this public terminal event
and its cause-derived public `outcome` event require literal
`timestamp: "1970-01-01T00:00:00Z"` and literal actor role
`evaluation_custodian_service`; real observed/terminal/outcome ticks and actor identity remain private.
Event hash and secret-backed commitments are explicitly opaque fields that may differ, but every other
public event field is byte-identical for matching eligible inputs. A real timestamp, different writer
role, deadline-relative bucket or missing sentinel is invalid. Before truth-terminal cause selection,
`truth_release_commit` durably preallocates one strict `$defs/revoked_public_id_plan` for the
terminal event, outcome event, disclosure-authorized event, disposition event, report, report-history
source/receipt, disclosure-outbox record/blob and verified-publication receipt. Each ID is exactly
`SHA256(b"FinProof/RevokedPublicId/v1\x00" || canonical_bytes({suite_id, run_attempt_id,
release_cycle_or_checkpoint_identity, report_revision: 0, purpose})))` lowercase hex; purpose is one
closed distinct literal and the projection forbids terminal cause/tick/actor/result/HMAC. Both revoked
causes must consume the same preallocated plan, and correction IDs derive only from that original
report ID plus revision under their existing fixed tag. Caller-selected, cause-coded, post-cause random
or reallocated retry IDs are invalid. Recovery reuses the committed IDs byte-for-byte. The plan is
private-control evidence bound in the truth-commit HMAC, while the IDs themselves appear only in their
ordinary public owners; no extra public linking object is emitted.
The complete embedded plan is capped at 16,384 canonical bytes, has `additionalProperties: false`,
and is byte-identical in the truth-commit private append and recovery-record projection; it is not a
separate record or a new HMAC domain.
`disclosure_authorized` is an embargoed self-state event created only after the private/public report
pair is finalized; it binds their verified hashes/commitment and disclosure class but does not expose
the report or assert publication. The lane's terminal retirement/invalidation event follows it and is
mechanically selected under the precommitted disposition policy; no model output or public disclosure
can alter that rule. Both events reproduce the disposition-policy ID/version/commitment and HMAC
metadata, and the terminal event records the mechanically recomputed rule result. The
later atomic `report_recorded` history/outbox CAS binds both lifecycle events and durably freezes the
canonical outbox under embargo. It is never a read grant; only the separate guarded
`enable_outbox` action may make it externally readable.

For a non-open suite there is no second lifecycle-current resource. The sole authoritative value is
`lifecycle_current_head_sha256` in the hash-verified current private-control snapshot named by the
independently read signed pointer.
The reservation/claim transaction above initializes it directly to the consuming-event hash. Every
later lifecycle append observes that pointer, writes the event and a new private-control snapshot with
the recomputed event hash, then advances the pointer by one generation in the same CAS as all related
global/sink/outbox changes. A stale pointer, duplicate
event ID, competing successor, missing head, or successful event write without the matching head CAS
fails closed; the losing writer does not treat its event as durable. Recovery may replay only the
byte-identical intended successor and accepts it only when the stored head already equals that same
event hash. The append-only lifecycle event store is evidence, not a competing current-head authority.
An open suite has only its self-contained event chain and no non-open-currentness claim.

The validator checks the hash
chain, unique IDs, legal transitions,
checkpoint/lane compatibility, fingerprint equality, exclusion timing and totals, suite-history
attestation consistency, disclosure rules, and report reconciliation. For `consumption_claim`,
`consumption_claim_transfer`, `consumption_claim_burn`,
`truth_release_commit`, `post_outcome`, `report_recorded`, and `post_adjudication` public variants it compares every
permitted public run-attempt/transport-close aggregate, release-fence-token hash/recovery-record ID,
candidate-attempt-set and outcome-set commitments, truth-capability terminal state/receipt,
event/attestation hash,
public-report hash, private-report commitment, slot state, and budget delta to the supplied
lifecycle/report objects. For
`corrected_report_recorded` it compares the final
corrected public report hash and independently supplied private commitment to the corrected reports;
for `slot_private_audit_closed` it requires the public-safe offset-profile/HMAC projection above. Its
`claimed_run` branch requires the matching `private_audit_closed` lifecycle event, then uses the
private witness/reader to compare the exact prior/new monotonic sink watermark/head pairs, all newly
added ordered content-free receipt projections/HMACs, destruction receipts, and recomputed chained
sink-ledger head. Its `never_activated_conditional` branch instead requires the exact immediately prior
candidate-cycle-resolution head, null run/lifecycle event, zero-channel/nonmembership-to-closed sink
proof, and the allocation terminal states above. Its `never_claimed_preclaim_close` branch instead
requires the exact authority-or-schedule close source/head, preparation and both allocation states,
branch-exact binding/transition, null run/conditional resolution/lifecycle event and the same zero-
channel sink proof. Cause, slot, schedule or close-head substitution fails. Every other
global successor likewise validates its privately consumed sink delta without exposing it publicly;
the Phase 4 secret-backed private-history check separately verifies the private report hash and
subject. A public/private opaque commitment alone never proves the non-secret cross-object bindings.

The module uses the approved `jsonschema`/`referencing` dependencies and the closed offline registry
to validate every supplied object before policy logic. It never fetches a remote schema and is not a
`python -S` bootstrap target; only `tools/verify_handoff.py` has that dependency-free obligation.

`build_history_projection` rejects unknown fields and returns the exact eight-key private projection
defined in Section 8.5; it never receives a key. `suite_history_policy_errors` is deterministic. It
validates the pinned genesis/registry, prior bounded state and predecessor, streams every touched
record/proof-bundle chunk, verifies the exact old/intermediate/new roots, recomputes the candidate
eight-key projection and
bounded resulting state, and checks the variant's local state-machine invariants. It cannot accept a
copied root in place of a proof. `suite_history_archive_errors` alone streams/reconstructs all prior
attestations, records, fingerprints, derivation ordinals, lane memberships, reserve order, disclosure
budgets, slot/claim/transport/truth/report transitions, human approval/scope/exposure transitions,
and dependencies across all suite versions.
Together they reject a new genesis, stale-head fork, forged fingerprint, public/private disagreement,
visible/locked/sealed overlap, reuse, truth-equivalent duplication, cycle, a result-informed suite/case/
truth/evidence-selection descendant,
optional stopping, or release-cycle reset without making the normal transition API unbounded.

Neither pure function claims to authenticate an HMAC. Phase 4 must obtain an empty policy result,
rebuild each projection with `build_history_projection`, and verify the secret HMAC over its
Canonical JSON v1 bytes before it may issue or trust the public history attestation. Task 3 uses
synthetic keys and private fixtures only to prove the formula and this ordering.

Stable governance diagnostic IDs begin with `EVL001_INVALID_TRANSITION`,
`EVL002_BROKEN_EVENT_CHAIN`, `EVL003_DUPLICATE_EVENT`, `EVL004_TRUTH_LEAKAGE`,
`EVL005_FINGERPRINT_MISMATCH`, `EVL006_ILLEGAL_RETRY`, `EVL007_ALREADY_CONSUMED`,
`EVL008_DENOMINATOR_MISMATCH`, `EVL009_DISCLOSURE_VIOLATION`,
`EVL010_COMMITMENT_MISMATCH`, `EVL011_UNREGISTERED_CHECKPOINT`, and
`EVL012_MISSING_ATTESTATION`, `EVL013_SUITE_HISTORY_CONFLICT`,
`EVL014_EXCLUSION_NOT_PRECOMMITTED`, `EVL015_ATTRITION_MISMATCH`,
`EVL016_HISTORY_CHAIN_INVALID`, `EVL017_DISCLOSURE_BUDGET_EXCEEDED`,
`EVL018_PRIVATE_FINGERPRINT_MISMATCH`, `EVL019_REPORT_PROJECTION_MISMATCH`, and
`EVL020_RUN_BINDING_REPLAY`, `EVL021_HISTORY_ANCHOR_MISMATCH`,
`EVL022_HISTORY_HEAD_CAS_CONFLICT`, `EVL023_POST_OUTCOME_HISTORY_MISSING`,
`EVL024_RETRY_LIMIT_EXCEEDED`, `EVL025_EXPECTED_PRIVATE_COMMITMENT_MISMATCH`,
`EVL026_HISTORY_EVENT_BINDING_MISMATCH`, `EVL027_ADJUDICATION_HISTORY_MISSING`,
`EVL028_GLOBAL_CONSUMPTION_SLOT_CONFLICT`, `EVL029_CANONICAL_DOMAIN_VIOLATION`,
`EVL030_RESERVE_ACTIVATION_MISMATCH`, `EVL031_CORRECTION_BINDING_MISMATCH`,
`EVL032_TRUTH_RELEASE_FENCE_CONFLICT`, `EVL033_TRANSPORT_FENCE_VIOLATION`,
`EVL034_SLOT_BURN_MISMATCH`, `EVL035_TRUTH_CAPABILITY_TERMINAL_CONFLICT`,
`EVL036_RETIRED_TOKEN_LEDGER_MISMATCH`,
`EVL037_TRUTH_CAPABILITY_RECOVERY_MISMATCH`,
`EVL038_LIFECYCLE_HEAD_CAS_CONFLICT`, `EVL039_OUTCOME_SET_MISMATCH`,
`EVL040_CASE_ATTEMPT_BINDING_MISMATCH`, `EVL041_DISPATCH_RECEIPT_MISMATCH`,
`EVL042_OUTPUT_SINK_WATERMARK_MISMATCH`, `EVL043_REPORT_CLOSURE_MISSING`,
`EVL044_ORGANIZER_CYCLE_AUTHORIZATION_INVALID`, and
`EVL045_REPORT_LINEAGE_CONFLICT`, `EVL046_DISPOSITION_POLICY_MISMATCH`,
`EVL047_DUPLICATE_JSON_MEMBER`, and `EVL048_DUPLICATE_CONFIG_KEY`. Diagnostics sort by code,
suite ID/version, event position,
and object path.

Lane behavior is:

- `open_regression`: visible and rerunnable; never eligible for locked/sealed metrics;
- `locked_validation`:
  `draft -> human_reviewed -> locked -> checkpoint_consuming -> checkpoint_consumed -> retired`,
  with the two explicitly bounded pre-truth infrastructure branches in this section;
- `sealed_holdout`:
  `draft -> human_reviewed -> sealed -> eligible -> consuming -> consumed -> retired|invalidated`,
  with the same bounded pre-truth infrastructure branches.

The terminal branches are lane-specific. Here “before truth release” means before the global
`truth_release_commit`; after that CAS the budget remains consumed even if decryption or outcome
persistence later fails. A locked suite with truth release always moves from
`checkpoint_consumed` to `retired` under embargo immediately before `report_recorded`; the original remains retired
even when its result informs later tuning, and the next checkpoint uses the next precommitted,
disjoint reserve suite/version. Before truth release only, a claim abort/fingerprint change may move
`locked|checkpoint_consuming -> invalidated` only through a terminal slot burn; no release or
replacement exists. A dispatched failure is sealed as that invocation's typed outcome. An ordinal-0
failure can transfer to the sole ordinal-1 binding only while no dispatch/outbox commit or egress
occurred; if ordinal 1 cannot reach dispatch, the exact binding remains recoverable or the slot burns.
An unfenced or late-byte attempt likewise requires slot burn and suite invalidation. A sealed suite moves
from `consumed` to `retired` only when the precommitted disposition policy accepts the unchanged
candidate under embargo; the same policy moves every non-accepted outcome to `invalidated` before
the report becomes readable. Later result-informed tuning, adjudicated defect, candidate-fingerprint
change, rejection, or abandonment appends withdrawal/adjudication metadata but does not change either
terminal state. Before truth release only a terminal burn may move
`eligible|consuming -> invalidated`. Each candidate-cycle cap and one-member batch forbid a second
suite in that cycle; the sole precommitted ordinal-1 conditional child under the shared organizer
opportunity is the only separate sealed cycle. Before truth release, a suite/fingerprint binding that changes is burned and invalidated rather
than rebound. `invalidated` and `retired` are terminal. Truth
edits always create a new suite ID/version and commitment. Contract tests exercise every locked and
sealed branch and reject cross-lane transitions.

“Terminal” forbids rerun and state transition, not append-only correction metadata. A typed
`adjudication` event may self-append on `retired` or `invalidated`, references the affected report
public hash, secret-backed private commitment, stable defect decision, and `correction_expected`,
and never reopens the suite. It may target only the current unsuperseded report-lineage head; the
event and `post_adjudication` CAS atomically mark that exact revision superseded/withdrawn. Its private
history record also binds
the affected private report hash. A locked defect found after retirement therefore uses adjudication rather than an
impossible `retired -> invalidated` transition. A sealed post-retirement adjudication withdraws any
release claim; the one-result-bearing-disclosure budget remains consumed.

Adjudication is globally visible before any later disclosure or suite reservation. The custodian
always appends and CAS-publishes a `post_adjudication` successor binding the adjudication-event hash,
current public report hash, current private-report commitment, revision, supersession/withdrawal decision,
and `correction_expected`. When that flag is false, the private append contains only the current
private-report control-record descriptor ID/length/SHA-256 plus complete digest/commitment; validation
streams the report. The branch is terminal, no `corrected_report_recorded` is permitted, and a
later otherwise-eligible reservation may extend that head. This represents withdrawal/supersession
without fabricating a replacement report.

Every `post_adjudication` target—true correction or withdrawal—must already have a completed
`enable_outbox` action leaf under the independently current release-action state, a matching verified-
publication receipt and repository-readable canonical outbox. A merely `report_recorded` but still
embargoed revision is not an adjudication target. A defect discovered before `report_recorded` is
handled by rebuilding the still-uncommitted candidate bytes or by the ordinary non-report terminal
failure path; after `report_recorded`, the immutable failure/report must first become readable rather
than being hidden by a prepublication adjudication. Thus the only legal order is original report
closure -> original enable -> optional adjudication/correction closure -> corrected enable, and each
revision retains its own action leaf/receipt.

When `correction_expected` is true, the lineage must have no prior true correction. First construct a
closed `correction_derivation_record`. It has exactly record/rule ID and version, closed rule kind
(`reference_executor_recompute_v1`, `evidence_binding_recompute_v1`, or
`report_projection_recompute_v1`), deterministic rule-artifact and independent-reference-executor
IDs/SHA-256, literal policy authorization `objective_custodian_correction_rule`, adjudication evidence
IDs/content hashes, current complete
public/private report hashes, original outcome-set commitment/content hash, immutable candidate-set,
truth-session, fingerprint, scorer/rule, selected execution-contract/common-response/isolation-profile
and policy bindings, ordered affected ordinals,
canonical input projection SHA-256, recomputed output projection SHA-256, and resulting corrected-
outcome content SHA-256. Manual replacement outcome values are not fields.

For `reference_executor_recompute_v1`, the record additionally carries the ordinal-ordered affected
original reference-truth-suite-witness entries: exact derivation-receipt, suite-wide executor-manifest,
execution-request and execution-result descriptors/hashes. They must match the immutable original
case-set/session/fingerprint inputs byte-for-byte and are rerun through the same reference executor;
a new/substituted executor artifact, source locator, QueryPlan or expected truth is forbidden. This
branch may correct only scoring/evidence/report derivation from unchanged truth. If the rerun would
change an expected result/answer or any hidden truth binding, `correction_expected: true` is illegal
and only deterministic withdrawal is allowed. Correction is an objective policy-authorized custodian
transition, not a discretionary or unauthenticated owner-approval field.

The validator executes the named immutable correction rule against the supplied exact inputs and
requires byte-identical output. A correction may repair only evaluator/reference/evidence/report
derivation; it cannot change candidate bytes, hidden truth, source evidence, freeze identity, scorer/
rule, threshold, original terminal disposition, or consumed disclosure budget. It cannot turn a
withdrawn/failed release into an accepted one. If deterministic recomputation is unavailable, differs,
or would require manual editing, the only legal branch is `correction_expected: false` withdrawal.
At most one true correction exists per report lineage; later defects may withdraw the current report
but cannot publish another correction.

Before `correction_expected: true` is legal, the validator first builds strict head-independent
`$defs/corrected_disclosure_aggregate_projection` from the already receipted original public payload
and the proposed corrected public aggregates. It contains exactly projection version, report ID,
target original/current revision and complete public-report hash, intended next revision, unchanged
disclosure class/partition identity, the complete corrected public aggregate cells/suppression markers,
and no report wrapper/head/attestation/commitment. Its external SHA-256 is computed over its complete
canonical bytes. One closed private `$defs/correction_disclosure_delta` then contains that projection/
digest, the original disclosure-payload digest, the ordered changed public aggregate cells, and for
each changed cell its original/corrected denominator/numerator, absolute delta, and both original/
corrected complement values. Both objects expressly forbid the future adjudication head, corrected
report subject/final public or private report hash, canonical report hash/attestation, private-report
HMAC reference, corrected receipt/outbox/future head, and their own digest. The record contains no case
ordinal/identifier and is HMAC-protected through the correction private append. For every separately observable changed denominator, numerator, outcome,
exclusion, category, product, or metric value, the record derives the smallest already published
`comparison_universe_denominator`: overall values use eligible; a partition-cell numerator/outcome
uses that cell's applicable original and corrected published denominator; and a denominator-membership
change uses its published parent/global universe. It requires `abs(corrected - original) >= cell_k`
and both applicable original/corrected universe remainders after that absolute delta to be at least
`cell_k`; the same arithmetic applies independently to every changed partition cell and published
complement under the original predeclared all-or-none view.
Grouping unrelated changes after observation is forbidden. If any nonzero delta is one through four,
if its complement is below five, if the original publication did
not expose the same partition, or if a safe delta cannot be derived deterministically, the only legal
public branch is `correction_expected: false` withdrawal. The corrected facts may remain in the
custodian-private adjudication record but no corrected public report/outbox is created. Thus two
individually K10-valid reports cannot disclose a K1-K4 correction by subtraction.

After that proof, construct and HMAC the corrected outcome set from the immutable original outcome set
plus the recomputed derivation; it binds the current report and intended next revision. Then construct
the custodian-private corrected-report subject:
the complete intended corrected private report with root `adjudication_history_head_sha256` and
`canonical_report_sha256` removed and nested `attestation.value` removed; no other field is omitted.
Its Canonical JSON v1 SHA-256 is `corrected_report_subject_sha256`; that digest remains inside the
HMAC-protected private append and is never published as a plain hash. The subject is one closed
content-addressed control record; its descriptor ID/length/SHA-256 and subject digest are bound by the
append, and the validator streams/recomputes it. The `post_adjudication` private append then
additionally binds the correction-derivation, correction-disclosure-delta, and corrected outcome-
index/root record descriptors; it
never inlines those objects or the report subject. The corrected
private report requires `supersedes_private_report_sha256`, `supersedes_public_report_sha256`,
`adjudication_event_sha256`, and the resulting `adjudication_history_head_sha256` and must reproduce
the bound subject. The corrected public report requires only `supersedes_public_report_sha256` plus
the same event/head, explicitly forbids the private predecessor hash, and must equal the deterministic
disclosure projection of that corrected private report. Its aggregate/suppression fields equal the
earlier `corrected_disclosure_aggregate_projection` byte-for-byte; only the closed report wrapper,
resulting adjudication head, final hashes/attestation and receipt-dependent fields may be added. After finalizing the
corrected private report hash/attestation, independently computing its private commitment, and
deriving/finalizing the corrected public report, the custodian appends a
`corrected_report_recorded` successor publicly binding the exact corrected public report hash and
private-report commitment while its private append additionally binds the corrected private-report
record descriptor/hash, original/corrected outcome-set commitments, and the head-independent outbox
record plus binary descriptor ID/length/SHA-256. It never duplicates outbox bytes or includes its
future resulting head. The CAS updates the unique lineage/receipt maps but leaves the outbox record
embargoed. A separate guarded `enable_outbox` action creates the corrected revision's own verified-
publication receipt and alone may make it readable. No intervening registry append or sink receipt is permitted between the
two correction successors; the held barrier covers both revisions and the outbox CAS.
For a sealed correction, that same CAS advances the sealed-disclosure head/count by exactly one entry
from the corrected candidate's bound predecessor and never rewrites the original entry.
Corrected disclosure and any later suite reservation are forbidden until that second CAS succeeds.
The corrected report remains acyclic because it binds the `post_adjudication` head; the later
`corrected_report_recorded` attestation is its externally verified receipt, and the supplied current
head must equal or descend from that receipt.

Before any suite-local consuming transition, the runner generates a fresh run-attempt ID and must win
the global two-revision reservation/claim transaction for the checkpoint/release-cycle budget slot.
It accepts only `slot_state: free`; verifies the one-member reserve batch, its sole ordinal, and
`reserve_batch_claim_gate_state: active`; verifies that the slot is not active,
`authority_closed_preclaim`, `scope_deadline_closed_preclaim`, burned,
truth-committed, or `closed_unused_conditional`; binds the exact suite,
reservation hash, candidate fingerprint, fresh suite `run_attempt_id`, prior global head, and complete
empty retired-token fence-ledger commitment; atomically rejects any prior-token late-byte receipt; and
exhausts the one-member batch while moving the slot to active with no truth or result-bearing delta.
A sealed ordinal-0 claim atomically updates its candidate-cycle leaf `free -> active`; a sealed
ordinal-1 claim accepts only the directly preceding `activation_authorized` resolution and atomically
updates that leaf to `active`. No resolution, reservation, or claim may duplicate either mutation.
That transaction's final lifecycle member is the suite-local state transition from `locked` to
`checkpoint_consuming` or from `eligible` to `consuming`; it contains `truth_released: false` and the
exact `consumption_claim_head_sha256`. A losing or stale claimant durably receives none of the
manifest, fingerprint, claim, preclaim lifecycle chain, consuming event, or truth handle.

Only that local winner may append a valid `run_binding_attestation`. Its
`previous_event_sha256` equals the winning consuming event's `event_sha256`, binds the active global
claim/transfer head, one fresh suite `run_attempt_id`, the immutable eligible count, and the ordered
case-invocation binding defined in Section 8.1. The secret HMAC covers the complete private
case-fingerprint/ordinal mapping; the public event exposes only eligible count and its commitment.
Every case-attempt/candidate-invocation/channel ID is globally unique. Each case sink
accepts at most one request and one terminal response stream under its binding. That event does not
unlock truth.

Immediately before each sequential dispatch, the custodian creates one immutable private
`case_attempt_binding` record and domain-separated `case_attempt_binding_commitment`. It binds the
suite run/root run-binding,
case ordinal, opaque invocation ID, private case fingerprint, fresh case-attempt/candidate-invocation
IDs,
attempt ordinal, output-channel token hash, dispatch policy, and active global claim/transfer head.
The sink, never the runner/caller, generates a fresh uniformly random 256-bit raw channel token per
case attempt. While the attempt remains `bound`, that token is ingress-inactive and may only be
tombstoned by `undispatched_token_closed`. The raw value is activated/delivered only by the atomic
dispatch-commit transition to the authenticated transport/sink path, is never reused/public/logged,
and ingress requires that token plus the bound transport identity/fence epoch;
only its lowercase SHA-256 enters commitments. Caller-supplied, predictable, reused, or unauthenticated
tokens fail before dispatch. The binding
also binds the selected execution kind/contract ID/version/hash, common response-contract hash, the
private committed question ID/text, and their exact correspondence. Its closed branch is:

- `deterministic_core`: exact callable/adapter, deterministic request/result fragment and QueryPlan
  schema hashes, canonical deterministic request bytes, the case's complete precommitted canonical
  QueryPlan bytes/hash, candidate-isolation/local-invocation profile, and
  `candidate_network_egress: forbidden`; it forbids HCX/prompt/provider, HTTP method/path/query,
  origin/TLS, transport-request, and API cache/retention fields; or
- `end_to_end_api`: literal method `GET`, literal path `/answer`, exact canonical query-parameter bytes
  for `question_id` then `question`, authenticated origin/TLS and transport profile, and all required
  HCX/prompt/provider/no-store fields; it forbids caller-supplied QueryPlan/callable fields.

A pre-dispatch check proves exact equality to the committed private case and selected contract. None
of those input fields enter public artifacts.

For `end_to_end_api`, canonical query serialization is closed and byte-level. Both names and both values must already be
Unicode-scalar strings; no Unicode normalization is performed. Serialize exactly two pairs in this
order: `question_id`, then `question`. UTF-8 encode each name and value, preserve bytes in the
RFC 3986 unreserved set `A-Z a-z 0-9 - . _ ~`, and percent-encode every other byte using uppercase
hexadecimal. Space is `%20`, never `+`. Join each encoded name and value with `=` and the two pairs
with one `&`; no leading `?`, omitted field, duplicate field, alternate ordering, or additional
parameter is legal. The private attempt binding stores the complete resulting query bytes as base64
and the dispatcher sends exactly those decoded bytes after `/answer?`. Tests freeze vectors for
Korean text, space, literal `+`, `%`, `&`, and a rejected lone surrogate.

For `end_to_end_api`, the bound transport profile fixes the exact HTTPS origin and authenticated TLS/hostname policy,
disables redirects and every client/proxy automatic retry, permits exactly one network send for the
dispatch receipt's transport ID, and accepts only one HTTP 200 response under the registered framing
and response-size limits. A 301/302/303/307/308, transparent reconnect/retry, alternate origin,
second response, or status/framing substitution is the same attempt's consuming
`protocol_violation`, never a fresh request or evaluation-exempt retry.

The deployment controller enforces the branch-specific deny-by-default outbound network policy for
the candidate service. Deterministic core permits zero candidate network/provider calls; any observed
attempt burns as `provider_egress_fence_breach`. In end-to-end mode, every allowed HCX/provider call
emits a content-free invocation receipt bound to
the case dispatch, exact destination/model/deployment identity, and policy-declared invocation
cardinality. The egress controller denies before network egress a third provider invocation for one
case attempt, an invocation above 20,000 across a maximum-size suite, or any provider transport retry.
That proven pre-egress denial seals the invocation as
`protocol_violation/PROVIDER_POLICY_DENIED` and never creates another evaluation attempt. Named
custodian operational-service calls are separately classified and payload-
restricted; live market-data, search, enrichment, or any other external financial-fact API is denied
even when non-generative. The candidate-attempt seal
reconciles the complete receipt set. Any alternate or extra call/retry that actually escaped the
controller, any unreceipted host, or any missing/unverifiable expected receipt burns/stops the slot as
`provider_egress_fence_breach`; it cannot be downgraded to a case outcome. The pre-egress-denied and
escaped/unverifiable branches are mutually exclusive.
Task 3 models the receipt/policy interface; Phase 4 tests deterministic-core no-egress and end-to-end
provider caps against the real network sandbox.

For `end_to_end_api`, because the organizer contract requires query parameters, Phase 4 also binds and verifies a
`locked_sealed_query_logging_v1` policy: proxy, load balancer, application server, APM, tracing,
exception, access, and transport logs disable or irreversibly redact `question`, `question_id`, and
the raw URI before persistence. Only opaque suite/run/transport IDs may be retained, and log storage
is denied to implementers/model-output observers. All intermediary/client/application response caches
and request caches are disabled, requests/responses carry `Cache-Control: no-store`, and raw request/
response bodies persist only in the custodian-private attempt store. HCX/provider prompt history,
trace, training retention, telemetry, and consoles must likewise be disabled or custodian-only and
inaccessible to implementers; if the provider cannot attest that mode, locked/sealed execution stops.
A canary containing unique Korean query text must be absent from every real deployment log, cache,
history, console, and non-custodian storage sink before locked/sealed execution. Task 3 freezes this
contract; Phase 4 proves it against the deployed path and stops on any leak. Deterministic core instead
uses a branch-specific local-process logging/no-cache policy that redacts the request, QueryPlan, and
response from every non-custodian log/trace and forbids network/provider history fields.

The private attempt store atomically changes that invocation/ordinal from `unbound` to `bound`; a
duplicate or conflicting record loses and no request is sent. An ordinal-1 binding additionally binds
the exact transfer head, prior ordinal-0 binding, infrastructure and transport-close attestations, and
retired-token-ledger successor. Candidate sealing accepts only the exact winning binding. The final
set projection contains every initial/retry binding, so an unbound retry request or substituted token
cannot enter truth release.

Dispatch uses a durable transactional outbox. The attempt store first persists an exact
`dispatch_prepared` record without activating ingress. The trusted controller then holds the
immutable runtime lease and the slot's exclusive registry/sink-fence lease shared with burn. At the
branch-specific invocation boundary it first constructs the fresh trusted observation from the
head-independent `dispatch_prepared` subject, exact binding/input hash, runtime/isolation state, and
invocation ID; that observation forbids the future dispatch-receipt commitment and invocation result.
It then constructs the dispatch receipt over that observation hash plus the exact binding/input bytes,
runner, dispatch sequence, commit timestamp, owner/head/fence/lease values. One transaction verifies
the exact active owner, expected registry head, output-sink fence epoch, runtime identity/deadline, and
still-live token; persists both acyclic objects; and changes `dispatch_prepared ->
dispatch_committed`. Only after that winning commit may it cross the invocation boundary:

- deterministic core fixes one local invocation ID, requires `at_local_invoke`, activates the token
  for the isolated local-process output path, and performs exactly one `answer_plan` call with no
  transport request, socket, HTTP, TLS, provider, or retry field; or
- end-to-end fixes one transport request/idempotency ID, requires `at_egress`, activates the token for
  authenticated transport ingress, performs at most one socket send, and records every provider
  invocation under the same lease.

The controller retains that lease through the terminal response seal. Burn and the local-invoke/
socket-send boundary are one serialization race: if burn wins, invocation is mechanically refused;
if dispatch wins, burn treats it as potentially executed/delivered and the attempt can never use the
pre-dispatch retry. A stale/expired observation or drift refuses invocation and burns/blocks the slot.
No worker may invoke/send a merely prepared/committed row after losing the gate, and recovery never
invokes/sends a committed dispatch again. A crash at or after the boundary is an ambiguous,
potentially executed/delivered attempt and becomes a typed failure/burn. Only a proven still-`bound`
record with no `dispatch_prepared` may close as `undispatched_token_closed`. Candidate sealing and
transport close both require the exact branch-matching dispatch commitment/state. Phase 4 integration-
tests both local exactly-once and external socket-send boundaries; Task 3 proves only their transition
model and HMAC contracts.

Response ingress is likewise durable before acknowledgement through the one signed
`candidate_ingress_current_state` resource defined in Section 3; no second attempt-store `open/sealed`
buffer or legacy state machine exists. For the bound token/fence, `receiving` carries the exact accepted-
byte count, prefix digest and next offset. Each chunk CAS requires `dispatch_committed`, the exact
dispatch-receipt commitment and branch invocation ID (local invocation for deterministic core,
transport request for end-to-end), authenticates the binding/execution channel, and requires the exact
next offset. A byte-identical replay at an already persisted offset is idempotent; a conflicting replay,
gap or second stream is a consuming protocol violation.

Each chunk transaction jointly checks the independently current ingress generation, binding/token/
fence/active dispatch, appends the exact bytes, advances active/run counters and prefix digest, records
`pending_burn`/tombstone when applicable, and determines acknowledgement eligibility. There is no
counter-only intermediate state. Terminal framing uses the Section 3 subject -> candidate-attempt/burn
source -> intermediate snapshot -> terminal receipt -> final private-control pointer ->
`terminal_consumed` order and one dual CAS; it never writes a separate `sealed` buffer state. No
candidate seal can name bytes or a zero-prefix marker absent from that authenticated state/receipt
lineage. If these fields cannot share the stated transaction, Phase 4 stops; an invented two-phase or
legacy `open -> sealed` protocol is outside this contract.

The same transaction prechecks the per-attempt 1,048,576-byte cap before persistence. A crossing
chunk is never persisted or acknowledged; instead it atomically seals
`protocol_violation/RESPONSE_SIZE_LIMIT`, tombstones the token, and binds the exact accepted-prefix
descriptor/length/SHA-256 plus rejected-chunk length without its bytes/hash. A zero-prefix overflow
forbids a response blob. Replay of the same crossing chunk returns the same terminal receipt and never
changes counters. A crash cannot leave `open`, retain overflow bytes, or seal a different prefix.

Cap precedence is total and deterministic. The transaction checks the per-attempt cap first. If that
cap would be crossed, only the `RESPONSE_SIZE_LIMIT` case seal occurs and the run-total accepted-byte
counter is unchanged. Only a chunk that fits the per-attempt cap is then checked against the run-total
cap and may enter the global pending-burn branch. A chunk that mathematically crosses both therefore
cannot select between outcome and burn.

A chunk that would exceed 67,108,864 cumulative bytes is not persisted or acknowledged; that same
transaction marks `candidate_response_run_budget_exceeded_pending_burn` and tombstones the active
token while preserving the already accepted prefix. No later ingress, dispatch, candidate-set seal,
or truth commit is legal. Recovery may only append the global `consumption_claim_burn` with reason
`candidate_response_run_budget_exceeded`, zero truth/result delta, the exact counter/token-fence
proof, and the required burn-response-buffer snapshot when the prefix is nonempty. The overflow chunk
records only its length, never bytes or content hash. Until that burn is durable the slot remains
blocked, and later bytes go only to quarantine.

Crash recovery resumes only the same durable buffer. If accepted-byte count is positive, recovery
must finish the exact terminal seal or burn the slot with the same snapshot record; it may never
erase/reclassify those bytes as a
zero-byte infrastructure failure or select a new response. For a zero-byte buffer under
`dispatch_committed`, terminal framing is decisive: a durably received HTTP 200 terminal frame with
an empty body, or a parsed response missing/empty required result, seals
`malformed_response/MISSING_RESULT`; no terminal frame by the request deadline seals
`timeout/CANDIDATE_TIMEOUT`; and an authenticated transport failure seals
`runtime_error/CANDIDATE_RUNTIME_ERROR`. Unreconciled state burns the slot. None enters the retry
path. Task 3 schedules these transitions in the pure
model; Phase 4 integration tests crash after the first durable byte and after the terminal frame but
before runner acknowledgement.

Before truth access, every non-infrastructure case attempt is frozen by exactly one custodian-private
`candidate_attempt_sealed` record carrying `candidate_attempt_commitment`. Its secret-backed
projection binds the suite run, opaque invocation
ID, private case fingerprint, case-attempt/candidate-invocation/channel identifiers, response framing
and accepted
bytes or a closed terminal failure marker, terminal state (`completed_response`,
`malformed_response`, `timeout`, `runtime_error`, or `protocol_violation`), start/end times, and the
exact case-attempt-binding commitment and run-binding event. No per-case seal projection enters a
public event or report. The sink tombstones the channel in the same terminal sealing transaction. A
second request, conflicting terminal frame, or changed response observed
before sealing yields `protocol_violation`, preserves all accepted candidate material only in the
private commitment, and consumes that case attempt; any post-seal byte follows the
quarantined-late-byte path below. No branch may select among them. An infrastructure failure eligible
for the sole transfer is the only case-attempt branch without this event; it instead requires the
zero-byte close path below.

Before a `completed_response` seal, the custodian strict-loads the exact buffered bytes and validates
the precommitted selected execution contract and common response-contract ID/version/hash. The
deterministic branch also verifies the request/result fragment and QueryPlan hashes, adapter receipt,
`verified: true`, request echoes, and exactly-one local invocation; the end-to-end branch verifies the
GET/API/transport response binding. An absent, empty, or whitespace-only `answer` takes
precedence and seals `malformed_response/MISSING_RESULT`. A missing required field other than
`answer`, any extra/duplicate/non-string field, a wrong `question_id`/`question` echo, BOM/trailing
data, or another schema violation seals `malformed_response/API_CONTRACT_VIOLATION`. The contract
cannot change between cases or after bytes arrive.

Deterministic-core local terminal mapping is total and precedence-ordered. `deadline_exceeded` maps
only to `timeout/CANDIDATE_TIMEOUT`; `raised` maps only to
`runtime_error/CANDIDATE_EXCEPTION`; `process_terminated` maps only to
`runtime_error/CANDIDATE_PROCESS_TERMINATED`; and `protocol_violation` maps only to
`protocol_violation` with its exact `LOCAL_*` receipt reason or, for a candidate seal, exact
`RESPONSE_SIZE_LIMIT`. `RUN_RESPONSE_BUDGET_EXCEEDED` is instead the explicit no-candidate-seal burn
pairing below. Those four exit classes forbid a
deterministic-core adapter receipt. `returned/NONE` requires exactly one adapter receipt and a complete
terminal output frame. A missing/mismatched receipt, result hash, or result-to-response mapping instead
maps to `protocol_violation/LOCAL_ADAPTER_CONTRACT_VIOLATION`. Otherwise the common validation
precedence above yields `malformed_response/MISSING_RESULT`,
`malformed_response/API_CONTRACT_VIOLATION`, or `completed_response`. No other pairing of local exit
class/reason, adapter receipt, buffer state, and candidate-attempt terminal state is legal.
The sink cap has higher terminal precedence than `returned/NONE`: a per-attempt crossing chunk changes
the local receipt to `protocol_violation/RESPONSE_SIZE_LIMIT`, forbids the adapter receipt, and uses the
exact accepted-prefix/rejected-length candidate-seal branch above; a run-total crossing chunk changes
it to `protocol_violation/RUN_RESPONSE_BUDGET_EXCEEDED`, forbids the adapter receipt/candidate seal, and
binds it in the pending-burn evidence. Overflow bytes are still never stored or hashed. These are the
only sink-driven overrides of the local exit mapping.

After all eligible invocations have exactly one final seal, the runner appends
`candidate_attempt_set_sealed`, but only after the trusted controller has issued the final
`pre_truth_commit` runtime attestation. Its private projection contains the eligible count, complete
ordered runtime-observation hash sequence, and the complete
ordered per-invocation attempt histories, including every case-attempt-binding commitment,
infrastructure/close record, final candidate-attempt commitment, and candidate-invocation/channel
identity.
The public event exposes only eligible count, the set HMAC, and event hash. Validators with the
custodian-private projection require exact denominator equality,
one-to-one coverage, contiguous ordinals, unique IDs, no unsealed/extra invocation, and exact linkage
to the run binding, fingerprint, and runtime lease. This final set event, not any individual response,
is the only candidate object
eligible for truth release.

Immediately before truth access, the runner must win a `truth_release_commit` append/CAS against the
externally supplied current registry head. In that single transaction the registry checks that the
slot is still active for the exact suite, fingerprint, attempt, consuming event, run-binding event,
candidate-attempt-set-sealed event/commitment, complete trusted runtime-observation sequence, every
final case-attempt seal, and output-fence ledger;
appends the private and public
commit records; changes the slot irrevocably to `truth_committed`; increments the applicable
result-bearing budget exactly once; atomically persists the raw release-fence token in an encrypted,
attempt-bound capability-recovery record; binds that record's opaque ID and the token hash in the
commit; and returns the raw token only to the winner. Failure to persist the recovery record aborts
the entire transaction. The
claim/transfer head may be an ancestor rather than the current predecessor, but every bound value
must match the active slot. This CAS, not a non-mutating “immediately before” read, is the linearized
truth-release decision. A concurrent transfer, burn, or competing truth commit can win that
predecessor only once; every loser receives no truth capability.

After the commit, the winner appends exactly one hash-chained `truth_release_authorized` lifecycle
event that binds the `truth_release_commit_history_head_sha256` and release-fence-token SHA-256 but
does not assert delivery. It also binds the opaque recovery-record ID and commitment; the raw
token and encrypted record content remain private. Only after that event is durable may the private
truth store validate the raw token against the same commit, event,
suite/fingerprint/run-attempt/candidate-attempt-set commitment and eligible count, and current-or-descendant
registry chain. The store then performs exactly one atomic terminal transaction. A redeeming winner
creates and durably commits the encrypted truth session for that same sealed response set, changes the
capability to `redeemed_with_durable_truth_session`, tombstones the token and recovery record, and emits its terminal
receipt commitment before making the session readable. A revoking winner creates no truth session,
changes the capability to `revoked_without_delivery`, tombstones the token and recovery record, and emits its terminal
receipt commitment. Redemption and revocation race on the same `available` state; one winner makes
the other fail, and replay returns no truth. Writing a “delivered” receipt before a durable session or
finalizing a null/unterminalized branch is forbidden.
The truth-store terminal CAS reads the authoritative durable clock. Redemption is legal only when its
observed tick is strictly before `effective_truth_terminal_deadline_tick`. At equality or afterward,
only `revoked_without_delivery/truth_terminal_deadline_expired` may win. The terminal receipt binds
the clock instance/epoch, observed tick, all three component deadlines, and their recomputed minimum,
so a redeem-versus-expire race has exactly one valid winner. Clock unavailability never supplies an
observed tick and therefore cannot itself win either terminal branch.

The runner then appends exactly one `truth_capability_terminalized` lifecycle event binding the
authorization-event hash, terminal state, and non-null receipt commitment. Every outcome event must
directly follow this terminal event and reproduce those values. If terminalization succeeded in the
store but this event cannot be persisted, recovery may append only that same event; no outcome,
report, truth replay, or new attempt is permitted first.

Failure to persist the authorization event leaves truth unavailable but does not undo the spent
slot. Recovery may finish only that same authorization event and suite run, retrieving the identical
token from the encrypted recovery record under audited custodian authorization. While the capability
is still `available`, recovery must redeem the one already sealed candidate-attempt set before the
effective deadline when the transaction can succeed and the fresh authority guard is allowed. It may
revoke at/after that deadline only with the typed expiry reason, or strictly before it only with the
authenticated authority-conflict reason; it may not append an outcome or mint a replacement token first.
After redemption, recovery may only resume idempotent deterministic scoring from the already sealed
response set and durable private truth session; it may not human-select a failure branch after seeing
any partial score. After revocation, each
invocation is classified by the exact total mapping below; the custodian may not choose among
multiple aggregate categories. Neither
branch may dispatch or select another case response or terminalize truth again. A crash after the
commit never authorizes retry or replacement.

Before the public `outcome` lifecycle event, the custodian deterministically builds and HMACs the
private `outcome_set_projection` root from the sealed candidate set, terminal truth, ordered outcome-
index/descriptor hashes, and streamed outcome records
capability. The event is the direct successor of `truth_capability_terminalized` and exposes only
eligible count, `outcome_set_commitment`, and its event hash—never per-case verdicts, scores, reasons,
or identifiers. A redeemed session may produce scored pass/fail plus typed malformed/runtime/timeout
case outcomes. A revoked capability produces no scored pass/fail and never creates a scoring lease or
work ledger. A final seal of
`malformed_response/MISSING_RESULT` maps to `malformed_output/MISSING_RESULT`;
`malformed_response/API_CONTRACT_VIOLATION` maps to
`malformed_output/API_CONTRACT_VIOLATION`; every other `malformed_response` maps to
`malformed_output/CANDIDATE_MALFORMED_RESPONSE`;
`protocol_violation` maps to `malformed_output/CANDIDATE_PROTOCOL_VIOLATION`; `timeout` maps to
`timeout/CANDIDATE_TIMEOUT`; and `runtime_error` maps to
`runtime_error/CANDIDATE_RUNTIME_ERROR`. Under deadline revocation, a `completed_response` maps to
`timeout/TRUTH_TERMINAL_DEADLINE_EXPIRED` and the other terminal candidate classes retain the exact
mapping above. Under `authority_conflict_after_truth_commit`, every eligible invocation maps uniformly
to `evaluation_error/AUTHORITY_RESTRICTION` regardless of candidate terminal class; no score or
candidate-class selection is used. No other revocation reason or pairing is valid.
The sealed disposition is `invalidated` regardless of configurable thresholds.

The outcome object has an exhaustive terminal-capability `oneOf`. The redeemed branch requires
`scoring_completion_state` of `complete` or `evaluation_error`. Complete and operational-error
sub-branches require both scoring observations, one non-null `scoring_lease_id`, and the exact work-
ledger/finalization fields above. The authority-error sub-branch uses the finalization receipt's strict
stage: `start` forbids scoring-start/lease/ledger; `finalize` requires the earlier allowed start/lease
and permits only its sealed unusable prefix. Recovery recomputes or resumes the same entries. The
outcome-store CAS accepts either one complete eligible-count set, one deadline/objective-lease
`evaluation_error/SCORING_FINALIZATION_FAILED` set, or one authority-conflict
`evaluation_error/AUTHORITY_RESTRICTION` set; it never accepts a partial prefix plus fabricated
candidate failures. At the same observed tick, an already durable earlier failure wins; otherwise
deadline expiry precedes authority conflict, which precedes a newly observed lease/runtime failure.
The evaluation-error branch forces sealed `invalidated`
and is reported separately from candidate `runtime_error`. The revoked branch requires
`scoring_completion_state: truth_not_delivered`, a runtime-observation sequence ending at
`pre_truth_commit`, null scoring lease/work-ledger/finalization fields, and only the deterministic
terminal-receipt mappings above. Fields from the other branch are forbidden.
The outcome HMAC, private report, and aggregate counters must all derive from the identical ordered
outcome set; a reconciled-looking report with different per-case outcomes is invalid.

Truth-authorization, terminalization, outcome, and report objects reference the exact suite
run-attempt ID, consuming-event hash, run-binding-event hash, candidate-attempt-set-sealed
event/commitment, outcome-set commitment, and immutable eligible count, active
claim/transfer head, inherited retired-token fence-ledger commitment, truth-release-commit head,
token hash, recovery-record ID/commitment, terminal capability state, and non-null terminal receipt
commitment. The raw token is a
custodian capability and never enters an event, report, repository, log, or disclosure.

Case-attempt ordinals are immutable and contiguous from zero per case invocation across all runner
processes under the one immutable deployment manifest. A key/resource rotation stops this design; it
cannot reset an ordinal. A suite-wide counter permits at most one ordinal-1 case attempt across
the complete suite/version. An ordinal-0 infrastructure failure before the truth-release commit may
authorize that sole retry only after the runner durably appends both the typed infrastructure
attestation and `attempt_transport_closed` event while the binding is still pre-dispatch. The close
event contains the HMAC-attested receipt for the exact inactive channel and attempt, null dispatch/
transport IDs, `egress_attempted: false`, output-sink fence epoch/token hash,
`candidate_output_observed: false`, and accepted-byte count zero. The output sink atomically
tombstones the old token before issuing that receipt. Then and only then may
`consumption_claim_transfer` CAS the same active slot, bind both event hashes and the close
receipt, replace only that invocation's attempt with a fresh ordinal-1 ID, and remain active and
suite-local consuming. Previously sealed invocations and their ordering remain immutable. No second
transfer anywhere in the suite exists, and ordinal 2 or greater fails closed. If ordinal 1 cannot
reach `dispatch_committed`, that exact binding remains blocked for recovery; if recovery is abandoned,
`consumption_claim_burn(reason=pre_dispatch_infrastructure_exhausted)` terminally stops the slot.
Once any attempt reaches `dispatch_committed`, a zero-byte timeout/runtime failure is sealed as that
invocation's typed outcome and never authorizes transfer or another suite.

All dispatch/send, accepted output ingress, and registry transfer/burn/truth-commit decisions share
the slot's serialized owner/head/fence state. A byte presented under a tombstoned attempt token is never accepted
as candidate output. The first such byte for a unique
`(output_channel_token_sha256, fence_epoch)` coalescing key makes the custodian-only sink durably
create one content-free receipt and privately CAS-burns a matching active slot through
`consumption_claim_burn`. The receipt/observation emits no distinct or late-specific public object;
the same transaction still appends the mandatory generic public burn attestation and lane
invalidation event. If that late-byte CAS linearizes before truth commit,
the truth commit loses and no truth is delivered; if it arrives after truth commit, the slot is already
consumed and the write-only late bytes remain inaccessible, so they cannot create another run or a
selectable result. Further bytes under the same coalescing key create no new sequence, record, public
count, or ledger entry; after authenticated fence classification they are discarded through the
write-only retention/destruction path. Thus hostile byte flooding cannot make the bounded report
schema or finalization barrier unrepresentable. If transport termination, accepted-byte count, or
sink fencing cannot be proven,
transfer is forbidden: the runner must burn the slot, or leave its current nonterminal
state blocked when the burn cannot be durably persisted. A timeout, runtime error, malformed response,
any accepted response byte, or any completed model output is a sealed case outcome and cannot be
relabeled as infrastructure. Global result-bearing consumption still occurs only once at the later
truth-release commit for the complete sealed set.

The authorization -> capability-terminal -> outcome lifecycle subsequence is contiguous. The late-
byte fact before truth commit is represented only in the HMAC-protected burn append/private sink
record, while the public chain receives only the unconditional generic burn/invalidation objects; a
first late byte after truth commit is durably receipted only in the independent write-only sink. No
late-byte observation interposes a public lifecycle event in that mandatory subsequence or creates a
later conditional public event. Report finalization privately consumes every unique coalesced receipt
already present at its atomic snapshot, while a receipt after publication extends only the private
sink/archive chain and does not invalidate the historical report. The private record reproduces the
first-observation timestamp and token/fence identifiers. Audit evidence is retained without revealing
whether or when the event occurred.

Post-outcome persistence and report finalization each acquire an atomic sink snapshot barrier. The
barrier fixes a monotonic receipt-sequence `output_sink_snapshot_watermark` and corresponding HMAC-chained
`output_sink_ledger_head_commitment`, streams every content-free receipt through that watermark into
the HMAC-protected private append, and updates `bound_sink_state` before new ingress may receive the
next sequence. `post_outcome` binds its private barrier pair; a later report binds an equal-or-newer
private pair and proves every receipt through its watermark is in the private ancestry. Receipts after
publication receive higher sequences and extend only that chain without invalidating the report. A
non-atomic sink query/private snapshot or omitted receipt at or below the bound watermark fails
closed. The number of ledger receipts
is bounded by the finite issued-token inventory because each token/fence pair can contribute at most
one receipt; raw byte volume never advances the watermark.

`attempt_transport_closed` is a type-specific self-state event before the sole pre-dispatch transfer.
Private late-output receipts are legal only for an attempt whose transport token is tombstoned or
whose slot is already truth-committed. `truth_release_authorized` and
`truth_capability_terminalized` are ordered type-specific self-state events on
`checkpoint_consuming` or `consuming`; the former requires the matching prior global truth-release
commit, and the latter requires the matching atomic truth-store terminal receipt.
`exclusion_approval`, run binding, infrastructure attestation, disclosure authorization, and adjudication have
only the expressly named self-state placements in this design. No generic or unregistered
self-transition is valid.

The transfer is legal only for an ordinal-0 binding that never reached dispatch/outbox commit or
network egress. A fingerprint change or custodian abort after claim uses a terminal burn with zero
truth/result delta; it never advances a hidden suite. An ordinal-1 pre-dispatch failure remains
blocked for the same binding's recovery or burns the slot, while a dispatched timeout/runtime error
is sealed into the denominator. If a required burn cannot be persisted, the slot remains blocked and
evaluation stops for custodian recovery; it is never assumed free.

After the truth-release commit, authorization event, and capability-terminal event, every outcome
records `checkpoint_consumed` for locked validation or `consumed` for sealed holdout. There is no
custodian-selected abandoned-run category: the exact terminal-capability mapping or deterministic
scoring-finalization rule supplies the outcome. Pass, fail, malformed output, timeout, runtime error,
and evaluator error all consume the suite. A missing candidate result is normalized before truth
commit to `malformed_output` with reason code `MISSING_RESULT` and consumes the suite.

Every truth-committed outcome must then append its globally durable receipt before any report or
disclosure is created. In one custodian transaction, the runner appends a private history record
binding the truth-release-commit head, active claim/transfer ancestor, suite/version, release cycle,
checkpoint, freeze fingerprint, suite run-attempt ID, candidate-attempt-set event/commitment,
inherited retired-token fence-ledger commitment, exact truth-release-authorization and
truth-capability-terminal event hashes, terminal truth-capability state and required non-null receipt
commitment, exact outcome-event hash and outcome-set commitment, zero additional budget deltas, and historical
`eligibility_history_head_sha256`, plus the atomic output-sink watermark/head pair. The exact
registry current head at transaction start—not necessarily those older ancestors—is the successor's
`prior_attestation_sha256`. The corresponding public `post_outcome` attestation CAS produces
`post_outcome_history_head_sha256`. It records the outcome but neither first consumes the slot nor
increments a disclosure budget. That history record binds the outcome event, never a report, so the
later report hash remains acyclic. Failure of this atomic append blocks reporting and requires
custodian recovery from the already durable truth commit/event; it never authorizes a new run. Every
later suite must reserve this successor (or a later valid descendant) as its eligibility head.
The registry's unique-receipt map rejects a second `post_outcome` for the same truth-commit head even
if an unrelated successor advanced the current head after the first receipt.

A pre-truth burn has no outcome report, but its global history successor and invalidation event remain
durable. The externally supplied chain must show the burned terminal slot, and no later reservation,
claim, retry, truth release, or report may use it.

### 8.5 Commitments and human independence

Non-secret structural artifacts use canonical JSON v1 and SHA-256. Custodian-domain locked/sealed
truth and private-history commitments use HMAC-SHA256 with custodian-held secret material so low-
entropy expected values cannot be dictionary-attacked from a plain public hash. The organizer-cycle
and owner-remediation authorization domains instead use their expressly defined independent owner-
controlled keys; a custodian cannot mint either decision. Each HMAC is lowercase hexadecimal.
`canonical_bytes` below means the exact Canonical JSON v1 UTF-8 bytes from Section 8.4; `||` means
byte concatenation. The frozen domain contracts are:

- `evidence_package_commitment = HMAC-SHA256(K_evidence_package,
  b"FinProof/EvidencePackage/v1\x00" || canonical_bytes(evidence_package_projection))`, where the
  private projection is the exact common-schema `$defs/evidence_package_commitment_projection`.
  Its record descriptor binds the complete schema-valid source/aggregate evidence package, which the
  validator streams and recomputes before HMAC verification;
- `case_set_commitment = HMAC-SHA256(K_case_set,
  b"FinProof/CaseSet/v1\x00" || canonical_bytes(case_set_index_projection))`, where the private
  projection is the exact common-schema `$defs/case_set_index_projection`. It contains only the
  bounded ordered entry-descriptor index/counts/exclusion commitment. Before verifying the HMAC, the
  validator streams every entry and referenced GoldenCase/evidence-package record, recomputes private
  fingerprints/descriptors/evidence-package commitments, and rejects missing, extra, reordered,
  duplicate, or unreferenced content;
- `private_registry_commitment = HMAC-SHA256(K_history,
  b"FinProof/SuiteHistory/v1\x00" || canonical_bytes(history_projection))`, where the private
  projection has exactly `history_registry_id`, `history_genesis_attestation_sha256` (null only for
  genesis), `target_registry_revision`, `attestation_kind`, `prior_attestation_sha256`,
  `prior_private_registry_commitment`, `appended_private_record`, and `resulting_counters`. The
  two prior values are null only for genesis and otherwise equal the immediately preceding public
  attestation hash and `private_registry_commitment`. `resulting_counters` is the complete bounded
  `history_registry_state` projection: exactly state version/current revision, fixed scalar locked and
  current-opportunity/competition-global consumption counts, nullable current organizer-opportunity ID
  (null only at genesis before the first organizer-authorized successor), next case-
  registration ordinal, archive-manifest head/shard/record/byte counters, sealed-disclosure head/count,
  and the closed map of named Sparse-Merkle roots. It contains no slot owner map, retired-token ledger,
  sink coalescing-key set, receipt/report/adjudication/opportunity map, or prior record array; those
  values live behind authenticated index roots and are proven only when touched. It is derived from
  the prior state and append, never caller asserted, and explicitly forbids the current/resulting
  public attestation hash or external CAS head.

  `appended_private_record` is the bounded schema-valid history-transition subject containing the
  exact already persisted `history_transition_source` descriptor/hash, variant metadata, other archive
  descriptor IDs/hashes, the proof-bundle manifest descriptor/hash, scalar
  deltas, and any required private-control record descriptors. It never inlines proofs, actual case/
  evidence packages, candidate bytes, ledgers, outcome arrays, or reports. The reader streams the
  referenced records before this projection is accepted. Construction order is fixed: hash all other
  touched records/proof chunks and their manifest; build the transition subject while forbidding its
  own descriptor and the new archive-manifest/public-attestation heads; hash that subject and add only
  its descriptor to the new archive manifest; compute the new archive-manifest head/resulting state;
  then HMAC this transition subject plus resulting state and build/hash the public attestation. The
  public attestation is not a member of the same manifest it advances. The projection
  explicitly excludes the not-yet-created successor attestation, successor attestation hash, and
  post-CAS current head. Compute this private commitment first, embed it as the public attestation's
  `private_registry_commitment`, compute the public history-attestation HMAC, hash the complete public
  attestation, and only then compare-and-swap the external head from
  `prior_attestation_sha256` to that hash. The next append carries that hash and this private
  commitment as its two prior values;
- `history_attestation = HMAC-SHA256(K_history_attestation,
  b"FinProof/SuiteHistoryAttestation/v1\x00" ||
  canonical_bytes(public_history_projection))`, where the projection is the complete public
  history-attestation object with `attestation.value` removed and includes
  `private_registry_commitment`, global registry ID, the pinned genesis for non-genesis variants, prior head,
  cumulative consumption counters, all variant-specific event/report bindings, and every applicable
  no-overlap/no-derivation assertion;
- `organizer_cycle_authorization_commitment = HMAC-SHA256(K_owner_cycle_authorization,
  b"FinProof/OrganizerCycleAuthorization/v1\x00" ||
  canonical_bytes(organizer_cycle_authorization_projection))`, where the exact projection omits only
  `attestation.value` and binds opportunity ID, registry/genesis, nullable-first
  `prior_organizer_opportunity_id`, the exact ordered pair of distinct candidate-specific release-cycle
  IDs, authority
  method/object ID/organizer-attributable ordinal, `organizer_evidence` key SHA-256, attributable
  official source/channel/date and source-artifact SHA-256, authorization time, owner role/key ID,
  authority-verification method and its method-specific signature/API/archive/message evidence, plus
  the exact `official_remediation_compatibility_review`. The
  key is controlled by the repository owner, never the
  custodian. The artifact and its Canonical JSON SHA-256 are externally pinned before the continuity
  CAS; Phase 4 verifies this HMAC and every available machine-authentication proof before consuming
  the opportunity, or requires the recorded out-of-band human check when such proof does not exist;
- `owner_remediation_authorization_commitment =
  HMAC-SHA256(K_owner_remediation_authorization,
  b"FinProof/OwnerRemediationAuthorization/v1\x00" ||
  canonical_bytes(owner_remediation_authorization_projection))`, where the exact projection is the
  complete strict `$defs/owner_remediation_authorization` with only `attestation.value` removed. It
  binds purpose/action, registry/genesis/opportunity and complete parent/child candidate-cycle
  identities, child-base descriptor/SHA-256 and its exact public-build-basis subprojection, the exact
  current parent `current_report_receipt_ref` and public secret-
  backed commitments, fingerprint, terminal/outcome/scoring/audit trigger projection, owner stable-
  person attestation/non-alias proof/key/tick, and branch-conditional corrected-build subject plus the
  complete change-evidence record descriptor and immutable first-ranked organizer-exception artifact/
  policy/allowed-path basis approved in the public request. It expressly forbids every transient
  `submission_freeze_authority_state`, official-instruction/clock/submission attestation, generation,
  current-read receipt, observed tick and derived freeze state. The activate projection additionally
  binds the exact blind-signer service/image/config/API/ACL/no-log/key-
  resource attestation identities; complete public-decision-request and owner-approval digests, fixed-
  length private-join commitment, the named strict preclaim-basis projection and digest and one-use consumption-receipt
  descriptor/hash. It expressly forbids the blind-signer result/result digest and nested/copied final
  HMAC. Decline forbids the corrected-build/change/freeze branch fields. It forbids raw private report/outcome bytes, plain private-report digest, child truth,
  suppressed detail, the current resolution/global predecessor and every resulting/future head, and
  its own HMAC; the expressly required already durable historical parent report/audit heads remain
  inputs. The independent
  `K_owner_remediation_authorization` key/domain is controlled by the repository owner, non-exportable
  and callable only by `owner_remediation_blind_signer_v1`; it is distinct from
  `K_owner_cycle_authorization`, every custodian/history key, and the curator principal's keys. The
  human sees/signs only the public-safe channel, while the isolated service alone joins the private
  descriptor channel before this formula.
  The resolution CAS consumes this commitment once under the ordinary suite-history/history-
  attestation HMACs; there is no redundant child-activation HMAC domain;
- `disposition_policy_commitment = HMAC-SHA256(K_disposition_policy,
  b"FinProof/EvaluationDispositionPolicy/v1\x00" ||
  canonical_bytes(disposition_policy_projection))`, where the projection is the complete schema-valid
  private disposition-policy object. It contains no self-commitment field. The reserve batch fixes
  the policy ID/version and complete `disposition_policy_hmac_reference` before activation; the Phase 4
  validator verifies the HMAC and mechanically derives the terminal state from the bound outcome set;
- `exclusion_commitment = HMAC-SHA256(K_exclusion,
  b"FinProof/ExclusionSet/v1\x00" || canonical_bytes(exclusion_projection))`, where the private
  projection binds suite ID/version, policy/checkpoint, ordered excluded case fingerprints, stable
  reason codes, applicability, counts, and approval role/time before lock or seal;
- `evaluation_storage_reservation_commitment =
  HMAC-SHA256(K_evaluation_storage_reservation,
  b"FinProof/EvaluationStorageReservation/v1\x00" ||
  canonical_bytes(evaluation_storage_reservation_projection))`, where the custodian-private closed
  projection contains the complete schema-valid `suite_preclaim_basis`, both formula versions, the
  complete schema-valid slot-preparation receipt, private-control plan/receipt, and private-
  history plan/suite-archive receipt, and exact HMAC metadata. Both store receipts require the same
  slot-preparation receipt ID/SHA-256, `slot_preparation_id`, `reserve_batch_subject_sha256`,
  preparation generation, and
  `expected_registry_predecessor_attestation_sha256`. The subject digest equals the preclaim-basis
  value; the receipt ID/SHA, preparation ID, principal attestation, and curation-scope SHA equal the
  complete occupied slot-preparation receipt/row and basis; and the predecessor equals the
  current generation's reserve-batch CAS guard. The projection excludes its own value, every
  future reservation/claim/fingerprint/history head, actual later usage, and every post-CAS
  confirmation. This projection is a transient HMAC message assembled by streaming the five exactly-
  once canonical records; it is not persisted as an additional record and never copies them into a bundle,
  run, outcome, or report. Construction order is exact: from the held clock/authority/current
  predecessors and immutable approvals/child base, build and content-address the head-independent
  schedule; build the scope containing its exact ref without advancing the human head; finalize
  every complete preclaim basis with that scope SHA; compute both reservation plans/hashes and obtain
  provisional allocation IDs without a final receipt; build the combined basis, authority subject/
  state/guard/binding and ordered slot sources; build the human transition and candidate human head from
  the scope plus ordered source-descriptor-list root; sequentially build each row/root/slot receipt;
  only then emit both slot-receipt-bound store receipts, compute every storage HMAC and derive the one
  final candidate slot-preparation current pointer; atomically CAS the old
  human head to the candidate scope head together with the slot-preparation pointer and every prepared
  allocation. The human transition never contains a slot-receipt digest, so this order has no scope/
  receipt fixed point. Only after that atomic scope/preparation winner may the system
  atomically CAS the `reserve_batch`
  plus allocation activation/archive/proofs; predict the paired suite-reservation hash from that new
  head; build the suite manifest/fingerprint; then atomically persist the reservation, manifest,
  fingerprint, and claim according to the two-revision transaction. Every foreign-domain public
  projection binds one complete
  `evaluation_storage_reservation_hmac_reference: $defs/hmac_reference` with domain
  `evaluation-storage-reservation`, scheme `HMAC-SHA256`, registered version `1`, opaque key ID and
  value. The owning transient storage projection retains only the matching `$defs/hmac_metadata` and
  excludes its value. Every prefixed scalar alias is forbidden. Private validators recompute the
  plans/receipt hashes and cross-object equality;
  Phase 4 secret-verifies the HMAC before activation. A public object never carries a plain plan,
  receipt, descriptor-manifest, or storage-usage digest;
- `case_attempt_binding_commitment = HMAC-SHA256(K_case_attempt_binding,
  b"FinProof/CaseAttemptBinding/v1\x00" || canonical_bytes(case_attempt_binding_projection))`, where
  the private projection contains the exact suite/run binding, case ordinal, opaque invocation ID,
  private case fingerprint, case-attempt/candidate-invocation IDs, attempt ordinal, output-channel
  token hash, selected execution kind/contract ID/version/content SHA-256, common response-contract
  SHA-256, static candidate-isolation-profile ID/version/content SHA-256,
  `candidate_build_resource_manifest_sha256`, the lane-conditional complete
  `candidate_cycle_identity`, dispatch policy, private committed
  question ID/text, active claim/transfer head, and, only for ordinal 1, the complete prior-binding/
  infrastructure/transport-close/ledger-successor graph. Its closed execution `oneOf` additionally
  requires either (a) deterministic request-fragment bytes, the complete precommitted canonical
  QueryPlan bytes/hash, callable/adapter/local-IPC identities, accepted result framing, and no-network/
  no-secret policy while forbidding every HTTP/HCX/provider field; or (b) API/origin/TLS/transport,
  redirects/retries disabled, accepted HTTP status/framing, query-log-redaction/no-store/provider-
  retention mode, literal GET `/answer`, and exact ordered canonical query bytes as base64 while
  forbidding plan/callable/local-invocation fields. The immutable attempt store computes this before
  dispatch and rejects duplicate/conflicting invocation ordinals;
- `case_dispatch_receipt_commitment = HMAC-SHA256(K_case_dispatch,
  b"FinProof/CaseDispatchReceipt/v1\x00" || canonical_bytes(case_dispatch_projection))`, where the
  private projection binds the exact dispatch-prepared record descriptor/subject SHA-256, case-
  attempt-binding commitment, request bytes, suite run, the lane-conditional complete
  `candidate_cycle_identity`, `candidate_build_resource_manifest_sha256`,
  invocation/attempt/candidate-invocation IDs, output-channel token hash, unique transport request/
  local-invocation ID as selected by the execution branch, global budget-slot ID, active suite/run
  owner identity, exact expected
  `consumption_claim_head_sha256`, output-sink fence epoch, runner, dispatch sequence, durable dispatch-
  commit timestamp, runtime-lease ID, durable clock identity, and request start/deadline ticks. Its
  closed `oneOf` requires deterministic-core callable/adapter/local-process/IPC identity plus a fresh
  `at_local_invoke` observation and forbids transport/provider fields, or requires end-to-end transport
  request/idempotency/origin/TLS identity plus a fresh `at_egress` observation and forbids local/plan
  fields. It is created by the trusted controller's branch-specific `dispatch_prepared ->
  dispatch_committed` local-invocation or egress transition and is required by every candidate seal or
  dispatched close;
- `candidate_attempt_commitment = HMAC-SHA256(K_candidate_attempt,
  b"FinProof/CandidateAttempt/v1\x00" || canonical_bytes(candidate_attempt_projection))`, where the
  private projection binds suite ID/version, lane/checkpoint/policy, release cycle, the lane-
  conditional complete `candidate_cycle_identity`, freeze-fingerprint SHA-256,
  `candidate_build_resource_manifest_sha256`, suite run-attempt ID, case ordinal/invocation/private
  fingerprint, exact
  case-attempt-binding and dispatch-receipt commitments, immutable candidate-invocation ID, output-
  channel token hash,
  run-binding-event hash, the complete predecessor-independent
  `candidate_ingress_terminal_subject` descriptor/hash (including the observed ingress state and
  attestation digests), exact terminal state/timestamps/framing, durable accepted-byte count and
  response-buffer SHA-256, plus the egress-policy
  identity, selected execution kind/contract/response-contract/static-isolation-profile identities,
  and the complete bounded branch observation projection. Deterministic core requires the exact
  `at_local_invoke` observation and one closed content-free `local_invocation_receipt` containing local
  invocation/process IDs, `call_count: 1`, invocation ordinal, exact input SHA-256, start/end ticks,
  exit class (`returned`, `raised`, `deadline_exceeded`, `process_terminated`, or
  `protocol_violation`), conditionally exact exit reason (`NONE`, `CANDIDATE_EXCEPTION`,
  `CANDIDATE_PROCESS_TERMINATED`, `CANDIDATE_TIMEOUT`, `LOCAL_VERIFICATION_FALSE`,
  `LOCAL_ADAPTER_CONTRACT_VIOLATION`, `LOCAL_DUPLICATE_INVOCATION`,
  `LOCAL_OUTPUT_PROTOCOL_VIOLATION`, `RESPONSE_SIZE_LIMIT`, or
  `RUN_RESPONSE_BUDGET_EXCEEDED`), and terminal output-buffer count/hash/close/tombstone state, with no
  payload. Its `returned/NONE` branch requires the exact deterministic-core adapter receipt; every
  other exit branch forbids that receipt. It also requires an empty/forbidden provider-observation
  array. End-to-end requires the exact
  `at_egress` observation and complete
  sequence-ordered `provider_invocation` observation hashes/objects for that attempt. Its terminal-
  state `oneOf` is closed. A positive accepted-byte count
  requires the exact unique private response-blob ID/length/SHA-256; zero bytes require a typed no-
  response marker and forbid a blob. `protocol_violation/RESPONSE_SIZE_LIMIT` additionally requires a
  positive `rejected_chunk_length`, forbids rejected bytes/hash, and permits either a positive prefix
  blob or the zero-prefix marker. Every other branch forbids `rejected_chunk_length`. It remains
  custodian-private. The projection expressly forbids every intermediate/final private-control
  pointer, terminal ingress state/attestation and terminal receipt; those later objects prove the
  acyclic atomic consumption of this exact subject;
- `candidate_attempt_set_commitment = HMAC-SHA256(K_candidate_attempt_set,
  b"FinProof/CandidateAttemptSet/v1\x00" || canonical_bytes(candidate_attempt_set_projection))`,
  where the private projection binds suite/run/fingerprint/policy/checkpoint, the lane-conditional
  complete `candidate_cycle_identity`,
  disposition-policy ID/version/commitment, scorer/rule, selected execution kind/contract ID/version/
  content SHA-256, common response-contract SHA-256, static candidate-isolation-profile ID/version/
  content SHA-256, `candidate_build_resource_manifest_sha256`, and branch egress-policy identities,
  eligible count,
  run-binding event/commitment, the continuously held `runtime_lease_id`, the complete contiguous
  branch-valid runtime-observation hash sequence ending in `pre_truth_commit`, exact
  `retry_ledger_count: 0|1`, exact `suite_retry_used == (retry_ledger_count == 1)`, and the complete case-
  ordinal-ordered invocation histories. The count is recomputed from the one legal transfer/retry edge
  across all histories; an ordinal-1 attempt without that edge, a second retry or a mismatched boolean
  is invalid. It also streams the ingress witness's exact terminal-receipt
  accumulator and requires one receipt/source/subject match for every dispatched terminal attempt with
  no extra, gap or reordered receipt. The deterministic branch requires exactly one
  `at_local_invoke` per dispatched attempt and zero `at_egress`/provider observations; the end-to-end
  branch requires each `at_egress` plus every provider observation. Each
  history contains every case-attempt-binding commitment, any infrastructure/transport-close/transfer
  graph, every dispatch-receipt commitment, exactly one final candidate-attempt commitment, and final
  candidate-invocation/channel identity.
  The public set event contains only eligible count, this HMAC, and its event hash;
- `infrastructure_attestation = HMAC-SHA256(K_infrastructure,
  b"FinProof/InfrastructureFailure/v1\x00" || canonical_bytes(infrastructure_projection))`, where
  the projection binds suite ID/version, consuming-event and run-binding-event hashes, candidate
  fingerprint, failure class, unique suite run-attempt ID, case invocation/attempt ID and ordinal,
  case-attempt-binding and nullable dispatch-receipt commitments, active consumption-claim/transfer head,
  runner identity, start/failure timestamps, `truth_released: false`,
  `candidate_output_observed: false`, zero materialized response bytes, request-dispatch state, and
  proof that no truth read or decryption occurred. Its closed `failure_stage` is either
  `pre_dispatch`, requiring null dispatch/transport IDs, `egress_attempted: false`, and an inactive
  token, or `post_dispatch`, requiring the exact dispatch receipt/transport ID and
  `egress_attempted: true`. Only the ordinal-0 `pre_dispatch` variant can authorize transfer;
- `attempt_transport_close_commitment = HMAC-SHA256(K_attempt_transport_close,
  b"FinProof/AttemptTransportClose/v1\x00" ||
  canonical_bytes(attempt_transport_close_projection))`, where the
  projection binds suite ID/version, global slot and active claim/transfer head, candidate
  fingerprint, exact suite run-attempt ID, case invocation/attempt ID and ordinal, runner identity,
  candidate-invocation/channel IDs, case-attempt-binding commitment, and nullable dispatch-receipt
  commitment,
  output-sink fence epoch and tombstoned token hash, close timestamp, accepted response-byte count
  zero, and `candidate_output_observed: false`. Its closed `close_kind` is either
  `dispatched_infrastructure_closed`, which additionally requires the transport request ID,
  cancellation/termination acknowledgement, and infrastructure-attestation event hash, or
  `undispatched_token_closed`, which requires `request_dispatch_state: not_dispatched`, null transport
  request and infrastructure-event fields, and an atomic proof that no dispatch or ingress won before
  tombstoning. Only `undispatched_token_closed` for ordinal 0 can authorize transfer, and only while
  the serialized sink ledger still shows no late byte. The dispatched variant is audit evidence for
  a typed candidate failure and can never authorize retry;
- `late_output_receipt_commitment = HMAC-SHA256(K_late_output,
  b"FinProof/LateOutputReceipt/v1\x00" || canonical_bytes(late_output_projection))`, where the
  custodian-private projection binds registry/slot, suite run, causative retired-or-current token
  SHA-256, fence epoch, literal coalescing-key version `1`, positive monotonic receipt sequence,
  first-observation timestamp, and literal `late_byte_observed: true`. It has no previous-receipt field;
  ordering is authenticated only by the sink-ledger accumulator's prior head. It explicitly forbids
  payload, content hash, byte length, per-case
  terminal state, or any derived content field. Public history/burn objects carry no sink-ledger head,
  receipt HMAC/count, watermark, late-byte boolean, or conditional private-state marker; only each
  unrelated successor's ordinary transition-specific private-registry commitment privately binds the
  sink state. The producer atomically creates at most one receipt for each
  `(token_sha256, fence_epoch)` pair; repeat bytes for that pair never change this projection;
- `output_sink_ledger_head_commitment = HMAC-SHA256(K_output_sink_ledger,
  b"FinProof/OutputSinkLedger/v1\x00" || canonical_bytes(output_sink_ledger_step_projection))`.
  The empty head uses exactly `{ledger_version, history_registry_id, global_budget_slot_id,
  watermark: 0, prior_head: null, receipt: null}`. Every nonempty step has those first three fields,
  exact positive `watermark`, non-null prior head, and exactly one receipt tuple
  `(receipt_sequence, token_sha256, fence_epoch, late_output_receipt_commitment)` whose sequence equals
  the watermark; no array exists in the step projection. Starting from the empty head, the producer
  folds receipts in sequence and a checkpoint binds the prior/final head plus delta descriptor range.
  It rejects gaps, duplicates, reorder/omission, a duplicate coalescing key, or another-slot receipt;
  raw payload metadata and repeat-byte counts are never inputs. At most 10,001 steps exist. Reaching
  the policy bound blocks new evaluation ingress but never prevents a barrier/report over the valid
  accumulator;
- `retired_token_fence_ledger_commitment = HMAC-SHA256(K_retired_token_ledger,
  b"FinProof/RetiredTokenFenceLedger/v1\x00" ||
  canonical_bytes(retired_token_fence_ledger_projection))`, where the projection is exactly the
  version `1.0.0` object defined in Section 8.2. The producer validates the complete prior projection,
  appends at most the one transition-authorized next entry, checks contiguous sequence and exact
  tombstone/close-receipt bindings, computes the new HMAC, and only then includes it in the same
  registry CAS. The empty-ledger value is the HMAC of that exact slot-bound projection with
  `entries: []`; it is not an all-zero or null sentinel. Every public object carrying the commitment
  also carries scheme `HMAC-SHA256`, commitment version `1`, and an opaque
  `retired_token_fence_ledger_key_id`. The run binding, transfer, burn, truth commit, outcome, and
  report must reproduce the applicable commitment, metadata, and slot ID byte-for-byte. Pure
  validators check structure, append/inheritance, and cross-object equality without claiming secret
  authentication; the Phase 4 custodian independently rebuilds the projection and verifies this HMAC
  before accepting a successor;
- `suite_commitment = HMAC-SHA256(K_suite,
  b"FinProof/Suite/v1\x00" || canonical_bytes(suite_projection))`, where the projection is the
  complete schema-valid public suite manifest with `suite_commitment` removed and therefore binds
  suite ID/version, lane, checkpoint, policy version, the lane-conditional complete
  `candidate_cycle_identity`, counts/applicability, disclosure class,
  case-set commitment, exclusion commitment, disposition-policy ID/version/commitment and HMAC
  metadata, selected execution kind/contract ID/version/content SHA-256, common response-contract SHA-
  256, static candidate-isolation-profile ID/version/content SHA-256,
  `candidate_build_resource_manifest_sha256`, `history_registry_id`,
  `history_genesis_attestation_sha256`, `eligibility_history_head_sha256`, and role/key IDs;
- `run_binding_attestation = HMAC-SHA256(K_run,
  b"FinProof/RunBinding/v1\x00" || canonical_bytes(run_projection))`, where the projection binds
  suite ID/version, release-cycle ID, the lane-conditional complete `candidate_cycle_identity`, lane,
  checkpoint, policy version, suite/history commitments,
  the exact freeze-fingerprint SHA-256, a custodian-generated 128-bit lowercase-hex
  suite `run_attempt_id`, immutable eligible count, ordered private
  `(case_ordinal, case_invocation_id, private_case_fingerprint)` map,
  `case_dispatch_order: case_ordinal_ascending`, `max_in_flight_case_requests: 1`, global budget-slot
  ID, disposition-policy ID/version/commitment and HMAC metadata, active
  `consumption_claim_head_sha256`, complete retired-token fence-ledger commitment, and the
  winning `consuming_event_sha256`, runtime-lease ID, and initial trusted `run_start` runtime-
  observation hash, exact scorer/rule, selected execution kind/contract ID/version/content SHA-256,
  common response-contract SHA-256, static candidate-isolation-profile ID/version/content SHA-256,
  `candidate_build_resource_manifest_sha256`, and branch egress-policy identities, timeout durations,
  clock authority identity, the same five reservation
  record descriptor IDs/lengths/SHAs,
  current private allowances, and the recomputed `evaluation_storage_reservation_commitment` plus
  exact HMAC metadata; the pinned private-control pointer resource/genesis/store/allocation IDs and
  exact initial generation-zero/sequence-zero/snapshot SHA-256 plus opaque current-state-attestation
  digest, immutable store-monotonic epoch, attestation scheme, and opaque key ID; the matching
  generation-zero candidate-ingress resource/genesis/store/allocation IDs, empty-state canonical SHA-
  256, complete initial attestation digest, zero receipt head/count, store-monotonic epoch, scheme and
  key ID; and suite start/
  deadline ticks before the truth-release commit. Every later private
  successor preserves the pointer resource/genesis identities and accepts only the monotonic CAS
  transition defined above.
  Its execution `oneOf` requires deterministic callable/adapter/request-result fragment/QueryPlan/
  local-process/no-network identities and forbids every HCX/API/provider field, or requires the exact
  HCX/prompt/API/origin/TLS/transport/provider-retention identities and forbids callable/plan/local-
  invocation fields.
  Attempt-specific request/channel
  identities exist only in the separately HMAC-bound case-attempt records;
- `runtime_observation_attestation_commitment = HMAC-SHA256(K_runtime_observation,
  b"FinProof/RuntimeObservation/v1\x00" || canonical_bytes(runtime_observation_projection))`, where
  the exact projection is the complete schema-valid runtime-attestation object with only
  `attestation.value` removed. The key belongs to the trusted deployment/egress controller and is
  distinct from custodian/history keys. The projection binds observation kind/sequence, lease/time
  bounds, runtime-lease ID, nullable/required-by-kind scoring-lease ID, fingerprint hash, every
  observed local/provider identity, transport/logging profiles, and attestor/key metadata;
- AEAD encryption uses the closed purpose registry, not an untyped caller key. The private strict
  `$defs/aead_nonce_registry_state` has exactly registry/genesis IDs, contiguous global sequence and
  claim count, an immutable receipt-chain head, authenticated Sparse-Merkle roots for the unique
  `(aead_key_resource_attestation_sha256, nonce_hex)` and
  `(nonce_registry_genesis_sha256, suite_id, suite_version, run_attempt_id, aead_key_purpose)` key
  spaces, and no current-pointer/public-head/signature field. Genesis has sequence/count zero, the
  domain-separated empty roots and null receipt-chain head. Each occupied leaf value contains exact
  preparation/claim/target-record identities, key purpose/resource, suite/run and claim sequence; it
  is immutable and never contains the writer's resulting current-pointer/head.

  `$defs/aead_nonce_claim_receipt` has exactly receipt version, nonce-registry ID/genesis SHA-256,
  suite ID/version and run-attempt ID, preparation ID, nonce-claim ID and contiguous global sequence,
  `aead_key_purpose`, opaque `aead_key_id`, immutable key-resource-attestation SHA-256, 96-bit lowercase-
  hex `nonce_hex`, target record ID, authoritative clock instance/epoch/tick, complete predecessor and
  resulting registry-state digests/roots/counts, prior receipt-chain head, resulting receipt-chain
  head, and descriptor-bound old-root nonmembership/new-root membership proofs for both unique keys.
  The predecessor-independent entry projection excludes both the resulting receipt-chain head and
  `resulting_registry_state_sha256`;
  `resulting_receipt_chain_head = SHA256(b"FinProof/AeadNonceClaim/v1\x00" ||
  canonical_bytes(entry_projection))`. The resulting state is then built from that head, both new roots
  and new count/sequence; its complete digest is inserted into the final receipt. Only after the entry/
  head, resulting state/digest, complete receipt/proofs are fixed is the candidate
  `aead_nonce_registry` current-pointer attestation constructed. Including either derived field in the
  head preimage or placing the candidate pointer in any state/receipt/proof is invalid.

  Governance pins one KMS-attested global nonce-registry resource/genesis/current-pointer lineage for
  all registered AEAD resources. The common coherent current-registry witness independently supplies
  its actual current state/pointer plus a bounded `AeadNonceRegistryReader` for state, receipt and proof
  bytes. A claim transaction accepts the entry only when both nonmembership proofs terminate at that
  observed current state, then atomically persists receipt/leaves/state and compare-and-swaps the
  candidate pointer last. Reports/control bundles validate every referenced receipt as an immutable
  member/ancestor of the independently read current nonce state, not merely as a self-consistent local
  chain prefix. Each immutable key-resource attestation maps to this one lineage; alternate registry/
  genesis, reset/fork/rollback, stale-prefix claim, deletion, or purpose/key/nonce/target substitution
  is invalid. Key rotation/revocation stops every later non-open action in this design. Only a new
  separately owner-approved frozen design/manifest may add a genuinely new attested resource; old
  occupied nonce leaves remain immutable audit evidence and never authorize continuation here.
  Phase 4 KMS attestation proves the two AEAD resources are distinct from each other and every HMAC
  resource; comparing opaque aliases alone is insufficient.

  Recovery encryption has no separately durable prepared state. One truth-commit transaction acquires
  and rechecks the coherent five-resource current-registry snapshot/global-slot/sink guard, nonce-
  registry state/pointer, current private-
  control pointer/attestation, and remaining allowance. With those predecessor states locked, it
  derives the nonce entry/resulting nonce state and complete receipt/proofs; builds the predecessor-independent
  recovery AAD; encrypts; builds the ciphertext descriptor and complete recovery record/HMAC; and then
  builds the descriptor snapshot suffix and resulting private-control pointer attestation last. None
  of the nonce/AAD/recovery/snapshot payload projections contains the resulting global head, resulting
  pointer attestation, or future truth-release event. The HMAC-protected `truth_release_commit` private-
  history append then binds the exact global predecessor, expected and resulting private-control
  pointer attestations, allowance decrement, nonce receipt/record/ciphertext descriptors, and the
  candidate-set/claim/capability inputs; only after that append is fixed is the public resulting global
  attestation/head computed. One all-or-none CAS persists the nonce entry/receipt/proofs/state and
  candidate nonce-current pointer, recovery record/blob,
  private-control snapshots/pointer/allowance, capability row, and private/public history successor.
  A stale pre-lock observation writes nothing. An ambiguous crash must resolve the authoritative
  transaction status before returning existing bytes or retrying; partial objects, an orphan snapshot,
  or a fresh nonce while status is unresolved are invalid. A backend unable to hold this transaction
  across nonce-registry, ciphertext/control-record, private-control snapshot/pointer/allowance,
  capability, private-history, sink barrier, and global-head stores fails the Phase 4 gate.

  Truth-session encryption likewise has no separately durable prepared state. One terminal transaction
  read-locks and rechecks the coherent current nonce state/pointer, authoritative clock/capability,
  fresh `truth_session_redeem` authority subject/state/guard plus
  the exact current private-control
  pointer and allowance. Only when `available`, strictly before the effective deadline and authority-
  allowed does it use
  this acyclic construction order: rederive the canonical truth-payload record bytes/descriptor from
  the precommitted case-set; derive the nonce-claim entry/resulting head and complete receipt/
  descriptor; build AAD from predecessor-independent session fields, those payload/nonce descriptors,
  and the predetermined ciphertext blob ID; encrypt; derive the ciphertext descriptor; build/hash the
  complete session; build the terminal projection/HMAC against the read-locked predecessor pointer;
  then build descriptor batches/snapshots and the resulting pointer attestation last. One all-or-none
  CAS persists the truth-payload record, nonce entry/receipt record, ciphertext blob, session record,
  terminal-receipt record, snapshot suffix and allowance decrement; advances the private-control
  pointer; atomically advances the nonce state/current pointer; tombstones the raw token/recovery
  record; and changes the capability to redeemed. The
  truth-payload record is forbidden in every pre-redemption bundle prefix. At equality or later, the
  deadline revocation transaction wins regardless of a simultaneous authority conflict. Strictly
  before the deadline, a guard decision `authority_conflict` instead selects the authority revocation
  branch; otherwise revocation is invalid. The selected revocation transaction derives its revoked terminal projection/HMAC against the same
  read-locked predecessor, persists only the revoked terminal-receipt record plus its descriptor
  snapshot/allowance decrement/resulting pointer, tombstones the raw token/recovery record, and changes
  the capability to revoked. It forbids a truth-payload record, nonce claim/receipt, ciphertext, or
  session. Both revoked reasons bind the complete authority object; the authority-conflict reason
  additionally requires its byte-identical conflict selector, while deadline expiry does not treat a
  guard conflict as the cause. Its resulting pointer is also derived last. A losing/stale transaction writes nothing. A
  crash is all-or-none: authoritative transaction-status proof of commit recovers exactly the already
  committed complete branch; proof of abort permits a fresh transaction with no prior branch objects;
  unresolved status blocks and never permits another nonce/terminal attempt. The payload/AAD/session/terminal
  projections forbid any resulting snapshot/pointer attestation, terminal event, or future global
  head; only the terminal projection binds the exact read-locked predecessor pointer. A backend unable
  to make nonce-registry/private-control/ciphertext/session/capability persistence one transaction
  fails the Phase 4 gate;
- `truth_release_fence_recovery_record_commitment = HMAC-SHA256(K_recovery_record,
  b"FinProof/TruthReleaseFenceRecoveryRecord/v1\x00" ||
  canonical_bytes(recovery_record_projection))`. The exact projection binds record version, opaque
  record ID, registry/genesis, suite/version, global slot, run attempt, claim/transfer and run-binding
  heads, candidate-attempt-set event/commitment and eligible count, retired-token-ledger commitment,
  token SHA-256, created-at timestamp, literal `aead_key_purpose: recovery_record_aead`, AEAD scheme
  `AES-256-GCM`, opaque AEAD key ID, immutable key-resource-attestation SHA-256, unique 96-bit nonce,
  exact nonce-claim receipt record descriptor plus preparation/claim IDs, and the exact
  `recovery_record_ciphertext` blob descriptor whose byte length is 48 and SHA-256 equals
  `ciphertext_and_tag_sha256`.

  The named `recovery_record_aad_projection` has exactly `record_version`, `record_id`,
  `history_registry_id`, `history_genesis_attestation_sha256`, `suite_id`, `suite_version`,
  `global_budget_slot_id`, `run_attempt_id`, `consumption_claim_head_sha256`,
  `run_binding_event_sha256`, `candidate_attempt_set_event_sha256`, complete
  `candidate_attempt_set_hmac_reference`, `eligible_count`, complete
  `retired_token_fence_ledger_hmac_reference`,
  `release_fence_token_sha256`, `created_at`, `aead_key_purpose`, `aead_scheme`, `aead_key_id`,
  `aead_key_resource_attestation_sha256`, `nonce_hex`, `aead_preparation_id`, `nonce_claim_id`, the
  complete nonce-claim receipt record descriptor, and the predetermined ciphertext blob ID. The
  receipt must resolve to the complete schema-valid claim and match every duplicated field. The AAD
  additionally requires `nonce_claim_receipt.target_record_id == recovery_record_projection.record_id`.
  The AAD
  intentionally omits the ciphertext descriptor length/hash, which do not exist until encryption.
  The ciphertext is authenticated encryption of the exact 32-byte raw token with these canonical AAD
  bytes. The outer record contains the same AAD fields plus the complete ciphertext descriptor/digest.
  Both projections exclude the immediate target revision/prior head, future truth-release-commit
  head/public attestation, and their own HMAC solely to keep construction acyclic. Before the history
  CAS advances, the custodian verifies the pinned nonce-registry lineage/unique claim, durable
  ciphertext, successful authenticated decryption, and recovered-token hash. A stale observation
  before the authoritative lock creates nothing and restarts with a fresh transaction/preparation/
  nonce. After an ambiguous crash, recovery first queries authoritative transaction status: only
  proof that this exact all-or-none transaction and history head committed may return the existing
  bytes; proof of abort means no nonce/ciphertext exists and permits a fresh transaction. An unresolved
  status blocks. Task 3 synthetic tests freeze the projection/
  HMAC and mutation failures; real AEAD/KMS durability and atomic integration are Phase 4 gates;
- `truth_capability_terminal_receipt_commitment = HMAC-SHA256(K_truth_capability_terminal,
  b"FinProof/TruthCapabilityTerminalReceipt/v1\x00" ||
  canonical_bytes(truth_capability_terminal_projection))`, where the custodian-private projection
  binds suite ID/version, release cycle, checkpoint, truth-release-commit head,
  release-fence-token SHA-256, opaque recovery-record ID/commitment, suite run-attempt ID,
  candidate-attempt-set-event hash/commitment and eligible count, lifecycle authorization-event hash,
  terminal transaction timestamp, durable clock instance/epoch, observed tick, applicable persisted
  component deadlines, recomputed `effective_truth_terminal_deadline_tick`, exact
  `expected_private_control_pointer` with resource/genesis/CAS generation/snapshot sequence/current-
  snapshot SHA-256/current-state-attestation SHA-256, the complete byte-identical
  `irreversible_action_authority_binding` for `truth_session_redeem`, and exactly one
  terminal variant. `redeemed_with_durable_truth_session` requires the complete non-self-referential
  `truth_session_record_projection` and its SHA-256 and forbids revocation fields including
  `revoked_publication_not_before_tick`. That projection has
  exactly record version, opaque session ID, registry/genesis, truth-release-commit head, suite/
  release-cycle/checkpoint/slot/run IDs, claim/run-binding heads, freeze fingerprint,
  candidate-attempt-set event/commitment and eligible count, case-set/evidence-package commitments,
  disposition-policy and scorer/rule identities, the complete truth-payload record descriptor and
  `truth_payload_sha256` equal to that descriptor's SHA-256, created-at tick, literal
  `aead_key_purpose: truth_session_aead`, AEAD scheme `AES-256-GCM`, opaque AEAD key ID, immutable
  key-resource-attestation SHA-256, unique 96-bit lowercase-hex nonce, exact nonce-claim receipt
  record descriptor plus preparation/claim IDs, and the exact `truth_session_ciphertext` blob
  descriptor whose SHA-256 equals `ciphertext_and_tag_sha256` and whose length is at most 16,777,232.

  The named `truth_session_aad_projection` is that closed list without the complete ciphertext
  descriptor/digest or any HMAC/SHA value over the complete session record, but with the predetermined
  ciphertext blob ID. It includes and resolves the nonce-claim receipt and truth-payload record
  descriptors, which must match every duplicated purpose/key/nonce/preparation/payload field. The
  nonce-claim receipt additionally requires
  `target_record_id == truth_session_record_projection.session_id`. The
  ciphertext is authenticated encryption of the exact Canonical JSON v1 truth-payload record bytes
  under those AAD bytes; redemption decrypts, byte-compares, hashes, and fully re-derives that record
  from the precommitted case-set entries before committing. `truth_session_record_sha256` is SHA-256
  over the complete record projection including the ciphertext descriptor/digest and is not a field
  inside that projection. The terminal-receipt HMAC includes the complete projection and this digest,
  so a session ID/digest alone is insufficient and no separate unauthenticated commitment is accepted.
  `revoked_without_delivery` requires `revoked_publication_not_before_tick` equal to the selected
  private scope-schedule entry's `report_closure_deadline_tick`, forbids every truth-session/payload/
  nonce/ciphertext field and proves that
  no session was created. Its strict reason `oneOf` is
  `truth_terminal_deadline_expired`, which requires observed tick >= the recomputed minimum of the
  persisted component deadlines, or `authority_conflict_after_truth_commit`, which requires observed
  tick strictly before that minimum and a byte-identical binding whose state/guard decision and safe-
  terminal selector equal that authority-conflict reason. At/after the deadline the expiry branch has
  precedence even if a prohibition is also current. Store-health/custodian-selected or any third reason
  is invalid. Both variants produce a non-null HMAC
  commitment and omit the raw token;
- `outcome_set_commitment = HMAC-SHA256(K_outcome_set,
  b"FinProof/OutcomeSet/v1\x00" || canonical_bytes(outcome_set_projection))`, where the
  custodian-private projection binds suite/run/fingerprint/policy/checkpoint, the lane-conditional
  complete `candidate_cycle_identity`, disposition-policy
  ID/version/commitment, the exact candidate-set
  event/commitment, truth-release-commit head, capability-terminal state/receipt, branch-conditional
  private `revoked_publication_not_before_tick`, eligible count,
  the same five reservation record descriptor IDs/lengths/SHAs, final used/remaining allowances, and
  the recomputed `evaluation_storage_reservation_commitment` plus exact HMAC metadata,
  and
  a terminal-capability-discriminated runtime/scoring projection, exact precommitted scorer
  ID/version/artifact hash and rule-manifest hash, selected execution kind/contract ID/version/content
  SHA-256, common response-contract SHA-256, static candidate-isolation-profile ID/version/content SHA-
  256, `candidate_build_resource_manifest_sha256`, branch-specific callable/adapter or HCX/API
  identity, and
  exact outcome-index record ID/SHA-256, ordered descriptor-list SHA-256,
  `outcome_set_content_sha256`, and derived aggregate counters. The indexed outcome entries—not this
  root—bind each private case fingerprint, final case-attempt/binding/candidate commitments, terminal
  codes, scorer/rule versions, score components, and bounded claim/evidence references. The redeemed
  scoring projection is a strict four-way `oneOf`: (a) `complete` requires allowed scoring-start and
  outcome-finalize bindings, both observations, non-null equal lease, complete ledger and one derived
  outcome per eligible invocation; (b) `objective_evaluation_error` requires both observations/non-null
  lease, authenticated deadline/lease/runtime failure and optional sealed prefix; (c)
  `authority_restriction_start` requires only the start-denied finalization observation, null start/
  lease/ledger and its `scoring_start` conflict binding; or (d) `authority_restriction_finalize`
  requires prior allowed start/non-null lease, finalization conflict binding and its sealed unusable
  prefix. Each error branch deterministically binds only its full eligible-count uniform error mapping,
  never a prefix score. A revoked branch ends observations at `pre_truth_commit`, requires the not-
  before tick byte-equal to the terminal receipt/private schedule entry, requires null scoring fields,
  and binds only the deterministic terminal-receipt mapping. Every redeemed branch forbids the not-
  before field. The
  public outcome event exposes only eligible count, this HMAC, and event hash;
- `corrected_outcome_set_commitment = HMAC-SHA256(K_corrected_outcome_set,
  b"FinProof/CorrectedOutcomeSet/v1\x00" || canonical_bytes(corrected_outcome_set_projection))`,
  where the projection contains corrected outcome-index record ID/SHA-256, corrected ordered-
  descriptor-list SHA-256, corrected content SHA-256/counters, plus original outcome-set commitment,
  current report revision/hash, adjudication event/decision/evidence, exact correction-derivation
  record/content hashes, exact correction-disclosure-delta record/hash and K5-safe verdict,
  correction reason, and intended next revision. It never embeds the corrected
  outcome entries. It is computed before
  `post_adjudication`, included in that HMAC-protected private append, reproduced by the corrected
  private report, and receipted by `corrected_report_recorded`; it never alters the original event or
  post-outcome receipt;
- `private_report_commitment = HMAC-SHA256(K_private_report,
  b"FinProof/PrivateEvaluationReport/v1\x00" || canonical_bytes(private_report))`, where
  `private_report` is the complete schema-valid `custodian_private` report including its canonical
  hash and report attestation and, by schema, contains no `private_report_commitment`; and
- `canonical_report_sha256_bytes := bytes.fromhex(canonical_report_sha256)` after first requiring the
  input be exactly 64 lowercase hexadecimal characters and the result exactly 32 bytes; and
  `report_attestation = HMAC-SHA256(K_report,
  b"FinProof/EvaluationReport/v1\x00" || canonical_report_sha256_bytes)`.

Every cross-object HMAC occurrence named above uses the complete common `$defs/hmac_reference`, or the
explicit collection `$defs/hmac_metadata`; an owning domain object uses its exact domain-specific
schema fields and never an ad hoc subset. Validators compare the normalized value/domain/scheme/
version/key-ID tuple byte-for-byte. The objects never carry key bytes.
Every domain uses an independent uniformly random key of at least 256 bits; a key ID may not cross
domains. A custodian/key-resource change, compromise, revocation or required rotation stops every
later non-open action under this immutable deployment trust manifest and requires a new owner-approved
frozen design; no live re-HMAC/key successor is legal in this history. The secret, private projection, truth payload, and private
registry never enter the repository or normal CI artifacts.
Secret verification decodes an exact lowercase 64-hex value and uses constant-time comparison (for
Python, `hmac.compare_digest`) after recomputing the domain message; ordinary string equality is
forbidden in the Phase 4 runner.

The schema-backed control-plane validator checks domain IDs, projection-field completeness, and that
the same opaque commitments/metadata are bound consistently across manifest, history attestation,
fingerprint, events, and report; it cannot and must not receive the keys or recompute secret HMACs.
Secret-backed verification belongs to the Phase 4 custodian runner. Contract tests use synthetic
keys and private fixtures to verify every formula and reject cross-domain replay, lane/checkpoint
swaps, policy-version swaps, suite mix-and-match, forged private fingerprints/evidence commitment,
run-attempt/candidate-invocation replay, candidate-response selection or commitment substitution,
global
slot/claim substitution, fingerprint substitution, exclusion mutation,
history-assertion mutation, private/public report divergence, forged or output-observed pre-truth
infrastructure retry, forged transport-close receipt, live/late old-token output, release-fence-token
or recovery-record substitution, retired-token-ledger mutation, and truth-payload mutation.

The owner has confirmed that one independent human can serve as curator/reviewer/custodian. That
person:

- does not implement the system under test;
- remains blind to model-under-test output during truth creation and approval;
- works only from official source evidence and an independently executable deterministic reference
  query/evidence package;
- records a pseudonymous role ID rather than personal details in repository artifacts;
- precommits selection quotas and applicability before execution;
- preserves append-only revision history; and
- cannot delete or rewrite a case after seeing a result.

The policy and manifest freeze `independence_model: single_human_combined`. The curator, reviewer,
and custodian fields may intentionally carry the same pseudonymous role ID; validators must not
invent a three-distinct-humans requirement. Independence means that this combined human is distinct
from every implementer/model-output observer during truth creation, while the deterministic
evidence-package/derivation check supplies the mandatory second verification mechanism.

The pseudonymous role ID cannot reset human blindness. The strict private
`$defs/human_stable_identity_attestation` contains exactly version, deployment-pinned identity-
authority resource/genesis, attestation ID, one authority-stable private subject ID, role class
`curation_principal` or `repository_owner`, deployment-pinned trusted-clock resource/genesis/epoch,
literal tick unit `monotonic_nanoseconds`, signed-64 issued/expiry ticks, status `active`, authority sequence,
`ED25519_IDENTITY_AUTHORITY_V1`, key resource/key ID/public-key fingerprint and a canonical base64
64-byte signature. Its message is exactly
`b"FinProof/HumanStableIdentity/v1\x00" || canonical_bytes(attestation_without_signature)`; the
complete-object SHA-256 is external and is the existing `human_principal_attestation_sha256` key.
The strict private `$defs/owner_curator_non_alias_proof` contains version/proof ID, the same authority/
genesis/current sequence, exact owner and curator attestation IDs/digests/stable subject IDs, assertion
`distinct_subjects`, the same trusted-clock resource/genesis/epoch and tick-unit literal, issued/expiry
ticks and the same signature metadata with message tag
`b"FinProof/OwnerCuratorNonAlias/v1\x00"`. It is invalid when the stable subject IDs are equal.

`$defs/identity_authority_current_witness` contains the independently read signed no-reset authority
state, complete `$defs/identity_authority_current_attestation`, current-store receipt, contiguous generation/prior-attestation digest,
subject-to-attestation uniqueness root, active-attestation and revocation roots, and bounded membership/
nonmembership proofs for the supplied attestations/non-alias proof. `IdentityAuthorityReader.read_current()`
returns that authoritative current state and resolves the bounded signed objects; it never treats a
caller-named ancestor as current. Its genesis is exactly
`SHA256(b"FinProof/IdentityAuthorityGenesis/v1\x00" || canonical_bytes({resource_id, store_id,
version: 1}))`; generation zero has empty uniqueness/active/revocation roots. The strict
`$defs/identity_authority_current_attestation` contains exactly attestation version, complete named
`identity_authority_current_attestation_projection`, and canonical base64 64-byte `signature`. That
projection binds resource/genesis/store, CAS generation, complete state SHA-256/roots/counts,
store-monotonic epoch/version, prior complete-attestation digest, deployment key references,
`ED25519_STORE_ATTESTATION_V1` and projection version `1`; it excludes only the enclosing signature.
The signature message is exactly
`b"FinProof/IdentityAuthorityCurrent/v1\x00" ||
canonical_bytes(identity_authority_current_attestation_projection)`. The complete attestation SHA-256
is external and cannot occur in its projection. The manifest pins a distinct
`identity-authority-object-signing` key role for the
two object signatures above and the `identity-authority-current` store key role; cross-role reuse is
forbidden. Human-governance/slot-preparation and owner-remediation transactions
hold or recheck that generation through their CAS, reject an expired/revoked/replaced/self-signed
attestation or proof, require the identity/non-alias clock tuple to byte-equal the freshly held trusted-
clock and selected schedule tuple, and require aliases/role rotation to resolve to the same stable subject. A cross-
resource/genesis/epoch or millisecond/nanosecond substitution is invalid even when the bare integers
compare. Phase 4
verifies the real identity-authority signatures and real-world subject assertion; Task 3 freezes the
message/key/currentness contract and deterministic equality/non-alias checks. Repository artifacts
carry no stable subject, authority proof or person-linking field.

The authority does not replace an attestation or issue a second digest for the same stable subject
inside this competition history. At scope/slot preparation the private scope freezes
`identity_valid_through_tick`, computed no earlier than the maximum precommitted suite, report, fixed-
audit and scope-completion deadline in that exact trusted-clock tuple, and requires both the
attestation and non-alias-proof expiry at or after that tick. A
currently expired/revoked attestation cannot authorize a new review, preparation, claim, dispatch or
child activation. If revocation/expiry nevertheless occurs after a claim, the historical claim-time
membership proof plus the current revocation/expiry proof still permits only deterministic burn,
report, audit and scope closure; readiness is permanently non-PASS and no new result-bearing action is
legal. Thus current identity failure cannot strand mandatory terminal cleanup or reset blindness.

Before the first non-open dispatch in a
curation batch, the principal must complete review/approval and exclusions for every suite in the
batch, and that batch must cover every not-yet-terminal required named slot proven by the guarded
global state. The custodian atomically appends each `human_review_approval` receipt and one immutable
`human_curation_scope` value containing the complete ordered slot/suite/case-set/reserve-subject set,
those receipt IDs/hashes, case-set commitments, and exclusion commitments. The first three entries
have obligation kind `must_execute`; the fourth has `conditional_remediation_child` and the exact
parent/child activation-or-close predicate. The later
public `human_reviewed`/exclusion lifecycle events only mirror these already final receipts inside the
winning claim transaction; they perform no new human decision. Every slot preparation proves scope/
approval membership and exposure nonmembership against the same authoritative private human-
governance head. Review after exposure, scope growth, or a read-then-prepare race therefore loses
mechanically.

The ACL forbids this principal from reading candidate bytes, failure/case identifiers, scoring
entries, private outcome/report detail, provider consoles, or retained traces while any scoped
obligation is unresolved. An unconditional entry resolves only by its deterministic report/burn or
the exact schedule-deadline preclaim/claimed terminal branch with its required audit proof;
the conditional child resolves by parent pass plus `not_activated_parent_pass`, parent pre-truth burn
plus `not_activated_parent_burn`, withdrawal-only parent adjudication plus
`not_activated_parent_withdrawal`, owner decline plus `owner_declined_nonpass`, owner-decision expiry
plus `owner_resolution_expired_nonpass`, or an activated child report/burn. Any still-unclaimed unconditional or conditional obligation may instead resolve only as
part of the exact current-authority `authority_conflict_preclaim_close` contiguous suffix or its
distinct matching `scope_schedule_deadline_close` transition and their
ordered zero-channel audits; that resolution makes completion permanent non-PASS. Every never-activated branch requires its immediate zero-channel child audit before
completion. A claimed parent/child slot's ordinary fixed-schedule audit is instead an eventual
release/organizer/retention prerequisite and is not an input to scope completion. The automated custodian service
may execute without granting human read access. Each nonfinal locked checkpoint may obtain its own
immutable `report_recorded` receipt and implementer/owner-visible outbox after its ordinary checks;
that report is historical named-checkpoint evidence only and does not authorize a batch, cumulative,
release-readiness, organizer-cycle, or submission claim. Its receipt is the prerequisite closure for
the next scope ordinal. An ordinal-0 invalidated report never completes the scope. Parent pass or pre-
truth burn, withdrawal-only adjudication, and owner decline compute the candidate-cycle resolution and zero-channel audit suffix
before deriving the unique completion; an activated ordinal-1 report/burn derives completion from its
ordinary terminal closure. The applicable transaction streams the complete scope, proves every prior
obligation and the conditional branch, and atomically advances every named global/sink/allocation/
human head. A
missing/changed/unclosed entry or concurrent transition loses. Abandoning an incomplete scope yields
the stable `incomplete_must_execute_scope` non-PASS state; it never erases valid historical checkpoint
evidence and never turns a favorable prefix into a releasable result.
For an activated ordinal-1 burn, the same acyclic order applies: its private append binds only the
expected human head and forbids completion/resulting-human-head fields; the transaction computes the
burn head first, derives completion from that head, and atomically advances the guarded stores.

Only after scope completion may a second human-governance transaction insert
`human_output_exposure` and grant the principal access. It proves membership of the exact completion
record, conditionally CASes the same global head unchanged, and advances only the human-governance
head; neither completion nor exposure creates a public successor or timing marker. Making a
repository report, outbox, shared channel, or implementer-visible artifact readable to this principal
is itself an output-access grant and is forbidden before exposure. Once present, the principal can
never curate/review or prepare another locked/sealed suite; a later organizer cycle requires a
genuinely different externally attested blind principal. A suite cannot be omitted from the batch
after another scoped result exists, and no output-informed halt is a valid closure. Repository
artifacts expose only a suite-scoped pseudonymous role ID and secret-backed history commitment, never
the stable private principal/scope ID, raw scope/approval records, private human-linkage proofs,
hidden child case/truth/evidence identities, raw completion record, exact completion tick, or exposure
timing. The policy-fixed four obligation kinds/order, cap, existence of the conditional child, and
each public reserve/report's own inclusion are intentionally public-derivable governance facts. An
individual checkpoint report logically reveals only its own authorized inclusion/closure; no stable
public scope/principal token may link undisclosed entries. A sealed release-readiness claim necessarily
proves only that the private completion prerequisite was satisfied. Task 3 validates
the modeled receipts/proofs/races; Phase 4 must prove the real identity, ACL, console, execution-
obligation, and audit integration before evaluation.

Because one person combines roles, every expected fact requires a deterministic evidence package
and derivation record as the mechanical second check. Any case that cannot be independently
derived and human-verified is ineligible for locked/sealed truth. An LLM, including development
agents or the model under test, may not create, approve, adjudicate, repair, or fill missing
locked/sealed truth.

The reference package may not import or call the production planner, compiler, executor, renderer,
or claim verifier and may not use their cached outputs as truth. It derives facts directly from the
immutable official data with separately reviewed queries and source locators.

### 8.6 Evaluation report and denominator

Create `schemas/evaluation_report.schema.json`. The custodian-private report preserves:

- `authored`;
- `schema_valid`;
- `human_reviewed`;
- `eligible`;
- `attempted`;
- `scored`;
- `passed`;
- `failed`;
- `runtime_error`;
- `timeout`;
- `malformed_output`;
- `evaluation_error`;
- `excluded`; and
- `not_attempted` counts.

Every denominator/outcome counter counts unique case invocations, never request attempts. The sole
retry replaces only that invocation's operational attempt history: with N eligible cases,
`attempted <= N` and can never become `N+1`. Private operational telemetry may separately count
request attempts but is neither a scoring denominator nor a public outcome metric.

The reconciliation equations are closed. `authored == case_count`, `schema_valid <= authored`,
`human_reviewed <= schema_valid`, `eligible + excluded == human_reviewed`,
`attempted + not_attempted == eligible`, `scored == passed + failed`, and
`attempted == scored + runtime_error + timeout + malformed_output + evaluation_error`. Those six terminal outcome
counts are mutually exclusive. An invocation is attempted once its first `dispatch_committed` record
is durable, whether or not the network send is later acknowledged; an ordinal-1 retry changes no
counter. Evidence- and claim-verification failure counts used by the disposition policy are explicit
subcounts with stable case-reference sets and may not be inferred by subtracting aggregate counters.
Every truth-committed locked/sealed report additionally requires `attempted == eligible` and
`not_attempted == 0` because truth release is impossible until the complete eligible invocation set
has a final sealed attempt. Positive `not_attempted` exists only for open/diagnostic reports.

Those equations are evaluated on the custodian-private outcome/report before disclosure. The sole
revoked-capability repository projection instead verifies
`eligible == attempted == truth_not_delivered` and that
every cause-discriminating public counter/partition/token is zero or absent; it may not be reverse-
joined to reconstruct the private equation terms.

The strict non-open report root also requires `release_cycle_id`, suite `run_attempt_id`, immutable
eligible count, `candidate_attempt_set_event_sha256`, complete
`candidate_attempt_set_hmac_reference`, and complete `original_outcome_set_hmac_reference` (equal to
the immutable outcome/post-outcome reference), `disposition_policy_id`,
`disposition_policy_version`, complete `disposition_policy_hmac_reference`,
`consumption_claim_head_sha256`, complete `retired_token_fence_ledger_hmac_reference`,
`history_registry_id`,
`history_genesis_attestation_sha256`, `eligibility_history_head_sha256`,
`truth_release_commit_history_head_sha256`, `truth_release_fence_token_sha256`,
`truth_release_fence_recovery_record_id`, complete
`truth_release_fence_recovery_record_hmac_reference`,
`truth_release_authorization_event_sha256`, `truth_capability_terminal_event_sha256`,
`truth_capability_state` and complete non-null
`truth_capability_terminal_receipt_hmac_reference`,
branch-conditional private `revoked_publication_not_before_tick` required only for
`revoked_without_delivery`, equal to the terminal receipt and selected private schedule entry, and
forbidden otherwise,
`post_outcome_history_head_sha256`, `prior_sealed_disclosure_history_head_sha256` and prior count,
`report_visibility`
(`custodian_private` or `repository_disclosure`), and `disclosure_class`. The eligibility,
truth-release-commit, and post-outcome history heads are distinct for a truth-committed outcome and
must appear in that ancestry order, while allowing unrelated valid successors between them. The
bound public/lifecycle chains must contain the exact commit, authorization-event,
capability-terminal-event, and outcome-event bindings described in Section 8.4.
`redeemed_with_durable_truth_session` requires the matching terminal receipt and may
support a scored pass/fail; `revoked_without_delivery` requires its revocation receipt, forbids a
scored/pass/fail result, and is reason-discriminated. Deadline expiry permits only the matching timeout,
runtime-error or malformed-output mapping above; `authority_conflict_after_truth_commit` permits only
the uniform `evaluation_error/AUTHORITY_RESTRICTION` mapping. That reason discrimination is strictly
custodian-private. Every `repository_disclosure` report for either revoked cause applies one mandatory
public coarsening derived solely from terminal state:
`eligible == attempted == truth_not_delivered`, and every
public passed/failed/runtime-error/timeout/malformed-output/evaluation-error/not-attempted count is zero.
It exposes no cause token, disposition subreason, outcome partition or K5 cell/complement value; any
public summary uses only the same literal `TRUTH_NOT_DELIVERED` bucket. The private report/outcome HMAC
retains the exact cause-dependent counters, and verification proves the public coarsening from the
public terminal state rather than copying a private cause. This is the sole intentional private/public
counter non-equality and makes every non-opaque public event/report field byte-identical for the two
revocation causes given the same public identities and eligible denominator.

An `open_regression` report uses a separate closed `oneOf` branch with
`disclosure_class: OPEN_FULL`. It requires the common report identity, suite/fingerprint, run identity,
count reconciliation, canonical report hash, and report attestation, but forbids the global history,
consumption-claim, disposition-policy, retired-token, release-fence/recovery, truth-capability,
private-report commitment,
sealed-history, and custodian-private truth fields that exist only for locked/sealed execution. It may
publish case-level detail because its cases and truth are already repository-visible. It never enters
locked/sealed metrics or disclosure budgets.

A non-open `custodian_private` report requires complete ordered `breakdowns`, `exclusion_summary`,
the applicable outcome-index record ID/SHA-256, ordered descriptor-list/content hashes, and case-
outcome accounting derived by streaming every indexed entry; it does not copy the outcome array. It
recomputes the original HMAC for revision 1
or the corrected HMAC for a corrected revision while retaining the immutable original commitment before
report signing and forbids
`private_report_commitment`. A non-open `repository_disclosure` report requires
complete `private_report_hmac_reference`, a deterministic `disclosure_payload`, and
`suppression_markers`; it
forbids private breakdown/case fields. Conditional schemas make the variants disjoint.

Every report also has a positive `report_revision` and `correction_state` of `original` or
`corrected`. Revision 1/original forbids every supersession/adjudication field. A corrected revision
targets the registry's current unsuperseded lineage head and increments its revision by exactly one;
no branch or replay of an earlier revision is legal. Every revision preserves
`original_outcome_set_hmac_reference` equal to the immutable `outcome`/`post_outcome` reference. An
original report forbids `corrected_outcome_set_hmac_reference`. A corrected report requires a distinct
`corrected_outcome_set_hmac_reference` whose complete private projection, HMAC, and derived counters were
bound by the matching `post_adjudication(correction_expected=true)` subject; it never overwrites the
original outcome set.

The custodian-private corrected variant also requires
`supersedes_private_report_sha256`, `supersedes_public_report_sha256`,
`adjudication_event_sha256`, `adjudication_history_head_sha256`, and the correction-derivation record
ID/version/rule-artifact hash/input hash/output hash plus the correction-disclosure-delta record ID/
SHA-256 and K5-safe verdict. The repository-disclosure
variant requires the public predecessor/event/head fields and forbids
`supersedes_private_report_sha256`. Its adjudication head must be a matching
`post_adjudication(correction_expected=true)` ancestor, and the authenticated current report-lineage
leaf/proof must contain the later matching `corrected_report_recorded` receipt
before disclosure. The receipt's public hash/private commitment and HMAC-protected private report
hash must equal the independently verified values. No correction changes the original disclosure
budget or permits another truth release.

Every report binds `report_id`/version, suite ID/version/commitment, candidate-fingerprint hash,
checkpoint, governance-policy version, the lane-conditional complete `candidate_cycle_identity`, exact
scorer/rule, selected execution kind/contract ID/version/content SHA-256, common response-contract SHA-
256, static candidate-isolation-profile ID/version/content SHA-256,
`candidate_build_resource_manifest_sha256`, and branch egress-policy identities, timeout/clock policy identities, lifecycle-event-chain head,
canonical report hash, and
a custodian HMAC-SHA256 attestation with an opaque key ID. Its lifecycle head is the exact atomic
head at report snapshot creation. Later content-free late-output, adjudication, disclosure, or
retirement successors do not invalidate the report: verification requires the stored report head to
equal or be an ancestor of `lifecycle_current_head_sha256` in the hash-verified current private-control
snapshot named by the independently read signed pointer. Report creation itself
fails if its supplied snapshot head is stale or omits any receipt already durable at that point.

The sealed candidate-cycle-1 repository-disclosure report branch additionally requires the exact
immutable ordinal-0 `remediation_predecessor_public_ref`, disposition `invalidated`, and parent freeze-fingerprint/
version hashes. The referenced parent outbox must remain repository-readable and its receipt must be
an authenticated ancestor; it need not remain current merely to finish the mandatory child report/
scope closure. The paired custodian-private report and HMAC-protected append require the matching
`remediation_predecessor_private_witness`; the public branch forbids every private witness/auth/proof
descriptor/hash. Ordinal 0 and every locked/open report forbid those fields. No report
contains the later opportunity-summary hash, because that summary is built from already receipted
reports and would otherwise be self-referential.

Only the `custodian_private` report requires the exact private
`output_sink_snapshot_watermark`/`output_sink_ledger_head_commitment` pair verified against the
history/sink witness, the complete ordered runtime-observation hashes,
`runtime_lease_id`, applicable created/deadline ticks, the same five reservation record descriptor
IDs/lengths/SHAs, actual used/remaining allowances, and the recomputed
`evaluation_storage_reservation_commitment` plus exact HMAC metadata. A redeemed capability uses a
strict scoring branch `oneOf` identical to the outcome/finalization contract. `complete` and objective
lease/runtime/deadline error require the non-null scoring lease, both scoring observations, the
authenticated work-ledger head/count/descriptor-list hash, outcome-index/content hashes and
finalization receipt. `authority_restriction` at stage `start` requires only the sole conflict
`scoring_finalized` observation and its complete `scoring_start` authority binding; scoring-start
observation, scoring lease and work-ledger fields are null/forbidden. `authority_restriction` at stage
`finalize` requires the earlier allowed scoring-start observation/non-null lease plus the sealed,
unusable work-ledger prefix and the conflict finalization receipt; no score from that prefix may enter
the synthesized uniform error index. For a revoked capability the scoring lease and all scoring-work/
finalization fields are null/forbidden and its private runtime sequence ends at `pre_truth_commit`.

The `repository_disclosure` branch forbids the sink watermark/head/receipt count/late-byte fields,
runtime-observation hashes, runtime/scoring lease IDs,
private ticks, all five reservation objects, slot-preparation receipt/ID/plain SHA and private
principal/scope/proof metadata, private-control/private-history plan/receipt IDs/plain digests,
snapshot hashes/sequences/chain length, descriptor-manifest hashes, store metadata, and actual
reserved/used/remaining allowances because
they expose observation count/order, response size, or evidence complexity. It requires only the two
non-secret formula versions and the exact `evaluation_storage_reservation_commitment` value plus the
exact HMAC metadata defined in Section 8.5 alongside
aggregate secret-backed candidate-set/
outcome/private-report commitments and non-secret precommitted policy/formula versions. Two
executions with the same permitted disclosure aggregates but different private byte use, observation
count/order, stable principal, curation scope, or proof metadata must produce identical public fields
apart from opaque commitments/HMACs. Neither branch
may populate or omit fields to switch terminal-capability branches.

The report hash is not self-referential. Its exact unsigned projection is a deep copy of the
schema-valid report with root `canonical_report_sha256` removed and nested `attestation.value`
removed; the attestation domain, scheme, version, and key ID remain. Canonical JSON v1 serialization
and SHA-256 of that projection produce `canonical_report_sha256`. The attestation value then uses
the exact `report_attestation` formula in Section 8.5. No other field is omitted from either
projection. A hash or HMAC mutation and every omitted/broadened projection field are RED cases.

After those fields are final, `public_report_bytes` is exactly Canonical JSON v1 serialization of
the complete schema-valid public report, including `canonical_report_sha256` and
`attestation.value`; `complete_public_report_sha256` is SHA-256 over those bytes. This digest is the
meaning of every history/adjudication/correction field named `original`, `target`, `supersedes`, or
`final` public-report hash and is not stored inside the report it hashes. The append-only disclosure
outbox accepts only `public_report_bytes`. Pretty-printed/member-reordered JSON, BOM, duplicate keys,
trailing data, or any non-canonical spelling is invalid even when it parses to the same mapping.
Each original or corrected canonical public-report payload is at most 16,777,216 bytes before the
outbox CAS; the two-payload per-lineage maximum therefore fits the 33,554,432-byte outbox reservation.
Likewise, `private_report_bytes` is Canonical JSON v1 serialization of the complete finalized private
report, including its report hash and attestation value, and `complete_private_report_sha256` is
SHA-256 over those bytes. Every `target_private_report_sha256` or
`supersedes_private_report_sha256` field means that complete digest and is not embedded in the object
it hashes. The independently verified `private_report_commitment` remains a separate HMAC binding.

Report validation is intentionally three state. Before history closure, the custodian freezes the candidate
bytes and obtains an empty `evaluation_control_errors` result plus successful secret-HMAC checks; a
call to `published_report_errors` must still fail with `EVL043_REPORT_CLOSURE_MISSING`. The later
`report_recorded` transaction receipts exactly those frozen hashes/bytes but leaves the canonical
outbox durable and embargoed; re-running the content validator may now succeed, but no external read is
authorized. Finally, `ReleaseActionTransaction.execute(enable_outbox)` completes the target's full
immutable/reference/HMAC validation before taking the current-resource guard, then under the short
guard rechecks exact hashes/current mutable joins and atomically persists that revision's signed
verified-publication receipt plus the resulting private-control pointer while flipping exactly that
outbox record to externally readable. Any report byte, freeze-
fingerprint object, commitment, policy, event, outbox or verified-receipt mutation between states fails
rather than being blessed by an earlier diagnostic result.

For a non-open report, after secret verification of the private report, Phase 4 computes the exact
`private_report_commitment` value from Section 8.5. `build_disclosure_payload` deterministically
derives the only permitted non-secret payload from policy plus that private report. The custodian
supplies that independently computed lowercase 64-hex value as the explicitly external-only
`expected_private_report_commitment_value`; it is not read from the public wrapper or inferred by the
pure validator. `disclosure_policy_errors` rejects a malformed expected value, independently requires
the public wrapper's complete `private_report_hmac_reference: $defs/hmac_reference` equal the
registered domain/scheme/version/key ID plus that value, rebuilds the payload, requires byte-for-byte
Canonical JSON v1 equality, and compares `private_report_hmac_reference.value` to the supplied value
exactly. The external scalar is not an artifact
reference and never substitutes for metadata validation. The
`OPEN_FULL` branch bypasses this private-wrapper comparison and is instead validated directly against
its size-capped content-addressed open manifest and repository-visible case/truth/evidence/run records;
it rejects a mutated outcome even when report counts/hashes reconcile internally. For non-open
reports, the function also checks that the
wrapper binds the suite/fingerprint, run attempt, event head, global registry and
genesis, global consumption claim, disposition-policy ID/version/commitment and verified terminal
decision, candidate-attempt-set and outcome-set commitments,
retired-token fence-ledger commitment, eligibility/truth-release-commit/post-outcome history heads,
release-cycle history, fence-token hash, recovery-record ID, authorization/terminal event hashes,
truth-capability terminal state/receipt,
disclosure class, and,
for a correction, both original/corrected outcome-set commitments and the private report's two
explicitly named predecessor hashes plus adjudication event/head. `build_disclosure_payload` copies
only `supersedes_public_report_sha256` into the public
projection and never exposes `supersedes_private_report_sha256`; `disclosure_policy_errors` requires
that exact mapping. The private report's sink pair is independently reconciled against the private
history/sink witness but is deliberately omitted from the public disclosure payload/wrapper; the
public report's already required history heads and transition-specific commitments provide public
lineage without a comparable sink-state oracle.
The pure function does not pretend to verify the secret HMAC; the custodian runner verifies it and
supplies the expected commitment before signing the public report. Synthetic tests reject an
omitted/altered breakdown, outcome, exclusion, suppression marker, expected/private commitment,
history head, or prior sealed report.

Exclusions are approved by the typed `exclusion_approval` event before lock/seal and remain outside
the eligible denominator. Its private-list commitment and total excluded count must match the suite
manifest, case-set projection, report, and event-chain position. For non-open lanes, reason and fine
applicability totals remain private unless the final disclosure view's same all-or-none K5 cell and
complement rule authorizes them. No exclusion
may be created, expanded, renamed, or reclassified after eligibility or result observation.

Small-cell policy applies to the complete public chain, not only the final report. A non-open
manifest, exclusion event, reserve/reservation attestation, lifecycle event, or history append may
not pre-disclose a reason/category/product/metric cell or complementary count that the final K5 view
would suppress. Validators combine every public count already exposed for that suite/slot and reject
manifest-plus-report or event-plus-report differencing; an earlier leak cannot be repaired by later
suppression.

For locked/sealed execution, the suite is ineligible unless every authored case was schema-valid
and human-reviewed before the manifest was committed and the post-exclusion eligible denominator is
at least `minimum_non_open_eligible: 10`. Invalid/unreviewed drafts or a too-small denominator are
repaired before suite versioning; they cannot silently disappear or proceed to truth release. The
primary denominator is all eligible cases. Candidate runtime error, timeout, malformed output,
evaluator `evaluation_error`, and
not-attempted eligible cases are failures. A
terminal HTTP 200 response with an empty body, or a parsed response with a missing/empty required
result, is normalized into `malformed_output` with reason code `MISSING_RESULT`; it
is not a second unreported bucket. Required reconciliation is:

```text
manifest.case_count = authored
authored = schema_valid = human_reviewed
human_reviewed = eligible + excluded
eligible = attempted + not_attempted
attempted = passed + failed + runtime_error + timeout + malformed_output + evaluation_error
scored = passed + failed
primary_failures = eligible - passed
```

The custodian-private report reconciles totals globally and by lane, category, product type, and
metric. Public/repository projections are fixed before execution and use exactly three disclosure
classes:

- `OPEN_FULL` may publish case-level detail only for repository-visible open cases;
- `LOCKED_AGGREGATE_K5` publishes overall outcome totals only when eligible is at least ten and may
  publish at most one predeclared disjoint one-dimensional partition. The partition is all-or-none:
  every cell and every cell's complement must each have denominator at least `cell_k: 5`; if any
  fails, the entire partition is replaced by one `suppressed: true` marker and no cell denominator,
  numerator, failure count, or token is published. The same all-or-none rule applies to exclusion
  reason partitions; and
- `SEALED_OVERALL_ONLY` publishes overall denominator/outcome counts only when eligible is at least
  ten, plus suite/fingerprint/report/release-cycle bindings and suppression-safe aggregate exclusion
  totals. It publishes no breakdown or failure token.

There is no below-ten locked/sealed report branch. A non-open suite below ten is ineligible before
reservation/claim/truth release and can produce only pre-execution eligibility/history evidence, never
`post_outcome`, report-candidate, disclosure-outbox, or `suppressed: true` result artifacts. The K5
suppression marker applies only to a partition of an otherwise K10-eligible report.

No ad hoc slice, intersection, overlapping partition, repeated-query differencing, or post-result
view change is permitted. Locked/sealed failure identifiers and explanatory dumps remain with the
custodian; implementers receive only the predeclared disclosure projection. Exact excluded totals
remain in the private report. A suppressed reason partition exposes neither its reason-code list nor
individual counts; the public aggregate excluded total cannot be used with another published
partition because no second partition is allowed. The validator rejects partial/secondary-cell
publication, small-cell/complement leakage, non-predeclared views, cross-tabulation, and totals that
cannot reconcile through suppression markers. Adversarial fixtures include `[1,5,5]`, `[3,6,6]`,
a lone small exclusion reason, and an attempted result-bearing report below ten.

Locked/sealed expected payloads, per-case correct answers, source evidence, and explanatory failure
dumps remain with the custodian. Post-result defect adjudication never overwrites the original
report: it appends the type-correct invalidation or terminal-state adjudication event and, when
authorized, produces a separately versioned corrected private/public report pair. The corrected
public report keeps the original disclosure class, whole-partition suppression, private-report
commitment history, and cumulative sealed-history predecessor head/count; it cannot reveal a
difference-slice or erase the
superseded report.

## 9. Handoff and repository enforcement

`tools/verify_handoff.py` remains dependency-free and adds stable checks for:

- every Task 3 schema/config/tool/test/document required by the handoff;
- this approved Task 3 design, the exact dated Task 3 execution plan, and the frozen legacy-seed
  migration manifest as required files; the plan binds this design's approved commit and SHA-256;
- unique schema `$id` values and a closed allowlisted `$ref` graph;
- all current visible seeds declaring only `open_regression`, `ai_scaffold`, and
  `human_review_required`;
- no visible seed or repository truth payload declaring locked/sealed eligibility;
- the exact LF base-blob 13-case/302-leaf inventory hash, closed transform registry, complete
  migration-mapping shape, and non-exact semantic-review binding;
- no forbidden locked/sealed truth fields under registered structured evaluation-asset roots;
- the exact 207-pair coverage inventory and catalog binding from the committed JSON lock, plus the
  exact YAML-byte hash without pretending to parse arbitrary YAML semantics;
- the governance lock's policy/checkpoint, release-cycle budget, HMAC domain, and disclosure
  projection plus exact YAML-byte hash; and
- unchanged bootstrap behavior under `python -S -B`.

Full semantic schema, YAML, coverage, lifecycle, and report validation remains in focused contract
tests using the approved development dependencies. Tests prove that dependency-free handoff checks
do not accept a mutation rejected by the corresponding security policy.

`HANDOFF_PACKAGE_MANIFEST.md` documents the new control-plane boundary but does not alter the
frozen `INITIAL_IMPORT` block unless `START_HERE.md` is changed in the same approved scope. This
Task 3 design does not require changing that frozen block.

## 10. TDD and adversarial verification

Every behavior follows observed RED -> minimal GREEN -> relevant suite -> refactor while green.
Dependency or fixture absence does not count as the RED for behavior whose prerequisite has not
yet been created; rerun the focused test after the prerequisite exists and before implementing the
behavior.

### 10.1 Typed-contract RED cases

At minimum reject:

- an unresolved, remote, duplicate, or mismatched schema reference;
- a seed plan missing `filters`;
- a JSON number in an exact-decimal result or calculation input;
- a float in a QueryPlan filter or EvidenceRecord `normalized_value`, a runtime `Decimal`, or any
  otherwise schema-valid object outside the Canonical JSON v1 evaluation domain;
- a lone surrogate U+D800 through U+DFFF in a question/value string or object key, with the stable
  value path or containing-object path/key ordinal reported before any UTF-8 encoding;
- an object mixing valid string keys with one or more non-string keys, with an aggregate UTF-8-safe
  diagnostic that never sorts or stringifies the invalid keys and still inspects every valid-key value;
- Pydantic coercion of a string/boolean/number into another JSON type, a mutable nested list/map in a
  boundary model, mutation after a canonical hash is computed, a raw dictionary crossing a core-
  module boundary, or model/schema dump-roundtrip drift;
- duplicate JSON object members, a UTF-8 BOM, non-finite constants, trailing JSON data, or YAML
  duplicate mapping keys/anchors/aliases/merge keys/custom tags before schema validation/canonicalization;
- a missing or empty evidence requirement;
- a legacy free-form required-semantics answer;
- a missing/duplicate legacy leaf mapping, CRLF/working-copy inventory substitution, changed frozen
  base-blob inventory hash, unresolved migration target, unknown transform/parameter, non-recomputed
  transform, missing non-exact semantic-migration review, changed included review-projection member,
  self-referential review digest, or broadened/narrowed review-projection exclusion;
- an invalid product/grain or fund-attribute identifier;
- duplicate rank/product/fact/claim IDs;
- an unknown nested property;
- aggregate evidence missing its execution-plan hash or internally valid logical-proof hash; and
- an evidence package with an unresolved claim/EvidenceRecord, mismatched reverse reference, or
  aggregate proof as the sole support for a material source-derived claim.

### 10.2 Coverage RED cases

At minimum reject:

- missing, extra, duplicate, table-less, or case-folded catalog pairs;
- an invalid status or missing reason;
- a concept reference to a nonexistent catalog pair;
- an unbound or multiply bound planner alias target;
- `risk_grade: supported` while any mapping, product scope/definition, missing/null, ordering, or
  evidence rule is absent;
- an implicit classification introduced by a default, glob, prefix, sample, example, or `axis_*`;
  and
- report changes caused only by input-order changes.

### 10.3 Governance RED cases

At minimum reject:

- a visible case relabeled locked or sealed;
- an `OPEN_FULL` report with a mutated truth/outcome that keeps self-consistent counts/hashes, a
  missing/extra/multiply referenced open case/evidence/run record, or an open manifest/record/total
  above its pre-parse cap;
- a suite containing repository-visible truth fields;
- locked/sealed overlap, reserve reuse, an output-informed derivation, a forged private fingerprint,
  or a truncated/forked/gapped history-attestation chain;
- a substituted registry ID/genesis, a second null genesis, a stale-head fork, a key-rotation reset,
  or a new organizer release cycle that does not extend the globally pinned history;
- a history transition with a copied root but missing touched record/proof, wrong Sparse-Merkle sibling
  order/bit/domain, immutable-leaf overwrite/delete, stale mutable old value, occupied-to-empty update,
  expanded full map/list inside `resulting_counters`, or A-to-B then B-to-A derivation; a locked/sealed
  child whose authenticated ancestry flag shows a disclosed ancestor, or a corrected receipt that
  reinserts/replaces the original suite-disclosure leaf;
- a proof bundle with more than 512 entries per chunk, 300,000 per registration transition, or 400,000
  cumulatively per suite, wrong deterministic order/
  intermediate root, missing/extra chunk, a max-10,000-case/eight-parent registration whose every
  transition record does not fit, or a transition subject containing its own descriptor/new archive-
  manifest/public-attestation head;
- a private-history record/manifest/transition/suite above its byte/count/shard cap, a suite-archive
  receipt with future registry heads, a per-kind size/occurrence/witness or total under-allocation,
  a maximum reserve transition whose 100,000 bootstrap records, 50,000 registration values, proof
  chunks, receipts, transition, and manifest descriptors do not simultaneously fit the 160,000-
  record/17,179,869,184-byte transition and 200,000-descriptor/134,217,728-byte shard caps,
  a private-history plan/receipt substituted or omitted between reserve, fingerprint, claim, run,
  private bundle, truth commit, outcome, or private report,
  a legal schedule of 10,001 one-at-a-time sink receipts/checkpoints that exhausts an accepted plan,
  or normal transition validation that tries to materialize the complete archive instead of using
  bounded state/proofs;
- a reserve suite manifest created before selection, an out-of-order batch activation, or a selected
  suite/case-set/checkpoint value differing from its pre-result reserve-batch commitment;
- a second reserve batch or a batch size other than one for a slot, a batch registered after any
  reservation/claim/dispatch, skipped/reused sole ordinal, two outstanding reservations, a reservation
  or claim committed without
  its atomic pair, or a paired CAS that publishes an orphan manifest/fingerprint/preclaim lifecycle
  event after losing, omits the consuming event, or rebuilds a retry from anything except the same
  immutable human-review/exclusion evidence;
- a private history projection containing its successor/current head, a changed predecessor/private
  prior/appended record/resulting counter, or a public outcome/retry/adjudication variant whose event
  hashes or budget deltas disagree with the lifecycle chain;
- a `history_registry_state/resulting_counters` projection containing its own current/resulting
  attestation/CAS head, or a slot leaf containing its same-writer claim, burn, truth-commit,
  post-outcome, report, resolution, or audit resulting head instead of the exact predecessor-
  independent source descriptor/hash and permitted already-durable prior heads;
- an AI truth author/reviewer or a missing independent-human attestation; a private human-governance
  registry reset/fork/alternate genesis, missing/mutated/replayed review-approval/scope/completion/
  exposure record, root, receipt, or proof, scope above its policy cap, duplicate/permuted/backward
  checkpoint order, a noncanonical suffix, omission of either candidate-cycle-0 or its conditional
  candidate-cycle-1 entry while that obligation is unresolved, a fresh-state shorter-than-four scope,
  or any omitted prefix without authenticated terminal closures,
  dispatch before an earlier ordinal is reported/burned, review/exclusion approval
  after exposure, slot preparation racing exposure in which both win, or a lifecycle `human_reviewed`
  event that differs from its completed private receipt; a combined human who reads any embargoed/
  repository candidate/outcome/failure/report detail before every scope obligation—including the
  conditional child's branch-exact resolution/audit or activated report/burn—has authenticated
  terminal closure; an exposure leaf omitted before ACL access, a scope enlarged or
  suite omitted after execution starts, a branch-specific resolution/audit/report/burn and completion
  transaction that is not all-or-none, a cumulative/release/submission/organizer-cycle claim from an incomplete or abandoned
  scope, a locked historical checkpoint incorrectly rejected only because completion is pending, a
  historical report rejected after a legal completion/exposure descendant merely because current-
  root exposure nonmembership is no longer true, a report-time human head that is not an ancestor, a
  caller-selected stale global/human head in the completion/exposure CAS, or the same stable principal
  hidden behind a fresh pseudonymous role ID/custodian transfer; or a public stable principal/scope
  token or cross-suite role alias that links reports back to the private stable person;
- a missing, forged, or mismatched evidence-package descriptor/content/HMAC commitment; a case-set
  index with missing/extra/reordered/duplicate/unreferenced entry, case, truth, or evidence records,
  mismatched counts/exclusions/descriptor-list hash, a plain public descriptor hash, an index above
  10,000 entries or 16,777,216 bytes, or a max-10,000-case/1,073,741,824-byte source set that cannot be
  verified through bounded streaming; an unknown/drifted selection-quota rule or predicate AST, a
  predicate reading truth/result/output fields, a self-asserted selected count, parent/child quota
  projection drift, or a comparability SHA over anything other than the exact public-safe projection;
  a truth-payload record that omits/reorders/substitutes an
  eligible entry, crosses suite/run/candidate-set identity, supplies a new expected value, differs
  from its decrypted session plaintext, or is not fully re-derived before scoring;
- an illegal lane transition, broken event hash chain, duplicate event, or second consumption;
- a locked post-consumption invalidation branch or a sealed post-consumption branch with the wrong
  tuning/fingerprint disposition;
- an exclusion without a pre-lock/pre-seal approval commitment, or any post-result exclusion edit;
- a non-open manifest/event/history object exposing a reason or fine applicability cell that fails the
  final K5 cell/complement rule, including a lone exclusion count recovered by public-chain/report
  differencing;
- truth read/decryption/delivery without the winning pre-decryption `truth_release_commit`, its raw
  fence token, matching durable authorization and capability-terminal events, or a commit that failed
  its CAS;
- two active claims for one locked-checkpoint/sealed-cycle slot, a suite-local consuming transition
  without the global claim CAS, a claim for the wrong suite/fingerprint/attempt, a transfer/
  burn interleaving between a stale read and truth access, or a `post_outcome` that first consumes or
  increments the slot instead of recording an already committed outcome;
- a truth-release commit without the exact run-binding HMAC projection, fresh suite run-attempt ID,
  winning consuming-event and global claim/transfer heads, eligible-count-complete
  candidate-attempt-set event/HMAC, matching fence-token hash and slot, or exactly one applicable
  result-bearing budget increment;
- release-fence-token replay, a second truth delivery, outcome/post-outcome while the capability is
  still `available`, a healthy pre-effective-deadline revocation, a terminal state inconsistent with
  its required non-null receipt, revocation
  that created a truth session, redemption without a durable truth session, or post-crash
  dispatch/scoring of a different response set;
- a revoked sealed run retired by permissive thresholds, any revocation-reason/final-seal outcome
  pairing outside the exact mapping, or a redeemed scoring crash that publishes a favorable/
  unfavorable prefix, mixes `evaluation_error` with partial scores, changes scorer/rule version, or
  permits human-selected abandonment;
- an AEAD purpose/key-resource reused across recovery/truth-session purposes or any HMAC resource;
  a nonce-registry reset/fork/alternate genesis, same key/nonce, or same suite/run/purpose under a fresh
  target/preparation/claim ID; a missing/substituted nonce-claim receipt, sequence/head/unique-key
  mismatch, target-record ID mismatch, or a nonce/ciphertext durably written by a losing/aborted
  transaction;
- a recovery record with substituted ciphertext/token hash/blob descriptor, wrong 48-byte length,
  failed authenticated decryption, mismatched attempt/set/purpose/key-resource/receipt, any omitted/
  extra AAD field, an immediate registry predecessor inside its encryption subject, or stale-head
  retry that creates a second nonce/ciphertext rather than committing all objects/head or none; a
  truth-release commit that omits the expected/current private-control pointer and allowance, recovery-
  descriptor snapshot suffix, resulting pointer attestation, or their same-transaction CAS; any partial
  nonce/record/blob/snapshot/pointer/history state or any recovery/AAD/snapshot payload containing its
  resulting pointer or global head;
- any pre-redemption or losing/stale/aborted truth payload, nonce receipt, ciphertext, session,
  terminal record, snapshot/decrement, or pointer change; an ambiguous-crash retry without
  authoritative commit/abort proof; a redeemed terminal receipt with a missing/substituted truth-
  session or truth-payload record, wrong case-set/candidate-set/predecessor-pointer binding, altered
  AEAD/AAD/ciphertext descriptor, session replay, activation at or after the effective deadline,
  partial terminal transaction, or a self-referential session digest; any payload/AAD/session/terminal
  projection containing its resulting snapshot/pointer attestation, terminal event, or future global
  head; or a revoked branch that creates payload/nonce/ciphertext/session material or omits its own
  terminal-record/snapshot/pointer all-or-none transition;
- fewer or more than N one-request-per-invocation bindings for N eligible cases, duplicate/extra
  requests for one invocation, noncontiguous ordinals, more than one terminal stream for one case
  attempt, candidate response/failure mutation after sealing, truth access before complete set
  sealing, or selection among conflicting responses instead of a consuming `protocol_violation`;
- a deterministic-core request with a missing/drifted request/result fragment or QueryPlan schema
  lock, wrong request/plan bytes, any expected-result/answer/evidence input, GET/HTTP/HCX/provider/
  network field, `at_egress`, injected/mislabeled private mount or custodian/KMS credential, unpinned
  resource attestation, invocation count other than one, dispatch-prepared observation containing its
  future dispatch receipt/result, or missing/mutated adapter receipt/`verified:true`/result hash/common-
  response mapping; a core first-chunk/prefix per-attempt overflow not paired with
  `RESPONSE_SIZE_LIMIT`, or a core run-total overflow missing the exact local receipt/burn snapshot and
  no-candidate-seal pairing;
- an end-to-end request whose method/path, execution-contract ID/version/hash, question ID/text,
  canonical query bytes, private case fingerprint, attempt binding, or dispatch receipt differs; query
  encoding that changes pair order, normalizes Unicode, emits `+` for space, uses lowercase percent
  hex, admits a lone surrogate, or mishandles Korean text or literal `+`, `%`, or `&`; or any caller-
  supplied QueryPlan/callable/local-invocation field;
- an execution kind/contract/common-response/isolation-profile ID/version/hash substituted between
  governance, reserve subject, manifest, fingerprint, claim, run/runtime, attempt/set, outcome,
  correction, or report; a Phase-2 core contract used at Phase 3/sealed, an end-to-end contract used at
  Phase 2, or a response with a missing/extra/duplicate/non-string field, wrong echoed request strings,
  or empty/whitespace-only answer accepted as `completed_response`; a missing `answer` not mapped to
  `MISSING_RESULT`, or a missing `think_trace` mapped anywhere except `API_CONTRACT_VIOLATION`;
- a redirect, transparent HTTP retry/reconnect, alternate origin/TLS identity, second response,
  unaccepted status/framing, cache lookup/write, or query/body persistence outside the private attempt
  store; a canary present in any log/APM/cache/provider console; or provider retention visible to an
  implementer;
- a controller-denied provider cap/retry attempt not sealed as
  `protocol_violation/PROVIDER_POLICY_DENIED`, an escaped/unverifiable provider call not burned as
  `provider_egress_fence_breach`, an unreceipted/extra provider invocation, an alternate generative
  endpoint, a provider request/response byte-length or SHA mismatch, public exposure of a provider-
  payload digest, or an egress-policy,
  scorer/rule, runtime lease, runtime-observation, timeout, or clock identity that differs from the
  reserve/fingerprint; more/fewer than the exact expected provider receipts;
- a runtime-observation list longer than 10,004 for deterministic core or 30,004 for end-to-end, any
  core provider/`at_egress` observation, any end-to-end `at_local_invoke`, more than two provider
  observations per end-to-end case attempt or 20,000 per run, any provider transport retry, missing/
  gapped/duplicate sequences, an unsigned-
  projection hash substituted for `runtime_observation_sha256`, drift between cases or before truth
  commit, runtime A->B->A drift during response generation, scorer/rule A->B->A drift or scoring-
  lease loss/restart between scoring start/finalization or recovery, an evaluation-error branch with
  no authenticated final failure observation or that falsely asserts lease continuity, or a dispatch
  prepared under one identity then sent after lease expiry/drift;
- a private-control bundle with an unknown/wrong stage, missing predecessor object, extra field,
  opaque commitment without the complete private projection, a missing/substituted attempt binding,
  dispatch-prepared record/subject, dispatch receipt, candidate seal or set member, a fabricated/
  gapped scoring-ledger head,
  a monolithic outcome array copied into an outcome root/report, a missing/duplicate/reordered outcome-
  entry descriptor, an indexed entry whose ordinal/length/hash differs, an outcome-content alternate
  wrapper/concatenation/omitted counter, an outcome-content/
  finalization-receipt mismatch, or disclosure-outbox bytes that are not the exact
  receipted canonical report bytes; a burned bundle that admits truth/report fields, an original-
  target withdrawal that admits corrected records, or a corrected-target withdrawal that deletes its
  already durable corrected records or adds a second correction/outbox;
- a private-control snapshot above 65,536 bytes, a snapshot delta above sixteen descriptors, a chain
  above 210,014 snapshots, a caller-selected ancestor instead of the trusted current pointer, more
  than 200,002 cumulative record descriptors or 10,004 binary descriptors, a generated max-shaped
  snapshot that exceeds its cap, a control record above
  134,217,728 bytes, response blobs above 67,108,864 or outbox blobs above 33,554,432 in aggregate,
  recovery ciphertext other than 48 bytes, truth-session ciphertext above 16,777,232 bytes, a
  max-shaped original/corrected public report above 16,777,216 bytes, a same-stage snapshot with no
  descriptor, a wrong stage edge, a partial-attempt/scoring crash whose durable descriptor is absent
  from the current chain, a compound transition whose intermediate snapshots/current pointer are not
  all-or-none, pointer-resource/genesis substitution, an ancestor/fork/reset pointer at a later CAS
  generation, a generation skip/replay, a first-new-snapshot predecessor other than the expected
  current snapshot, a run binding whose initial pointer state/attestation digest differs, a pointer
  attestation above 16,384 bytes, with a missing/substituted prior digest, reset monotonic epoch,
  changed scheme/key, field/value/complete-digest mismatch, or fresh opaque digest over the wrong
  pointer state, a pointer write outside the all-or-none transaction, a sequence-zero descriptor other
  than the exact five preclaim reservation records followed by the exact one-through-eleven-event
  claim-time lifecycle chain, a lifecycle event durable outside that snapshot/CAS, a run-binding/
  runtime/attempt record in sequence zero, a run HMAC
  whose bound pointer derives from a snapshot containing that HMAC record, a reservation below
  `13763477504` fixed snapshot bytes,
  snapshot counters that include
  their own bytes or private-history usage, or a private sink checkpoint charged to private control,
  duplicate/unreferenced/multiply referenced records/blobs, a length/hash/stream mismatch, a
  reservation-plan/per-record/schema-maximum mismatch, a legal max-shaped outcome entry that exceeds
  the record cap, a storage-reservation receipt or preclaim basis containing a future reserve-batch/
  reservation/claim/fingerprint/resulting head, an under-allocation/substituted plan, receipt,
  expected predecessor, amount, commitment, or key metadata, or any post-truth record rejected after
  a valid preclaim reservation; two prepared allocations for one suite/kind, two slot-preparation
  rows for one registry/slot, slot-preparation-registry reset/fork/alternate genesis, a missing or
  forged slot-preparation receipt/nonmembership proof, deletion/reuse of an abort tombstone, or an
  invalidated/reclaimed first
  subject followed by a fresh batch/suite/case-set subject for that slot; stale-head refresh that
  changes the stable key, subject/basis/plan/allocation ID/allowance, reuses predecessor-dependent
  proof/manifest bytes, skips/replays `preparation_generation`, or leaves an old receipt/HMAC usable;
  two receipt `slot_preparation_id`/subject digests, generations, or expected registry predecessors
  that differ, either receipt subject differing from the preclaim basis, or an archive-predecessor
  digest substituted for the registry-predecessor field;
  activated allocation reclamation; a bootstrap manifest treated as an archive shard or containing
  a registration value/proof/proof-bundle, receipt, storage HMAC, or reserve-batch transition; more
  than one actual archive manifest for the reserve-batch transition; or an H0-prepare -> unrelated-H1
  case-registration/archive append ->
  rebase/retry/crash/losing-CAS schedule that leaks a second/unreapable allocation or cannot produce a
  valid H1-rooted transition; H1 creating an overlap/disclosed ancestor yet refresh still reserving or
  selecting a replacement suite; or H0-prepare -> H1 key rotation/custodian transfer/policy change ->
  any outcome other than permanent slot-preparation abort tombstone, allocation reclamation, and no
  replacement/rekey/recustody retry;
- a process/host clock substitution, clock epoch reset/rollback, deadline extension after restart,
  expiry asserted without the same restored clock epoch, a component/effective-deadline mismatch, or
  boundary comparison that treats elapsed == limit as still valid;
- a retry without a fresh ordinal-1 attempt/request/token and exact transfer/ordinal-0-close ancestry,
  substitution of that graph in the final candidate set, duplicate send after an ambiguous dispatch,
  or recovery of anything except a proven still-undispatched binding;
- a response byte acknowledged before durable buffering, a chunk gap/conflict/second stream, a
  response above 1,048,576 bytes whose crossing chunk is persisted/acknowledged or not atomically
  sealed as `protocol_violation/RESPONSE_SIZE_LIMIT`, a first-chunk overflow with a fabricated blob,
  a prefix-overflow crash that remains open/changes counters, a chunk crossing both per-attempt and
  run-total caps that selects the burn branch or increments the run counter, a seal differing from the
  durable buffer, or a first-byte/terminal-
  frame crash that permits zero-byte retry, buffer loss, or response selection;
- a run-total response chunk crossing 67,108,864 bytes that is persisted/acknowledged, classified as
  a case outcome, or followed by anything except the exact terminal budget-exceeded burn;
- a terminal HTTP 200 empty/missing-result response classified as timeout/runtime error, a no-frame
  deadline classified as missing result, or an authenticated transport failure classified as
  timeout/malformed output;
- pre-dispatch ingress while the token is inactive, token activation without the exact
  `dispatch_committed` receipt/transport ID, or an ingress-versus-undispatched-close race in which both
  operations succeed;
- a burn-versus-dispatch or burn-versus-socket-send interleaving in which both win, a dispatch receipt
  omitting the active owner/expected registry head/fence epoch/lease, a prepared outbox row sent after
  burn, or a dispatch-winning ambiguous send treated as pre-egress retryable;
- retry or another run after a truth-release commit/crash; transfer unless ordinal 0 is still
  pre-dispatch with no `dispatch_prepared`, dispatch commit, egress, or ingress; more than one
  transfer/ordinal-1 binding; or ordinal 2 under any runner/key identity;
- retry after an ambiguous or committed dispatch, an ordinal-1 pre-dispatch failure fabricated as an
  attempted outcome, or creation of another binding instead of recovering that ordinal-1 binding or
  burning the slot;
- a fingerprint change/operator abort that returns the slot to free or selects another suite instead
  of terminal burn;
- a transfer whose old token remains live, a byte accepted under a tombstoned token, a late byte not
  quarantined and bound to an active burn or private sink checkpoint, a truth-commit-versus-late-byte
  interleaving that produces two selectable results, or transfer after an unfenced/late-byte attempt;
- a duplicate late-output receipt for one token/fence key, an omitted/reordered/replayed sink receipt,
  a second receipt ID for an occupied sink-coalescing key or missing empty-to-occupied proof,
  a checkpoint carrying commitments without the exact new content-free projections, a checkpoint
  copying any prior prefix instead of the delta range, a mismatched
  sink watermark/head or nonpositive/wrong delta, or a million-byte same-token flood that creates more than one
  receipt or prevents terminal report construction;
- a post-report or post-burn sink receipt omitted from `output_sink_checkpoint`, a continuity/
  organizer/adjudication append that loses a receipt arriving between sink observation and registry
  CAS, a missing/reordered/stale `HistoryTransitionWitnessModel` or history-reader record that cannot
  reproduce the supplied sink/report roots, duplicate charging of that record to private control, or
  a late receipt interposed inside the atomic original/corrected report-closure transaction;
- a private sink-registry reset/fork/alternate genesis, a global successor that checks the global and
  sink heads sequentially rather than one linearizable transaction, a bare/comparable sink-head HMAC,
  watermark, receipt count, late-byte boolean, conditional checkpoint/event, or private failure reason
  inserted into any public history/lifecycle/report branch, or two otherwise equal public successors
  whose non-opaque fields reveal whether the sink advanced;
- an omitted/conditional `slot_private_audit_closed` for a zero- or positive-receipt terminal slot, a
  closure whose private delta/destruction proof is incomplete, a claimed-run audit attestation
  persisted without its matching lifecycle event/head CAS, an unused-child audit persisted without
  its exact preceding resolution or with a fabricated lifecycle/run/channel, a stranded
  `terminal_close_pending_audit`, a later organizer/retention transition missing the applicable closure
  heads, or physical ingress still possible after a claimed closure;
- a candidate run with any missing or mismatched freeze component;
- reuse after consumption, invalidation, disclosure-driven tuning, or fingerprint change;
- more than one result-bearing locked disclosure at a named checkpoint, more than one result-bearing
  original sealed disclosure in one candidate cycle, or a correction that consumes another release
  cycle/result budget instead of remaining the sole zero-budget revision in that original's lineage;
  more than two result-bearing originals in one organizer opportunity, any child other than
  the sole precommitted ordinal 1, a release-cycle reset, optional stopping, or a cumulative report
  that hides a prior failed sealed result;
- a readiness/submission claim with a locked checkpoint burn, missing/withdrawn/noncurrent locked
  report, absent scope completion, owner decline, child burn/invalidation, blended parent/child totals,
  latest-only sealed input, a missing revision/hash-keyed parent dependency, a caller-selected lineage
  ancestor, or any parent adjudication/correction/supersession/withdrawal after remediation
  authorization;
- a sealed-disclosure entry containing its future resulting/receipt head, an entry computed from a
  head other than the exact pre-CAS predecessor, or a successor head/count not reproduced by the
  branch-correct `current_report_receipt_ref`;
- a sealed-disclosure genesis derived from `history_genesis_attestation_sha256` or another field inside
  the revision-1 attestation that the resulting private/public genesis commitments help hash;
- an organizer-cycle successor without an externally pinned owner authorization, with a reused
  opportunity ID or mismatched source/cycle IDs, with missing method-specific evidence/human check,
  that treats the owner HMAC as organizer-authenticating proof, or that resets a locked-checkpoint
  slot/counter; a missing/mismatched remediation-compatibility review, a no-conflict result with a
  nonempty restriction list, or cycle creation despite an explicit official conflict; cycle A -> B -> A under a fresh slot, or the same organizer authority object/artifact/
  ordinal replayed under a fresh opportunity ID; a non-null fabricated prior cycle on the first
  successor, a null prior later, or a prior cycle unequal to authenticated current state;
- a genesis missing either locked-checkpoint `slot_state: free` leaf/zero counter/empty ledger, a
  genesis that fabricates a sealed opportunity/cycle/slot without organizer evidence, or a first
  sealed cycle with a dangling/mismatched opportunity or organizer-evidence leaf;
- an owner-remediation authorization under the organizer/custodian domain or a reused key; with a
  substituted child base, parent report/fingerprint/terminal/outcome/audit trigger, action, cause,
  owner-person/non-alias proof, corrected-build subject, or change evidence; an activate decision whose
  submission-freeze authority state is missing, caller asserted, stale, based only on the opportunity-
  creation review, omits a newer first-ranked instruction, uses an owner-only post-freeze permission,
  uses a YAML/config/caller-chosen effective tick instead of the authenticated official deadline/
  clock mapping and optional earlier submission event, lacks either independently supplied current
  instruction/clock/submission-state witness, omits an existing submitted/frozen event, replays a stale
  pre-submission state, swaps/omits an authority signature tag, scheme, version or pinned key, uses a
  plain-digest/unregistered-HMAC/cross-key attestation, or changes a
  component outside the exact organizer-exception allowlist; an effective-freeze branch
  with no valid exception or out-of-bounds activation tick, a not-effective branch whose trusted tick
  is at/after the freeze, unequal checked/activation/current clock ticks, or replay of a just-before-
  freeze owner HMAC just after the freeze;
  an activate decision whose
  later fingerprint is not its exact fieldwise extension, a decline carrying build data, an auth object
  containing raw private report/outcome/plain digest, suppressed detail, enclosing scope hash, current
  resolution predecessor/resulting/future head, a nested/copied self-HMAC inside the action payload,
  or an HMAC input projection retaining root `attestation.value`; replay after the one-use leaf, activate
  after decline/pass/burn/parent withdrawal, a withdrawal-only adjudication that leaves the dormant
  child/scope unresolved, requires the adjudicated target receipt to remain current at the later
  resolution head instead of proving it current at the initial guard, or races successfully with
  activate/decline; an activated-child report that substitutes a later parent revision or requires the
  frozen remediation predecessor to remain current rather than proving its activation/receipt ancestry;
  a repository-disclosure child report/index key containing the private owner-authorization/base/
  change-evidence descriptor or hash, guarded-lineage proof descriptor/hash, stable-person/scope
  metadata, or complete private remediation witness; a public/private predecessor projection mismatch;
  a fingerprint containing the full private base/base SHA/approval/scope
  metadata, a digest-only or indirect public-basis equality, a second/alternate child, or a third
  candidate cycle; any post-parent-output change to the child case/truth/evidence selection hidden as
  a candidate-build remediation, or rejection of an otherwise valid owner-authorized build change
  solely because the already pre-output-frozen child selection is unchanged;
- a cross-domain HMAC replay or a lane/checkpoint/policy/suite/fingerprint substitution;
- a missing/extra HMAC domain, a domain/key-ID mismatch, one key ID reused across two domains, a bare
  HMAC value where the complete binding is required, missing/extra domain/scheme/version/key metadata,
  or reuse of the same value with substituted metadata in a manifest, case-set entry/index,
  comparability projection, fingerprint, attestation, outcome, or report;
- a self-referential or incorrectly projected report/logical-proof hash;
- a report where manifest count, authored, schema-valid, or human-reviewed counts differ;
- a denominator where one retry increments `attempted`, any reconciliation equation fails, or an
  invocation occupies two terminal outcome categories, or a truth-committed non-open report has
  positive `not_attempted`/`attempted != eligible`;
- any public reserve/history/fingerprint/report projection exposing one of the five reservation
  objects, a slot-preparation receipt/ID/plain SHA or private principal/scope/proof metadata, a
  private-control/private-history plan/receipt ID/plain SHA/descriptor-manifest hash/store metadata,
  a plain snapshot hash/sequence/chain length, or actual reserved/used/remaining record counts or
  bytes; a plain structural digest substituted for
  `evaluation_storage_reservation_commitment`; or two runs with equal permitted public inputs/
  aggregates but different private count/byte use producing different non-opaque public fields; a
  paired-suite public projection that reuses a principal/scope/role token and thereby links one
  published checkpoint to undisclosed future scope entries;
- a report that hides timeout/error/malformed/not-attempted cases or fails to classify a missing
  result as `malformed_output/MISSING_RESULT`;
- a truth-committed outcome without an atomic `post_outcome` successor, a report with missing, equal,
  unordered, unrelated, or substituted eligibility/truth-commit/post-outcome heads or fence-token
  hash, a second post-outcome after an unrelated successor, an outcome-set mutation hidden behind
  reconciled aggregate counters, or a later suite that reserves while outcome/report closure is
  outstanding;
- a missing/duplicate/substituted `report_recorded` receipt or disclosure-outbox record, report bytes
  readable before its CAS, a later cycle that omits a prior unreported result-bearing commit, or a
  terminal disposition selected after public score access instead of by the precommitted policy;
- an outbox payload with BOM, duplicate key, trailing data, pretty/reordered spelling, or bytes other
  than Canonical JSON v1 of the complete public report; one original/corrected public payload above
  16,777,216 bytes, copied outbox bytes inside a private-history append, an outbox record containing
  its future report-receipt head, or a complete public/private predecessor hash
  computed from an unsigned projection or changed attestation value;
- a prepublication candidate accepted by `published_report_errors`, a published report rejected only
  because its receipt has a later valid descendant, a receipt/outbox pair that blesses bytes
  differing from the embargoed candidate, or publication validation that omits/substitutes the
  complete freeze-fingerprint object while copied fingerprint hashes remain unchanged;
- a missing, late-created, or substituted disposition policy; a policy commitment that differs across
  reserve, fingerprint, run, outcome, terminal event, and report; or a terminal state that differs
  from exact application of the committed bounds to the ordered outcome set;
- a pass-rate comparison that divides or changes under another `Decimal` context, including an exact
  1-of-3 case near a long finite-decimal threshold that must be decided by coefficient/scale cross
  multiplication;
- an adjudication without `post_adjudication`, a `correction_expected: false` branch with any
  corrected report/receipt, a true branch without its direct `corrected_report_recorded` successor,
  a corrected report subject/final hash/commitment/predecessor mapping mismatch, or corrected
  disclosure before its receipt;
- an adjudication append inlining a target/corrected report or corrected subject, omitting/substituting/
  duplicating its control-record descriptor, or a maximum legal target/subject record that cannot fit
  its generated history-reservation witness;
- a public `post_adjudication` exposing `target_private_report_sha256`, or a repository-disclosure
  report exposing runtime-observation hashes, runtime/scoring lease IDs, private ticks, storage-
  reservation plans/receipts/plain digests, or actual staged/reserved/used/remaining record counts or
  bytes;
- a true correction with no deterministic derivation record, unknown/mutated rule or reference-
  executor artifact, manual outcome replacement, input/output hash mismatch, changed candidate/truth/
  freeze/scorer/threshold/terminal disposition, a missing/substituted correction-disclosure-delta
  record, an eligible-20 overall value changing 10 -> 11, any other public K1-K4 numeric delta, a
  published cell of denominator 7 changing 1 -> 6, a wrong smallest comparison universe/complement,
  or a second true correction in one lineage;
- adjudication of a superseded report, correction from anything except the current lineage revision,
  replay/fork/skipped revision, reuse of an old report after an unrelated successor, or a false branch
  that carries the original rather than the current target private report;
- a private/public report divergence, an absent/malformed independently supplied expected private
  commitment, or a public private-report commitment mismatch;
- a non-predeclared disclosure view, non-open eligible denominator below ten, partially published
  `[1,5,5]`/`[3,6,6]` partition, small cell/complement, cross-tab, or differencing attempt;
- an unapproved post-result exclusion; and
- totals that do not reconcile to the eligible denominator.

The late control-plane contracts above additionally require one generated positive/RED matrix; broad
"unsafe disclosure" or "wrong signature" tests do not satisfy it. The matrix must cover:

- exact bidirectional inventory equality for the 13 asymmetric store-attestation purposes and the
  eight non-store FinProof signature purposes, with one positive shape/order fixture per row and
  mutations of purpose, signed projection, version, literal tag, scheme, controller, deployment role,
  key resource/ID/fingerprint, canonical base64 length, signature field presence, reuse outside the
  sole permitted `human_stable_identity`/`owner_curator_non_alias` identity-authority pair, and out-of-
  band trust-root substitution. The paired rows positively reuse only that one key role; sharing either
  with any third signature/store/HMAC purpose rejects. Task 3 verifies deterministic message
  construction, registry/schema/manifest parity and mutation rejection only; Phase 4 must run real
  Ed25519 verification/vectors against independently pinned keys before locked execution;
- checkpoint pin rejection for a self-selected/self-signed key and pre-execution/final-order witness
  substitution, missing immediate provenance, future-object input, dirty/index-only candidate,
  reconstructed later candidate, wrong native OID/tree/path/parent, swapped checkpoint, `G0` omission,
  `G1` fed into its own gate, or use of a final witness during locked claim/execution. The positive
  creates candidate -> provenance -> execution checkout -> `G0`, validates readiness, then records
  gate evidence only in descendant `G1`;
- `release_action_current` generation-zero/reservation/state/current-attestation reconstruction,
  reset/fork/key/
  root/proof/bit-order/capacity/stale-current/CAS-loser/crash/replay mutations, verified-publication
  purpose/tag/scheme `ED25519_VERIFIED_PUBLICATION_V1`/key/fingerprint/projection mutations, and an
  exact 100,002-entry/196-shard maximum readiness-dossier streaming positive (two locked plus 100,000
  sealed) plus entry 100,003,
  shard 197, 513-in-one-shard, wrong shard/list root and every byte-cap-plus-one rejection, and an
  exact three-state `DisclosureOutboxReadTransaction` access positive:
  invalid or absent report fails; canonical report/receipt/outbox durable but no current enable leaf is
  embargoed; current enable plus its exact verified receipt permits controlled exact-byte read, while
  anonymous read additionally requires same-root readiness, completion and exposure. `outbox_read`
  must lose when an authority/lineage/current-resource successor lands before byte return;
- every member and branch of `irreversible_action_authority_binding`: caller digest/kind/lane, complete
  subject, current official/applicable-record state, ordered applicability-list root, read-lock receipt,
  state/guard/binding digest, scheduled-action current freeze basis/bound and conflict CAS. Omission,
  substitution, public copying, a 262,144-byte maximum plus one byte, and a prohibition arriving
  between validation and the irreversible write are all explicit vectors;
- `evaluation_scope_schedule_offset_profile`/ref construction, `evaluation_scope_deadline_transition`
  and `scope_schedule_deadline_close` selection, and exact millisecond-to-monotonic-nanosecond checked arithmetic,
  official-milestone/current-freeze clamp, cross-epoch identity/access context, scope-created/current-
  clock equality, final commit-before-first-deadline, per-entry deadline `-1/equality/+1`, owner expiry,
  ordinary/RC0-child zero-channel audit order, early-P2 no-premature-completion, crash recovery, stale
  stage and every `postfreeze_incomplete_scope_fence` stage. A max four-entry combined scope/slot/store
  CAS is fault-injected at every participant; the result is all authoritative heads or none, with only
  named provisional allocations allowed for a loser, and a fifth/permuted/duplicate entry rejects;
- the blinded `owner_remediation_private_join`: equal low-entropy private inputs under two independently
  generated salts yield unrelated commitments, while missing/nonrandom/public/caller-selected/reused/
  substituted salt, changed request ID/nonce/projection, nonzero pad, wrong length encoding, wrapper or
  projection over cap, and recovery under a different salt reject;
- paired `truth_terminal_deadline_expired` and `authority_conflict_after_truth_commit` witnesses with
  identical public inputs: every non-opaque public event/report/summary/ID byte is identical,
  including the literal `TRUTH_NOT_DELIVERED` category,
  lifecycle/history/report/outbox replication and controlled/anonymous reads are denied at
  `revoked_publication_not_before_tick - 1`, and both guarded enables/reads are eligible only at equality
  or later. Missing/unequal/cross-epoch/private-tick exposure, a cause/tick/bucket marker, caller-
  triggered early release or any direct storage-reader bypass rejects; and
- the disjointness public handle and control-plane public boundary: descriptor/kind/schema/length/record
  ID/SHA exposure, handle reuse/substitution/caller selection, a prior occupied or missing/wrong
  `disjointness_public_handle` nonmembership/membership proof/value, missing same-CAS private-history HMAC
  join, or any path/endpoint/tenant/ACL/private resource/key/credential field in the public control-
  plane role attestation/fingerprint/report/outbox rejects. The complete deployment manifest/pin and
  every ACL-private plan/receipt likewise fail if copied into a public artifact.

Every Task-3 matrix item above is a pure typed deterministic facade/transition simulation: it proves
schema/message construction, exported-API non-bypass, modeled all-or-none writes and rejection of the
named histories. It does not claim physical ACL, store, clock, KMS, signature, network or CAS
enforcement. The Phase-4 gate must repeat the corresponding fault-injection, direct-storage-access,
real-signature, clock/KMS/lease, ACL and concurrent multi-resource tests against the deployed adapters
before any locked/sealed execution.

A required positive ancestry control appends a later valid reservation/continuity successor and
proves that an earlier report remains valid only because its unique matching `report_recorded` or
`corrected_report_recorded` receipt is an ancestor of the supplied current head; a post-outcome-only
chain and equality-only validation must both fail that test.
A required two-phase positive control proves the same embargoed candidate fails published validation
before the CAS, passes only after its exact receipt/outbox record is durable, and fails again under
any candidate-byte mutation.
A required scope-order positive control starts from the initial exact four-entry scope, publishes each
locked checkpoint as historical evidence while completion remains absent, executes ordinal 0, and
then covers separately: parent pass -> unused-child resolution/audit/completion; parent invalidation ->
withdrawal-only adjudication -> resolution/audit/non-PASS completion; parent invalidation -> owner
decline resolution/audit/non-PASS completion; and parent invalidation -> child activation and
report/burn completion. Every incomplete prefix rejects cumulative/release claims, and only a valid
pass branch is accepted by `release_readiness_errors`. A second control starts from authenticated prior-slot closures and
accepts only the corresponding shorter suffix for a new blind principal. A third revalidates the old
locked report after legal completion/exposure descendants while rejecting a substituted or non-
ancestor human head.
A required execution-union positive control runs one max-shaped Phase-2 deterministic-core suite
through request+precommitted-plan binding, dispatch-prepared/`at_local_invoke`, exactly-one local call,
adapter/common-response seal, zero provider observations, and the 10,004-observation bound under the
no-network isolation profile. A second runs the matching max-shaped Phase-3/sealed end-to-end branch
through GET serialization, `at_egress`, provider receipts, and the 30,004-observation bound. Each
passes only its own schema/HMAC/reservation branch; swapping the execution selector/hash/profile,
supplying a plan to end-to-end, omitting the Phase-2 plan, drifting either deterministic fragment, or
injecting/mislabeling a private mount/credential fails before dispatch.
Task 3 deterministic concurrency tests schedule exact adversarial histories in a pure in-memory
transition model: two competing reservation/claim pairs for one slot; transfer versus
`dispatch_prepared`/dispatch commit/ingress; two simultaneous pre-egress failures competing for the
one suite transfer; ordinal-1 recovery versus terminal burn; truth commit racing a late-byte burn
after transfer; outcome -> unrelated reservation before `post_outcome`; `post_outcome` -> unrelated
reservation before the atomic report closure; report/correction closure versus a new sink receipt;
sink checkpoint versus continuity/adjudication; final scope report/burn versus human completion;
scope commitment versus a global closure; private-control pointer append versus ancestor/fork reset;
owner remediation activate versus decline; withdrawal-only parent adjudication versus activate or
decline; activation versus parent adjudication/correction or
current-lineage change; dormant-child claim versus unused-child close; exposure versus activation/
child claim; late sink receipt versus the zero-channel nonmembership close; crash at each
resolution -> reservation -> claim revision boundary; crash at each resolution -> zero-channel audit
-> human-completion boundary;
redemption versus revocation; scoring crash after different private prefixes; durable-clock restart/
epoch rollback; and custodian crash before/after capability terminalization. The model
must reject every dual-success history, prove deterministic ascending case dispatch and one retry,
coalesce same-token late-byte floods, show that only one transition returns a truth capability, and
prove that no `activation_authorized` or `terminal_close_pending_audit` state is externally stranded.
These tests freeze required linearization semantics; they do not prove the Phase 4 store or transport
is atomic. Phase 4 must rerun equivalent integration race tests against the real registry, attempt
outbox, truth store, output sink, and disclosure outbox before any locked/sealed execution.

### 10.4 Independent review loop

Implementation planning must split work into non-overlapping ownership units for schemas/seed
migration, coverage, governance, and handoff/docs. Fan-out is allowed only when agents do not edit
the same file or depend on uncommitted sibling output. Each unit receives:

1. an oracle author that records expected RED behavior without production edits;
2. an implementer that performs the smallest RED/GREEN change;
3. an independent spec reviewer that does not run shell commands or mutate files; and
4. an independent execution verifier in a fresh detached checkout.

The repository quality loop's three-candidate limit applies. A reviewer must report
BLOCKER/HIGH/MEDIUM/LOW findings with exact evidence and smallest correction. “AAA,” production
ready, competition ready, or global PASS cannot be claimed from Task 3.

## 11. File scope

After owner written-spec approval, the prerequisite first checkpoint is to create, hash, review, and
commit
`docs/superpowers/plans/2026-08-08-preflight-task3-evaluation-control-plane.md` before any
implementation or RED-oracle edit. That planning checkpoint edits only the plan and its STATUS
evidence. The plan must enumerate the exact writable paths below, bind this design's approved commit/
SHA-256, freeze the canonical brief/hash and candidate base, and explicitly
supersede only Task 3 of the historical 2026-08-07 preflight plan. No implementation path may be
edited while this planning checkpoint is uncommitted or under review.

The first post-plan implementation checkpoint is metadata-only TDD: add a focused failing handoff test
that requires this design and the dated plan, observe the intended RED, then update
`tools/verify_handoff.py` and `HANDOFF_PACKAGE_MANIFEST.md`, run both normal and `python -S -B`
handoff verification, update STATUS, and commit. No schema, seed, coverage, control-plane behavior, or
other RED oracle may be edited until that registration checkpoint is committed. This makes the plan
the prerequisite without asking an uncommitted plan to register itself.

The implementation plan may create:

- `docs/superpowers/plans/2026-08-08-preflight-task3-evaluation-control-plane.md`;
- `schemas/evaluation_common.schema.json`;
- `schemas/aggregate_evidence.schema.json`;
- `schemas/evidence_package.schema.json`;
- `schemas/golden_expected_result.schema.json`;
- `schemas/golden_expected_answer.schema.json`;
- `schemas/evaluation_suite_manifest.schema.json`;
- `schemas/evaluation_suite_history_attestation.schema.json`;
- `schemas/evaluation_disposition_policy.schema.json`;
- `schemas/evaluation_freeze_fingerprint.schema.json`;
- `schemas/evaluation_runtime_attestation.schema.json`;
- `schemas/evaluation_lifecycle_event.schema.json`;
- `schemas/evaluation_private_control_bundle.schema.json`;
- `schemas/evaluation_report.schema.json`;
- `config/question_coverage.yaml`;
- `config/question_coverage.lock.json`;
- `config/evaluation_governance.yaml`;
- `config/evaluation_governance.lock.json`;
- `tools/build_coverage_report.py`;
- `tools/build_seed_migration_manifest.py`;
- `tools/evaluation_models.py`;
- `tools/evaluation_contracts.py`;
- `tools/evaluation_control.py`;
- `tools/evaluation_control_core/__init__.py`;
- `tools/evaluation_control_core/canonical_io.py`;
- `tools/evaluation_control_core/storage_reservations.py`;
- `tools/evaluation_control_core/history_registry.py`;
- `tools/evaluation_control_core/runtime_lifecycle.py`;
- `tools/evaluation_control_core/remediation.py`;
- `tools/evaluation_control_core/reporting.py`;
- `tests/contract/test_evaluation_contracts.py`;
- `tests/contract/test_evaluation_models.py`;
- `tests/contract/test_question_coverage.py`;
- `tests/contract/test_evaluation_governance.py`;
- `tests/contract/test_evaluation_control_canonical.py`;
- `tests/contract/test_evaluation_control_reservations.py`;
- `tests/contract/test_evaluation_control_history.py`;
- `tests/contract/test_evaluation_control_lifecycle.py`;
- `tests/contract/test_evaluation_control_remediation.py`;
- `tests/contract/test_evaluation_control_reporting.py`;
- `tests/golden/legacy_seed_migration_manifest.json`; and
- `tests/evaluation/README.md`.

It may modify:

- `schemas/golden_case.schema.json`;
- `schemas/evidence_record.schema.json`;
- `tests/golden/seed_cases.jsonl`;
- `tests/golden/README.md`;
- `tests/contract/test_handoff_package.py`;
- `docs/07_TESTING_AND_EVALUATION.md`;
- `docs/09_RISK_REGISTER.md`;
- `docs/10_DECISION_LOG.md`;
- `docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md`;
- `docs/implementation/PHASE_GATES.md`;
- `docs/implementation/QUALITY_LOOP.md`;
- `docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md`;
- `docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md`;
- `docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md`;
- `tools/verify_handoff.py`;
- `HANDOFF_PACKAGE_MANIFEST.md`; and
- `docs/implementation/STATUS.md`.

No field, metric, planner, answer, quality, dataset, runtime, production source, dependency,
lockfile, source-material byte, or `START_HERE.md` change is authorized by this design. A new need
outside the list requires a new frozen brief and owner approval before editing.

## 12. Documentation reconciliation

The Task 3 implementation updates repository prose without creating a second authority hierarchy:

- `docs/07_TESTING_AND_EVALUATION.md` becomes the canonical operational explanation of lane
  eligibility, precommitted reserve-batch activation, globally claimed truth-release slots,
  fixed private-storage reservation and streamed snapshot/history readers, private human-governance
  review/scope/exposure fencing, checkpoint-discriminated deterministic-core/end-to-end execution,
  candidate isolation and resolved mount/credential attestation,
  sequential multi-case run binding, private per-case attempt sealing, public candidate/outcome-set
  commitments, persistent retired-token fencing, strict pre-egress-only same-suite transfer,
  terminal burn without hidden-suite replacement, two-way truth-capability terminalization, pre-decryption truth-release
  consumption, AEAD key/nonce registries and all-or-none recovery/session transactions, continuous
  runtime/scoring leases, CAS-updated history, the separate private sink registry and unconditional
  audit closure, post-outcome recording, exclusion approval, original-to-corrected K5 delta gating,
  disclosure suppression, denominator, and aggregate-evidence evaluation. It normatively consumes
  every Section 8 contract rather than treating this list as exhaustive;
- `docs/09_RISK_REGISTER.md` adds release-blocking risks for evaluation leakage, oracle coupling,
  single-reviewer bias, suite reuse/derivation, history-genesis reset/stale-head fork, HMAC replay,
  human-principal alias/scope/exposure races, private-storage under-allocation or stale snapshot head,
  AEAD key/nonce reuse or partial recovery/session persistence,
  execution-contract substitution or candidate truth-store/mount/credential injection,
  concurrent truth-release claims, unsealed multi-response selection, stale-read/decryption TOCTOU,
  live capability after terminal reporting, dispatch-to-retry ambiguity, unfenced late output,
  sink-registry reset or missing unconditional audit closure, unbounded infrastructure retry,
  original-versus-corrected small-cell differencing,
  fingerprint drift, denominator manipulation, and aggregate proof without source evidence;
- `docs/10_DECISION_LOG.md` records the owner-approved strict migration, one-use truth-release rule,
  independent-human migration/custody availability, precommitted disjoint reserve, global
  pre-decryption consumption claim and atomic truth-release commit, two-way terminal truth receipt,
  persistent transport-fenced pre-egress retry ledger with no suite replacement, one
  result-bearing locked disclosure per named checkpoint, one result-bearing sealed disclosure per
  candidate cycle with exactly two preallocated candidate cycles (one conditional remediation child)
  per authenticated organizer opportunity and no third/reset/replacement, while recording that this
  is an owner-approved internal remediation budget—not an organizer grant—and any first-ranked
  official one-attempt/no-correction restriction overrides it and stops execution; `D-017` delayed
  ordered Phase-4 historical replay of the pinned Phase-2/Phase-3 candidates with no Phase-2-result
  guidance/gating of Phase 3; checkpoint-discriminated execution/
  isolation contracts, private human-governance and
  output-exposure fencing, fixed storage/snapshot
  reservation, private sink/audit closure, AEAD nonce uniqueness, correction-delta K5, overall K=10
  and cell K=5 disclosure floors, and Task 3/Phase 4 boundary;
- `docs/implementation/QUALITY_LOOP.md` aligns its sealed freeze with code, model, prompt, config,
  schema, source/artifact, dependency, and image identity;
- `docs/implementation/PHASE_GATES.md` normatively incorporates the updated Phase 4 plan and requires
  the Task 3 governance lock/contracts plus real Phase 4 custodian, secret-HMAC, atomic-CAS,
  one-use-truth, race, attrition, K10/K5 disclosure, and external-boundary verification before its
  existing “Phase 4 gate — All must pass” readiness statement can be satisfied;
- the Phase 2 plan exports the exact `AnswerService.answer_plan` adapter boundary, requires structural/
  byte parity with the frozen deterministic request/result fragments and common response mapping,
  instruments the local invocation/output-buffer receipt hooks, and makes the deterministic-core
  checkpoint runnable under the closed no-network candidate-isolation profile;
- the Phase 3 plan consumes full canonical expected plans rather than partial plan objects;
- the Phase 4 plan normatively consumes every Section 8 contract. It may derive new open cases from
  visible seeds but may not copy, relabel, or
  re-review them into locked/sealed truth; it must implement the private fingerprint/history,
  immutable genesis dossier, predecessor-only private history commitment, atomic registry-head CAS,
  delayed one-suite reserve activation, global pre-truth claim/transport-close/transfer/burn,
  both execution-contract branches and the real candidate isolation/mount/credential/IPC boundary,
  inherited retired-token ledger, private per-case attempt sealing and public set sealing,
  pre-decryption truth-release commit/
  one-use capability terminalization, public event-binding variants, fixed storage reservation and
  streamed private-control/history readers, the human-governance/exposure registry, the private sink
  registry and unconditional audit closure, AEAD nonce/recovery/session atomicity, continuous runtime/
  scoring leases, post-outcome/adjudication receipts, correction-delta K5, evidence commitment,
  secret verification, and private-to-public report projection interfaces; and
- the new dated Task 3 execution plan explicitly supersedes only Task 3 of the 2026-08-07
  controlling preflight plan; the historical plan remains unchanged for auditability.

## 13. Stop conditions

Stop instead of guessing when:

- any official catalog count or pair differs from the verified 207-column snapshot;
- seed migration would require a new product ID, value, rank, answer fact, or human truth decision;
- a planner alias or candidate source mapping lacks the semantics required for `supported`;
- an unresolved schema reference or bootstrap/full-validator disagreement appears;
- a locked/sealed payload or secret is found in the repository;
- the independent human can no longer remain blind to implementation output;
- a freeze component cannot be identified or hashed;
- a lifecycle transition, denominator, or report cannot be reconciled;
- the authoritative durable clock instance/epoch cannot be restored without resetting or extending a
  persisted post-commit deadline;
- a claimed organizer release-cycle authorization cannot be verified against a first-ranked official
  source by its declared machine method or the required recorded human check;
- the global history genesis/current head, monotonic private-control pointer, consumption-slot claim,
  transport-close/late-byte fence, retired-token ledger, complete candidate-attempt-set seal, truth-
  release commit, truth-capability terminal receipt, or post-outcome successor cannot be externally
  verified and atomically advanced;
- a RED fails for an unexplained or infrastructure reason; or
- implementation needs an unapproved file or dependency.

## 14. Acceptance criteria

Task 3 is accepted only when current-task evidence proves all of the following:

1. the exact dated Task 3 execution plan was hashed, reviewed, and committed before any implementation
   or RED-oracle edit; the first post-plan metadata checkpoint then observed the focused handoff RED
   and registered this design/plan before any substantive schema or control-plane behavior edit;
2. all registered schemas are valid Draft 2020-12 documents with unique absolute IDs and a closed
   offline reference graph, and every public/cross-module Pydantic root or named `$def` has strict,
   deep-immutable, no-coercion schema/model dump-roundtrip parity;
3. all 13 migrated seeds validate, retain their visible AI-scaffold/open-regression status, and
   bind the exact LF base-blob inventory, recompute all 302 closed transformations exactly once,
   and carry independent `faithful_migration_only` review for every non-exact semantic wrap without
   elevating seed truth status;
4. removal of canonical `filters`, numeric substitution for an exact decimal, and removal of an
   evidence requirement each fail for the intended reason, while float/`Decimal` values in
   evaluation QueryPlan/evidence objects and lone surrogates in values/keys fail the canonical-domain
   overlay with stable UTF-8-safe paths before serialization; nested mutation cannot change a frozen
   value/digest and type coercion is rejected;
5. a valid evidence package proves aggregate source/artifact/plan binding, execution stages, result
   commitment, calculations, exclusions, resolved bidirectional claim/EvidenceRecord linkage, and
   the rule that aggregate proof is never sole support for a material source-derived claim;
6. the deterministic coverage report contains exactly the 207 verified pairs and explicitly
   reports every required concept and planner alias target;
7. `risk_grade` and every other unresolved named concept cannot be reported as supported;
8. pure validators and deterministic adversarial fixtures reject missing, inconsistent, or replayed
   modeled evidence for truth leakage, forged fingerprints, cross-suite
   overlap/derivation, genesis substitution, stale-head forks, optional stopping/release-cycle reset,
   slot-preparation reset/replacement, private-control pointer rollback/fork/ancestor omission,
   output-exposed-human reuse, out-of-order reserve activation,
   illegal transitions, unapproved exclusions, concurrent global
   consumption claims, suite-local truth access without the claim and atomic truth-commit winner,
   unsealed or multiply selectable candidate output, stale-read truth-release races, duplicate
   consumption or truth-token terminalization, lost retired-token ledger, post-dispatch retry,
    hidden-suite replacement, unfenced or late old-token output, more than one pre-truth infrastructure retry,
    post-commit crash replay, run/request replay, missing post-outcome history, truth-capability
    terminal-receipt or truth-payload/AEAD nonce-registry mismatch, fingerprint/runtime/scorer drift,
    checkpoint execution-contract substitution, deterministic adapter/local-invocation mismatch,
    candidate-isolation mount/credential/IPC substitution, redirect/automatic retry, unsafe
   logs/caches/provider retention, alternate-model egress, durable-clock/deadline replay,
   output-sink-checkpoint races, partial-score finalization,
   public/private event-binding mismatch, concealed or falsely corrected
   adjudication, attrition/denominator manipulation, private/public report divergence, and unsafe
   disclosure views, while retaining validity of a historical report only when its unique matching
   original/corrected report receipt is an ancestor of the valid current head; the updated Phase 4
   gate separately requires real integration evidence for secret stores, ACLs, CAS/egress, provider,
   log/cache, and truth-access enforcement and Task 3 does not claim to observe an unlogged real-world action;
9. synthetic secret-backed tests verify the exact closed HMAC registry and messages for
   `evidence-package`, `case-set`, `suite-history`, `history-attestation`,
   `organizer-cycle-authorization`, `owner-remediation-authorization`, `disposition-policy`, `exclusion`,
   `evaluation-storage-reservation`, `case-attempt-binding`,
   `case-dispatch-receipt`, `candidate-attempt`, `candidate-attempt-set`, `runtime-observation`, `infrastructure`,
   `attempt-transport-close`, `late-output-receipt`, `output-sink-ledger`, `retired-token-ledger`,
   `suite`, `run-binding`, `recovery-record`, `truth-capability-terminal-receipt`, `outcome-set`,
   `corrected-outcome-set`, `private-report`, and `report-attestation`; the externally supplied expected private-report
   commitment; the immutable global
   history genesis, one-suite reserve activation, pre-truth claim/transport-close/transfer/burn,
   truth-release-commit fencing, and eligibility-to-post-outcome/adjudication successors; the
   predecessor-only private-history
   commitment; plus the non-self-referential migration-review/coverage/report/logical-proof/event
   hashes; synthetic AEAD/registry tests additionally verify the exact two-purpose key-resource
   separation, pinned no-reset nonce-registry, slot-preparation-registry, and private-control pointer
   resource/genesis/head lineages, the strict signed pointer-attestation projection/digest/prior chain,
   one-use receipts, descriptor/AAD/ciphertext binding, and all-or-none truth-commit/redemption
   transactions. A separate generated acceptance inventory equals exactly the 13 store-attestation
   purposes `private-control-pointer`, `suite-history-current`, `human-governance-current`,
   `sink-registry-current`, `slot-preparation-current`, `aead-nonce-registry-current`,
   `candidate-ingress-current`, `owner-remediation-signer-current`, `official-instruction-current`,
   `trusted-clock-current`, `submission-state-current`, `identity-authority-current`, and
   `release-action-current`, and exactly the eight non-store purposes
   `deployment_trust_anchor_manifest`, `evaluation_deployment_trust_anchor_pin`,
   `checkpoint_candidate_pin`, `official_instruction_semantic_review`,
   `owner_remediation_public_approval`, `human_stable_identity`, `owner_curator_non_alias`, and
   `verified_published_report`. It proves bidirectional registry/schema/manifest/fixture parity,
   deterministic signed-projection/tag/scheme/controller/key-role construction, base64 signature shape,
   the sole positive identity-authority pair plus rejection of every other cross-row/store/HMAC reuse,
   trust-root separation and every Section 10.3 mutation; Phase 4, not this dependency-free Task-3
   fixture, supplies real Ed25519 verification. The same acceptance run executes the named checkpoint-
   G0/G1, release-action/verified-publication/three-state AccessGate, irreversible-authority-binding,
   max-four combined-scope CAS, schedule boundary/postfreeze-fence, blinded-private-join, revoked-cause
   byte-and-availability noninterference, disjointness-handle and public-boundary controls from the
   generated late-control-plane matrix;
10. the two locked checkpoints and one sealed release-candidate checkpoint type—with exactly two
    preallocated candidate-cycle ordinals, the second the sole conditional remediation child—are
    machine-readable and consistent across config, schemas, tests, and documentation, with Phase 2 mapped only to the
    deterministic-core request+plan adapter and Phase 3/sealed mapped only to the end-to-end GET
    contract under their exact isolation profiles;
11. both generated lock files equal canonical regeneration, bind the exact YAML bytes, and pass
   dependency-free structural verification;
12. both normal and `python -S -B` handoff verification pass;
13. source audit and schema-catalog checks still report 145,393 rows at snapshot `2026-07-11` and
    207 columns;
14. focused task-local checks and all six repository-required commands have current observed results:
    `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src tests tools`,
    `uv run pytest -q`, `uv run python tools/audit_source_data.py --check`, and
    `uv run python tools/verify_handoff.py`; any new/unexplained failure stops, while an exactly
    reproduced pre-existing failure is recorded as diagnostic non-PASS debt;
15. independent spec and execution verifiers report no unresolved BLOCKER or HIGH finding; every
    accepted MEDIUM or Phase-4 implementation detail is named in Section 15 and does not weaken an
    official rule, submission-freeze rule, data-fidelity invariant, or security boundary;
16. the exact candidate diff contains only owner-approved paths and exact-root post-commit
    `git status --short` proves both worktree and index clean; and
17. status records every command/result, diagnostic global-gate debt, accepted candidate and final
    commit hashes, and the exact next task.

Running and recording the required global commands is mandatory evidence; it is not a global-
readiness claim. Global Ruff, mypy, coverage, lockfile, production, release, competition, and AAA
readiness remain outside this acceptance claim, and reproduced global quality debt stays explicitly
non-PASS until Preflight Task 5 closes it.

## 15. Implementation backlog and residual risks

The following accepted MEDIUM/Phase-4 items do not block this written-spec freeze and must not be used
to relax its invariants:

- Store-attestation row keys may sign successive valid generations and, for the two dynamic rows,
  valid per-run instances of that same row. The table's "no reuse" wording means no cross-purpose/
  cross-row key reuse, no resource/genesis reset and no in-design rotation. Implementation tests must
  preserve that interpretation without creating another registry or signature purpose.
- Task 3 proves only typed/model transaction semantics. Phase 4 must supply real Ed25519, ACL, KMS,
  monotonic-clock, store-CAS, concurrent-fault and direct-storage-bypass evidence against deployed
  adapters before any locked/sealed execution.
- The 100,002-entry sharded release-validation maximum is a correctness cap, not a performance claim.
  Phase 4 must measure bounded streaming memory/time and provision the custodian validation workspace
  without changing entry semantics, counts or public disclosure.
- The common revoked-publication not-before policy is frozen; Phase 4 still must operationally schedule,
  monitor and recover that guarded release path without exposing private ticks, cause-dependent timing
  or an alternate raw-storage reader.
- Real deployment resource/key IDs, fingerprints and deployment-global g0 checkpoints remain Phase-4
  provisioning inputs under the exact frozen purpose rows. The two dynamic g0 resources remain claim-
  created as specified.
- The current `submission` action remains an internal immutable package/intention only. A real organizer
  send requires the separately frozen authenticated idempotent adapter or explicit manual handoff
  already required by Section 8; ambiguous external status remains fail-closed.

Any backlog item that later proves to change an official requirement, cryptographic separation,
truth-access boundary, one-use budget, disclosure floor, submission freeze or source-fidelity rule is
promoted to BLOCKER/HIGH and requires a new owner-approved frozen design before implementation.

## 16. Non-goals

Task 3 does not:

- generate or store locked/sealed questions or answers;
- use an LLM to create evaluation truth;
- choose an external secret-store vendor;
- instantiate the custodian's private suite-history registry or verify its real HMACs;
- implement ACLs, audit-log infrastructure, or the one-time runner;
- create the independent reference executor or scoring engine;
- set competition-quality thresholds before the metric denominator exists;
- repair field/metric/planner registries or decide unresolved financial semantics;
- change production behavior, API behavior, prompts, HCX integration, or source data;
- execute Phase 4 evaluation; or
- claim that any visible AI seed is a human-reviewed benchmark.
