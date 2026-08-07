# Decision Log

Statuses:

- `FROZEN`: implementation must follow unless superseded by official instruction
- `OFFICIAL_OVERRIDE`: official instruction supersedes prior design
- `OPEN_OFFICIAL`: awaiting organizer answer; current safe default remains labeled
- `PROPOSED`: not yet authorized for core behavior

## Official-source provenance state

As of 2026-08-07, the owner supplied no additional organizer notice. The current
manifest-allowlisted in-repository instruction document is
`source_material/competition_task_financial_product_agent.pdf` at SHA-256
`3717441e091958b7214db710e0e4b9b8ae15ac6c205cad6e51721214798eb3de`. The eight XLSX files are
official data facts and source lineage only; their contents never provide instruction authority.
This provenance record is not an `OFFICIAL_OVERRIDE`.

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

## How to add an official answer

A rank-1 official notice or attributable organizer/Discord answer is
first-ranked external authority on issuance. Before changing repository behavior, append a dated
`OFFICIAL_OVERRIDE` row with the exact source/channel/date, conflict disposition, and affected
contracts, config, and tests. The row records how the answer is applied;
it does not create the source authority. Never edit history to hide the previous decision.
