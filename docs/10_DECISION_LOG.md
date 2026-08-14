# Decision Log

Statuses:

- `FROZEN`: implementation must follow unless superseded by official instruction
- `OFFICIAL_OVERRIDE`: official instruction supersedes prior design
- `OPEN_OFFICIAL`: awaiting organizer answer; current safe default remains labeled
- `PROPOSED`: not yet authorized for core behavior
- `OPEN_INTERNAL`: conflicting repository contracts need an explicit project decision; this status has no behavioral authority
- `RESOLVED_INTERNAL`: an internal contract conflict was explicitly resolved and linked to a frozen decision
- `RESOLVED_MIGRATION`: a non-product handoff discrepancy was corrected without choosing product behavior

## Frozen decisions

| ID | Date | Status | Decision | Rationale |
|---|---|---|---|---|
| D-001 | 2026-08-07 | FROZEN | Product name is FinProof | concise evidence/verification identity |
| D-002 | 2026-08-07 | FROZEN | HCX plans; deterministic code executes | numeric/query reliability and auditability |
| D-003 | 2026-08-07 | FROZEN | Source Fidelity is a global invariant | official data is evaluation reference |
| D-004 | 2026-08-07 | FROZEN | public-fund default grain is `itm_no` | 95,619 rows are item-attribute pairs, not independent products |
| D-005 | 2026-08-07 | FROZEN | plain ETF excludes ETN | user/product-type semantics |
| D-006 | 2026-08-07 | FROZEN | current = 2026-07-11 snapshot | official fixed snapshot |
| D-007 | 2026-08-07 | FROZEN | `pd_tr_yn = 0` means not suspended | supplied schema semantics and audit |
| D-008 | 2026-08-07 | FROZEN | zero policy is operation-specific | preserve official values without unsafe comparison |
| D-009 | 2026-08-07 | FROZEN | no integrated cross-currency AUM rank by default | incompatible units without FX basis |
| D-010 | 2026-08-07 | FROZEN | exact identifier links only auto-merge | avoid false entity consolidation |
| D-011 | 2026-08-07 | FROZEN | no free-form Text-to-SQL | injection and semantic reliability |
| D-012 | 2026-08-07 | FROZEN | deterministic renderer is default | stability, latency, exact claims |
| D-013 | 2026-08-07 | FROZEN | conditional dual-lens only when interpretation changes | useful without making every answer verbose |
| D-014 | 2026-08-07 | FROZEN | DuckDB + Parquet default runtime data architecture | small read-heavy snapshot and reproducibility |
| D-015 | 2026-08-07 | FROZEN | evaluation mode has no live external data | stable official-reference answers |
| D-016 | 2026-08-07 | FROZEN | `think_trace` is execution/tool summary | reproducible, bounded, safe output |
| D-017 | 2026-08-13 | FROZEN | Production XLSX ingestion accepts only a manifest/catalog-verified source descriptor; raw rows preserve checksum, snapshot, exact row/cell location, raw payload/value, and an explicit optional cell applicable date | prevents unverified files or caller-invented lineage from entering normalization and resolves A-002 |
| D-018 | 2026-08-14 | FROZEN | `SourceFileManifest.load` validates JSON structure and metadata; `SourceFileManifest.verify(base_dir)` exclusively validates manifest-relative path containment and emits `PATH_ESCAPE` | keeps metadata parsing independent from a caller-supplied source root and resolves the Task 2-versus-Task 3 plan conflict without weakening fail-closed path validation |
| D-019 | 2026-08-14 | FROZEN | OPC package-absolute internal worksheet targets such as `/xl/worksheets/sheet1.xml` are accepted only after strict canonicalization to an internal ZIP member; `..` escape, URI schemes or external URLs, external relationship mode, and host-filesystem interpretation remain prohibited | all four checksum-verified official workbooks use the package-absolute internal form, so blanket rejection would reject official inputs while strict ZIP-internal canonicalization preserves the source-security boundary |
| D-020 | 2026-08-14 | FROZEN | Validated source-catalog metadata is deeply immutable and predictably serializable; every parsed XLSX XML part rejects DTD/entity declarations before consuming values or attributes and requires its exact root/direct metadata structure; D-019 target checks apply to raw and percent-decoded text with canonical round-tripping before ZIP-member access | closes mutation, XML attribute/entity, ambiguous metadata, and post-decoding canonicalization gaps without changing official values, bounded worksheet streaming, or the approved canonical `/xl/...` policy |
| D-021 | 2026-08-14 | FROZEN | The canonical persisted quality-issue JSON contract is exactly `DataQualityIssue.model_dump(mode="json")`, including the complete nested `SourceCellLocator`; pure normalization emits `first_detected_at=null`, the first artifact persistence supplies an injected timezone-aware UTC value whose JSON form ends in `Z`, and operational timestamps do not enter logical reproducibility hashes | resolves the quality-issue portion of A-011 without creating a second drifting DTO or preempting the later evidence, golden-case, and metric contracts |
| D-022 | 2026-08-14 | FROZEN | A Task 5 build receives one injected UTC persistence timestamp for manifest, Bronze load, and D-021 issue persistence; physical file/database hashes prove generation integrity, while canonical table, semantic-report-ID, and manifest logical hashes exclude operational/output-path/physical metadata. Verification recomputes Parquet/report/overall logical identity, timestamp consistency, and bounded exact DuckDB-to-Parquet content. Evaluation requires the packaged expected logical contract; only a non-packaged, unpublished, no-write candidate builder may omit that comparison while bootstrapping an absent baseline and must refuse once it exists. Publication is a guarded stage/verify/backup/rename transaction with pre-commit rollback; post-commit cleanup atomically tombstones the old backup before recursive deletion and never rolls back the verified new target. Runtime `artifacts/` are untracked. | makes logical reproducibility compatible with operational provenance, resolves first-baseline bootstrap without creating an evaluation bypass, rejects same-count substitution, and prevents unsafe deletion or partial publication |
| D-023 | 2026-08-14 | FROZEN | Task 5 materializes only generic Bronze source-column/row/cell tables; wide typed Silver bond, domestic-listed, overseas-listed, fund-item, and fund-attribute tables with canonical strict-model `record_json`; canonical D-021 quality issues; and exact-link plus exact-link-evidence Gold tables. The only automatic link rule v1.0.0 joins the exact untrimmed domestic ETF `pd_itm_no` to the public-fund item representative `ksd_itm_no`, emits one item-grain link with the left locator and every equivalent right locator, and blocks one-to-many conflicts. Metric, family, eligibility/state, alias/fuzzy, search, and runtime evidence tables remain deferred. | freezes a source-faithful Phase 1 artifact boundary without inventing Phase 2 policy or converting repeated public-fund attribute evidence into duplicate products |
| D-024 | 2026-08-15 | FROZEN | Task 5 verification is deliberately capability-staged. Checkpoint 2 owns strict manifest/report models (including manifest UTC shape), canonical hashing primitives, one descriptor-bound recursive physical inventory, and an internal verification kernel exercised only with synthetic closed ports; it neither exposes `ArtifactManifest.verify` nor creates `VerifiedArtifactSet`. Checkpoint 3 supplies the frozen table registry, the Bronze/quality timestamp-neutral logical projections, and reopened Parquet table verifier. Checkpoint 5 supplies D-021 persistence plus operational timestamp/quality-relation verification and the quality-summary producer; Checkpoint 6 completes source-audit semantic content after exact links. Checkpoint 7 supplies the concrete report/database ports, the packaged-comparator implementation, complete operational timestamp/link rechecks, and authorization-independent publication state-machine mechanics; while the official expected source/resource is deliberately absent, only D-022's guarded repository candidate may return a strict core logical contract, and it remains unpublished/no-write. No CP7 target-recognition or publication path accepts a core result. Checkpoint 8 alone installs the independently approved expected source/resource, activates the expected route, exposes `ArtifactManifest.verify`, wires publication/recognition exclusively to the expected-accepted trusted result, and creates the first public `VerifiedArtifactSet`. Broader prose saying that a manifest “verifies” is a final Task 5 invariant, not permission to implement a later capability or bypass the absent baseline early. | resolves the conflict between the final verification contract, the eight-checkpoint TDD sequence, D-022, and the rule that official expected bytes do not exist before Checkpoint 8, while preventing a physically/core-checked tree from being mislabeled or published as an expected-accepted trusted artifact set |

## Open official questions

| ID | Status | Question | Current safe default |
|---|---|---|---|
| Q-001 | OPEN_OFFICIAL | What is the expected public-fund answer grain in hidden evaluation? | `itm_no` based on schema PK and duplicate analysis |
| Q-002 | OPEN_OFFICIAL | Should recorded zero fee/tracking/return values be treated literally for rank scoring? | preserve literal result and add comparison/tie policy |
| Q-003 | OPEN_OFFICIAL | Does bond “buyable” mean positive quantity only or maturity/state validated? | provide source and validated counts when material |
| Q-004 | OPEN_OFFICIAL | What exact content/length is expected in `think_trace`? | deterministic execution summary |
| Q-005 | OPEN_OFFICIAL | What are API timeout, concurrency, retry, and response-size limits? | bounded conservative defaults; tune after answer |
| Q-006 | OPEN_OFFICIAL | Which HyperCLOVA X models/features are enabled for team accounts? | planner adapter with structured JSON preference and validated fallback |
| Q-007 | OPEN_OFFICIAL | Are JSON-serialized strings accepted in context/trace fields? | compact string as shown by response field types |
| Q-008 | OPEN_OFFICIAL | Is identical-image restart/failover allowed after freeze? | prepare immutable redundancy and avoid behavior change |
| Q-009 | OPEN_OFFICIAL | How are hidden answers matched: exact whole-string/JSON serialization, normalized text, or semantic scoring? | keep all output deterministic and serialization stable; do not optimize to an unconfirmed matcher |
| Q-010 | OPEN_OFFICIAL | What HTTP status and response body are required for request-validation failures outside the successful five-string response? | use the framework's bounded standard validation response, subject to organizer confirmation |

## 2026-08-13 macOS handoff audit records

These records track contradictions found while reading the entire transferred package. An `OPEN_INTERNAL` row blocks only the listed affected task, not earlier unrelated work. Phase 1 Task 1 can begin now; it must add the missing CI, pre-commit, and environment-template files under TDD.

| ID | Status | Conflict or gap | Resolve before | Safe action until resolved |
|---|---|---|---|---|
| A-001 | OPEN_INTERNAL | `aggregate` is a supported intent, but QueryPlan has no typed aggregation function, target, grouping, or output contract. | Phase 2 Task 1/3 | do not implement aggregate planning or compilation |
| A-002 | RESOLVED_INTERNAL | D-017 and `docs/superpowers/specs/2026-08-13-phase1-task2-source-ingestion-design.md` freeze the complete Task 2 raw-lineage and verified-reader boundary; Phase 1 Task 2 implements that boundary in commits `c711623` through `f4d49cc`. | Phase 1 Task 2 | implemented under D-017; preserve the verified-descriptor and complete raw-lineage contract in later producers/consumers |
| A-003 | OPEN_INTERNAL | Overseas-listed and public-fund product-specific eligibility rules are incomplete. | Phase 2 Task 5 | do not infer eligibility from generic status fields |
| A-004 | OPEN_INTERNAL | Cache-key prose/tests disagree on argument order and inclusion of artifact, rating, quality, and execution-mode versions. | Phase 3 Task 4 | disable or defer result caching |
| A-005 | OPEN_INTERNAL | The release plan builds/verifies a manifest before the final covered commit/tag, which would stale the manifest. | Phase 4 Task 5 | do not freeze or publish a release manifest |
| A-006 | OPEN_INTERNAL | Per-product top-k followed by currency/policy partitioning has no defined application order. | Phase 2 Task 3/5 | do not combine ambiguous partitions into one rank |
| A-007 | OPEN_INTERNAL | Operational endpoints differ between `/health/live` + `/health/ready` and `/health` + `/ready`. | Phase 3 Task 3 | implement only the official `/answer` contract until resolved |
| A-008 | RESOLVED_MIGRATION | The original manifest claimed CI/environment templates that were absent. The manifest/start guide now state the files are pending. | Phase 1 Task 1 | create and test the three missing templates in Task 1 |
| A-009 | OPEN_INTERNAL | All 13 seed `expected_plan` objects omit canonical QueryPlan-required fields. | Phase 4 Task 1, or earlier if reused | treat seeds as non-canonical AI handoff examples only |
| A-010 | OPEN_INTERNAL | Seed fields `return_1d`/`risk_grade` and seven registered metrics are unreachable through the field registry. | Phase 2 Task 1 | reject unreachable fields rather than bypassing registries |
| A-011 | OPEN_INTERNAL | D-021 resolves the quality-issue JSON portion. The later evidence and golden-case schemas and metric entries still do not enforce every frozen lineage, quality, and version field; the Task 2 raw-lineage boundary remains implemented under D-017. | Phase 2 Task 1/6 and Phase 4 Task 1 | use only the D-021 quality contract now; resolve each remaining evidence/golden/metric contract before its first producer or consumer is implemented |
| A-012 | OPEN_INTERNAL | Planned provider-compliance scanning is narrower than the competition's ban on every non-HCX generative provider. | Phase 3 Task 1 and Phase 4 Task 4 | keep production dependencies provider-free except HCX |
| A-013 | RESOLVED_MIGRATION | Hidden-answer matching and request-validation questions were missing from this log. | organizer response | tracked as Q-009 and Q-010 above |
| A-014 | OPEN_INTERNAL | Some Phase 3/4 plan steps create behavior/configuration before their failing test. | before each affected Phase 3/4 task | rewrite those task steps into strict red-green-refactor order |

## How to add an official answer

Add a dated `OFFICIAL_OVERRIDE` row containing the exact source/channel and affected config/tests. Never edit history to hide the previous decision.
