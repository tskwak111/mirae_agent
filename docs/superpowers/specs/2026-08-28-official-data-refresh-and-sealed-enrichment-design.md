# Official Data Refresh and Sealed Enrichment Design

**Status:** In-chat design approved on 2026-08-28; written-spec review pending

**Scope:** Replace the superseded 2026-07-11 official dataset with the organizer's
2026-08-24 distribution, migrate only the affected FinProof contracts, add bounded
offline holdings enrichment, and align the evaluation runtime with the organizer's
latest HCX, missing-value, eligibility, cross-product, and timeout instructions.

**Preserved architecture:** HCX interpretation, deterministic execution, Source
Fidelity, native product grains, cross-product segmentation, allowlisted SQL,
evidence construction, claim verification, and the exact five-string `/answer`
response.

## 1. Authority and purpose

The organizer's latest notice and replacement archive are higher-priority sources
than D-006, D-008, D-012, D-015, Q-002, Q-003, Q-005, the old frozen design, and all
data-derived implementation baselines. Implementation must append dated
`OFFICIAL_OVERRIDE` entries to `docs/10_DECISION_LOG.md`; it must preserve the old
rows as history rather than editing them.

The replacement archive supplied by the user is:

```text
ai-festival2026_금융상품Agent_DtataSet260824.zip
SHA-256 93450657290e09f5f6afd65bdacb229faddca33a9e9bad6d37bbd11f41c492fc
```

The archive contains eight substantive XLSX files and eight macOS metadata entries.
Only the substantive schema/data workbooks are admitted. The old 2026-07-11
workbooks, artifacts, audit counts, canonical values, and answer expectations leave
the active build and runtime. They are not copied into a second in-repository archive;
Git history is the recovery and audit mechanism.

This is a targeted migration, not a clean redo. Completed code and contracts remain
unless the replacement source or notice directly invalidates them. Phase 4 Task 3's
old-data ablation run stays paused until the migrated artifact and evaluation corpus
are sealed.

## 2. Observed replacement-package contract

Read-only inspection produced the following candidate baseline. Implementation must
independently regenerate and seal these facts from the admitted source files before
using them as production expectations.

| Source table | Rows | Columns | Native product count/grain | Structural change |
|---|---:|---:|---|---|
| `PRBD01N001` | 21,882 | 58 | 20,497 `instrument` IDs | multiple market/sale-LOT rows per `pd_no` |
| `PREF01N001` | 1,780 | 98 | 1,780 `listed_product` rows | new fields and nonconstant tracking/return values |
| `PREF02N001` | 6,037 | 49 | 6,037 `listed_product` rows | same width, refreshed values |
| `PRFD01N001` | 23,676 | 75 | 23,676 `fund_item` rows | one row per item; attribute list replaces attribute rows |

The total candidate row count is 53,375. Data sheets are named `data`; schema sheets
are named `schema`. Production ingestion must not retain the old `datarows` and
`Sheet1_Schema`/`Sheet2_Sample` assumptions.

The distribution version is `2026-08-24`. It is not a claim that every cell was
measured that day. The organizer describes domestic/public coverage through the
2026-08-22 business date and overseas coverage through 2026-08-23 Korea time. Each
field's actual source date remains authoritative and is preserved independently.
Internal code tables are unavailable: code-table meanings are not queried or guessed.

## 3. Version and time model

FinProof will distinguish four dates:

1. `dataset_version = 2026-08-24`, identifying the organizer distribution;
2. the user-requested plan date, defaulting to the `2026-08-24` distribution date;
3. each product segment's official coverage boundary;
4. each source or derived field's applicable date.

A plain “current” question means the 2026-08-24 distribution and must say that the
domestic/public and overseas coverage boundaries differ. It must not describe the
values as real-time.

The plan-level date remains one value for API and trace compatibility. Semantic
validation derives the applicable product-specific boundary before state or metric
policy runs. A field carrying an earlier explicit source date keeps that date; neither
the package date nor the segment boundary overwrites it. External records retain their
own `as_of_date <= 2026-08-24` and never inherit an official-master date.

## 4. Official-source normalization changes

### 4.1 Domestic bonds and sale lots

`pd_no` remains the native `instrument` identity. Every valid source row also becomes
one `bond_sale_lot` child keyed by the complete source identity, including
`pd_exg_mkt`, `info_base_dt`, `info_seq`, and original row lineage. The child relation
does not become a public result grain and cannot duplicate a product in final results.

The source contains 1,078 duplicate-instrument groups. In 307 instruments, more than
one sale lot has a positive `buy_yield`. The approved instrument-level policy is:

- preserve every raw lot and every lot-specific value;
- ignore `buyable_quantity` for eligibility, filtering, ranking, and aggregation;
- among otherwise valid sale lots, project the maximum valid `buy_yield` as the
  instrument's representative buy yield;
- take price and every quote-associated value from that same selected lot;
- break equal yields by canonical source-key order, never by quantity;
- show the selected rule and the observed lot-yield range when the range materially
  affects interpretation;
- count, rank, and aggregate each instrument once.

`BUYABLE_QUANTITY` stays in Bronze and source lineage but is removed from the query
field and metric registries. For the organizer's purchaseability assumption, an
instrument present in the replacement master is treated as purchasable unless its
issue date proves that it is not yet issued. Ended or delisted evidence excludes a
bond; absence of both permits the organizer assumption. Missing or sentinel maturity
alone does not
make the instrument ineligible under the organizer's assumption, but the answer must
warn that the end state is not source-verifiable. No quantity threshold is used.

Product-level fields that disagree across sale lots are not silently merged. Exact
equal values can share a representative with all equivalent locators retained.
Conflicting values either remain lot-specific or produce a quality issue and an
unavailable parent projection, according to the field's role.

### 4.2 Domestic and overseas listed products

The listed-product grain and ETF/ETN discriminator remain unchanged. A plain ETF query
still excludes ETNs. All new and retained columns are re-audited against their schema
comments and observed domains before normalization rules are reused.

The refreshed domestic tracking error and one-year return are no longer constant-zero
fields, so the old snapshot-specific constant-metric handling is removed. The
overseas one-day return is likewise a normal varying source metric. Product state uses
the replacement listing and applicable-date fields; no old row counts or constant
distributions remain authoritative.

### 4.3 Public funds

The default grain remains `fund_item = itm_no`. The new source already has one row per
item, so the old source-row attribute grain and `(itm_no, prfd_attr_cd)` primary key are
retired from the active source contract.

`prfd_attr_cds`, `prfd_attr_cnt`, and `prfd_attr_search_text` replace the removed
single `prfd_attr_cd`. Attribute parsing yields an immutable many-valued property on
the fund item. Empty lists and a count of zero are valid source states. They are not
expanded into duplicate fund products.

Exact domestic-ETF/public-fund links are regenerated from the replacement data. The
candidate exact intersection is 217 identifiers, but the production count and hash
come only from the new sealed build. The exact-only and one-to-many-conflict rules are
unchanged.

### 4.4 Intentional zero and missing values

Raw zeroes and blanks remain immutable and retain full lineage. A zero or missing
value is not labeled suspicious merely because it is zero or missing. Each metric
declares only the operation-specific behavior required by the organizer notice:

- display either omits the value or states that it is unavailable;
- filtering and ranking exclude unavailable values;
- aggregation reports the included count and never treats missing as zero;
- material omissions and partial comparison universes become evidence-backed
  limitations.

Old snapshot-specific dual-lens and constant-zero policies are deleted only where the
replacement distribution or official notice directly invalidates them.

## 5. Sealed external enrichment

### 5.1 Admission boundary

External data may participate in evaluation because the new organizer notice permits
teams to choose data used to build knowledge. It remains supplemental and cannot
overwrite a nonmissing official value.

An external snapshot is admitted only when all of the following are available:

- source owner and direct source URL;
- source-specific as-of and publication dates no later than the cutoff;
- retrieval timestamp and immutable raw-file SHA-256;
- a schema/field dictionary sufficient to preserve units;
- an exact owner-product mapping to an official FinProof identifier;
- a recorded reuse/redisplay basis compatible with the submitted artifact;
- deterministic coverage counts and quarantine results.

Failure of any admission condition excludes that source generation. Runtime never
calls KRX, SEC, KOFIA, an asset manager, or another live data API.

### 5.2 Minimal relations

Only two new query-time relations are required:

```text
silver_product_holding
silver_product_holding_coverage
```

One holding row contains the owner product type/ID, one source-selected exact
constituent identifier and type, raw/display name, available quantity and unit,
available market value and currency, available weight, source as-of/publication dates,
source kind/URL/hash/row ordinal, normalized quality state, and canonical `record_json`
with complete raw lineage. Unknown units remain unknown; values are not guessed or
converted.

One coverage row exists per official product in a product type enabled for holdings
queries. It records `complete`, `partial_top_10`, or `unavailable`, along with source
generation when present, dates, observed row count, and a limitation code. This
separate relation is required so zero holding rows cannot be confused with complete
evidence of non-holding.

### 5.3 Source-specific scope

- **Domestic ETF:** KRX ETF PDF is eligible only after logged-in historical capture
  proves the selected date and reuse/redisplay permission is recorded. KRX owner
  `isuCd` links to the official domestic product only by exact identifier. ETF PDF is
  not used as ETN holdings evidence.
- **Overseas ETF:** SEC Form N-PORT may cover exactly mapped U.S.-registered funds.
  `CIK` alone is a candidate generator, not a product link. Automatic admission
  requires an exact approved `CIK + SERIES_ID + CLASS_ID` crosswalk. ETNs, non-U.S.
  products, and ambiguous classes remain unavailable.
- **Public fund:** public asset-management reports may supply only documented top-ten
  holdings and therefore receive `partial_top_10`. Automatic owner linkage requires an
  exact published KSD/standard/official fund identifier. Names never create the link.
  A comprehensive holdings claim requires a separately authorized KOFIA or licensed
  fund-evaluation-company monthly feed.

Positive matches from partial coverage are usable. Absence from `partial_top_10` or
`unavailable` cannot prove non-holding, support an exhaustive count, or define a
complete ranking universe.

### 5.4 Supplemental metrics

No generic external-metric platform or placeholder table is created. An external
metric is added only after a primary source, exact product mapping, definition, period,
unit, as-of rule, and comparability policy are approved under the existing metric
registry contract.

SEC N-PORT does not directly publish a one-year return. A derived twelve-month NAV
return is therefore not admitted by this design. Until a verified compatible source is
approved, overseas ETF/ETN one-year-return segments are pruned with an explicit
limitation and are not mixed into a global domestic-ETF/public-fund one-year ranking.

## 6. Query and execution design

The existing `QueryPlan`, `ExecutionBundle`, product types, result grains, and
`top_k_scope` remain. Holdings are a relation filter and evidence source, not a product
type or result grain.

The field registry gains one allowlisted relational filter,
`holding_constituent`. It supports only `eq` with one resolved constituent identifier;
the implementation plan may not broaden its operators. Deterministic constituent
resolution applies this order:

1. exact admitted constituent identifier;
2. unique normalized exact name within the admitted snapshot;
3. bounded candidate list and clarification.

Fuzzy similarity never creates an automatic constituent or owner link.

Each native product segment compiles independently. The compiler emits a parameterized
`EXISTS` predicate against `silver_product_holding`; it does not union incompatible
product tables or interpolate identifiers/values. Ordinary scalar projections still
come from the native product table.

For a cross-product constituent query, policy proceeds in the existing order:

1. resolve the constituent and product entities;
2. filter each product segment through exact positive holding evidence;
3. apply product state and metric eligibility;
4. form compatibility partitions;
5. rank, tie, aggregate, and apply `top_k` under the declared scope;
6. attach coverage limitations and evidence.

A global rank is valid only for a compatible metric. With partial holdings coverage,
it is explicitly a rank among evidenced positive matches rather than an exhaustive
universe rank; an exhaustive claim requires complete coverage. Unsupported or
partially covered segments are not silently treated as complete. Each returned
product retains its native identity and grain under the heterogeneous `product`
envelope.

## 7. Evidence and answer generation

Every returned holdings match binds at least:

- official owner-product evidence;
- the exact owner crosswalk;
- the external holding row;
- the owner coverage row;
- the ranked/displayed official metric evidence;
- partition, tie, exclusion, and top-k evidence;
- all source and registry versions.

`retrieved_context` exposes a bounded verified fact pack. `think_trace` remains a
deterministic execution trace and never contains hidden model reasoning.

HyperCLOVA X is mandatory at two evaluation stages:

1. intent analysis and constrained QueryPlan production;
2. final answer wording from the verified fact pack.

Evaluation has no rule-planner or deterministic substantive-answer fallback. Planning
may perform one bounded HCX repair after schema failure. The answer verbalizer returns
a strict object containing the answer plus used claim/limitation IDs. Local claim
verification checks every material entity, number, comparison, rank, omission, and
warning. One bounded HCX answer repair is allowed. A second failure returns a fixed
non-substantive safe response; it never calls another model or publishes an
unverified answer.

The endpoint continues to return exactly five strings: `question_id`, `question`,
`retrieved_context`, `think_trace`, and `answer`.

## 8. Failure, timeout, and publication behavior

The organizer's 300-second timeout is a physical no-response boundary, not a target
latency. FinProof uses a 295-second end-to-end outer deadline and reserves enough
remaining time to serialize a fixed safe response. Planner, deterministic execution,
and verbalizer budgets remain independently bounded and latency-focused; retries are
never allowed to exceed the outer deadline.

External acquisition failures cannot occur at runtime. At build time:

- an absent, unapproved source yields explicit unavailable coverage;
- a declared/admitted generation with a checksum, schema, mapping, or count mismatch
  blocks publication of that generation;
- no partially verified replacement artifact becomes active;
- unaffected official-only queries remain available through a verified official
  artifact.

No response silently truncates evidence or claims. Expected failures become bounded
typed errors or the fixed safe response, without keys, internal paths, raw SQL, stack
traces, or unrestricted source payloads.

## 9. Artifact and migration boundary

The refreshed offline artifact keeps the existing Bronze/Silver/Gold and read-only
DuckDB architecture. It adds only the bond-sale-lot and two holdings relations required
by this design. Generated manifests, expected contracts, Parquet, DuckDB, reports,
exact links, and logical hashes are regenerated by the verified builder and are never
hand-edited.

Implementation order is fixed:

1. record the official notice overrides and admit the replacement source package;
2. migrate source manifests/catalogs, date semantics, and the four normalizers;
3. migrate bond lots, eligibility, zero/missing policy, exact links, and artifacts;
4. admit authorized external snapshots and add holdings/coverage relations;
5. add the relational query path and mandatory HCX verbalizer/verification path;
6. migrate evaluation references and run release checks.

The old 265-case corpus remains useful for language, intent, safety, and policy
coverage, but its old snapshot values and artifact hashes are not active truth.
Data-dependent plans, evidence, results, and answers are regenerated and human-reviewed
against the replacement artifact. A separate organizer-shaped suite contains exactly
35 cases: ten easy, ten medium, ten hard, and five explicitly unanswerable, including
multi-product constituent queries.

## 10. TDD, review, and gates

Every behavior change follows focused RED -> minimum implementation -> focused GREEN.
No test is weakened, deleted, or manufactured to pass. Related aggregate tests run
only when their functional bundle closes. The mandatory repository-wide gate runs once
for the final commit candidate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

API/release completion also runs the required integration, load, latency, resilience,
and soak checks. If code changes after the final gate, the affected focused tests run
first and the final full gate runs exactly once again.

Each independently reviewable checkpoint is committed. One independent code review
checks the approved contract and diff. Only Critical and Important findings block.
One focused correction/re-review round is allowed. Later findings are classified by
the root agent as direct contract violation, out-of-scope regression risk, or
unsupported hardening; only the first class is fixed in the checkpoint. Closure occurs
at Critical 0 / Important 0, followed by one batched status/decision documentation
update.

## 11. Explicit non-goals

This migration does not add:

- live market or holdings APIs;
- a generic external-provider framework or data lake;
- automatic fuzzy owner/constituent links;
- ETN holdings inferred from ETF PDF or index constituents;
- an external one-year return without an approved metric contract;
- a new holdings result grain;
- free-form Text-to-SQL;
- another generative model;
- forecasts, categorical recommendations, or personalized suitability logic;
- a clean rewrite of already valid FinProof modules.

## 12. Completion criteria and stop conditions

The migration is complete only when:

- the active official data-workbook set contains only the admitted replacement
  package while the task PDF and source-contract metadata remain;
- source checksums, schema widths, keys, counts, and applicable dates are sealed;
- all official values retain complete Source Fidelity lineage;
- bond instruments are unique while every valid sale lot remains recoverable;
- no query/state policy consumes `BUYABLE_QUANTITY`;
- public-fund attributes remain many-valued without duplicate fund items;
- every external positive match has exact owner/constituent evidence and a coverage
  record;
- partial/unavailable coverage cannot produce a negative holdings claim;
- HCX performs both mandatory stages and unverified wording is blocked;
- the 35-case organizer-shaped suite and migrated regression corpus are reviewed;
- final full, API, performance, resilience, soak, compliance, and independent-review
  gates meet their contracts.

Implementation stops rather than guesses if the replacement archive differs from its
approved hash, a regenerated source fact differs without explanation, bond lot metric
semantics differ from this approved policy, an external source lacks exact mapping or
reuse authority, the HCX model cannot satisfy the mandatory interfaces, or a metric's
unit/period/comparability would change a result without an approved registry rule.

## 13. Primary external-source references

- KRX ETF PDF screen: <https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT050.jsp>
- KRX open-API information: <https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd>
- KRX legal notice: <https://info.krx.co.kr/contents/KRX/06/06070200/KRX06070200.jsp>
- SEC Form N-PORT datasets: <https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets>
- SEC N-PORT readme: <https://www.sec.gov/files/nport_readme.pdf>
- KOFIA fund-reporting regulation: <https://law.kofia.or.kr/service/law/lawFullScreenContent.do?historySeq=819&seq=136>
- Korean Capital Markets Act Enforcement Decree, Article 92: <https://www.law.go.kr/LSW/lsLinkProc.do?datClsCd=010102&gubun=admRul&joNo=009200004&lsId=36022&lsNm=%EC%9E%90%EB%B3%B8%EC%8B%9C%EC%9E%A5%EA%B3%BC%EA%B8%88%EC%9C%B5%ED%88%AC%EC%9E%90%EC%97%85%EC%97%90%EA%B4%80%ED%95%9C%EB%B2%95%EB%A5%A0%EC%8B%9C%ED%96%89%EB%A0%B9&mode=10>
