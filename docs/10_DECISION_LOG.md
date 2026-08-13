# Decision Log

Statuses:

- `FROZEN`: implementation must follow unless superseded by official instruction
- `OFFICIAL_OVERRIDE`: official instruction supersedes prior design
- `OPEN_OFFICIAL`: awaiting organizer answer; current safe default remains labeled
- `PROPOSED`: not yet authorized for core behavior
- `OPEN_INTERNAL`: conflicting repository contracts need an explicit project decision; this status has no behavioral authority
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
| A-002 | OPEN_INTERNAL | Planned SourceRow/evidence locators do not carry every Source Fidelity checksum/snapshot/applicable-date field. | Phase 1 Task 2 | preserve raw inputs; do not freeze a weaker lineage model |
| A-003 | OPEN_INTERNAL | Overseas-listed and public-fund product-specific eligibility rules are incomplete. | Phase 2 Task 5 | do not infer eligibility from generic status fields |
| A-004 | OPEN_INTERNAL | Cache-key prose/tests disagree on argument order and inclusion of artifact, rating, quality, and execution-mode versions. | Phase 3 Task 4 | disable or defer result caching |
| A-005 | OPEN_INTERNAL | The release plan builds/verifies a manifest before the final covered commit/tag, which would stale the manifest. | Phase 4 Task 5 | do not freeze or publish a release manifest |
| A-006 | OPEN_INTERNAL | Per-product top-k followed by currency/policy partitioning has no defined application order. | Phase 2 Task 3/5 | do not combine ambiguous partitions into one rank |
| A-007 | OPEN_INTERNAL | Operational endpoints differ between `/health/live` + `/health/ready` and `/health` + `/ready`. | Phase 3 Task 3 | implement only the official `/answer` contract until resolved |
| A-008 | RESOLVED_MIGRATION | The original manifest claimed CI/environment templates that were absent. The manifest/start guide now state the files are pending. | Phase 1 Task 1 | create and test the three missing templates in Task 1 |
| A-009 | OPEN_INTERNAL | All 13 seed `expected_plan` objects omit canonical QueryPlan-required fields. | Phase 4 Task 1, or earlier if reused | treat seeds as non-canonical AI handoff examples only |
| A-010 | OPEN_INTERNAL | Seed fields `return_1d`/`risk_grade` and seven registered metrics are unreachable through the field registry. | Phase 2 Task 1 | reject unreachable fields rather than bypassing registries |
| A-011 | OPEN_INTERNAL | Golden/evidence/quality schemas and metric entries do not enforce every frozen lineage/quality/version field. | Phase 1 Task 2/4 and Phase 2 Task 1/6 | resolve each schema before its first producer/consumer is implemented |
| A-012 | OPEN_INTERNAL | Planned provider-compliance scanning is narrower than the competition's ban on every non-HCX generative provider. | Phase 3 Task 1 and Phase 4 Task 4 | keep production dependencies provider-free except HCX |
| A-013 | RESOLVED_MIGRATION | Hidden-answer matching and request-validation questions were missing from this log. | organizer response | tracked as Q-009 and Q-010 above |
| A-014 | OPEN_INTERNAL | Some Phase 3/4 plan steps create behavior/configuration before their failing test. | before each affected Phase 3/4 task | rewrite those task steps into strict red-green-refactor order |

## How to add an official answer

Add a dated `OFFICIAL_OVERRIDE` row containing the exact source/channel and affected config/tests. Never edit history to hide the previous decision.
