# Phase 1 Task 4 Overseas and Public-Fund Normalization Design

**Status:** Approved-design candidate under the user's standing instruction to select
the safest contract-preserving approach and continue without intermediate confirmation.

**Scope:** Normalize verified `PREF02N001` overseas ETF/ETN rows and verified
`PRFD01N001` public-fund attribute rows into immutable typed records; collapse valid
fund attribute rows to the frozen `itm_no` item grain without losing any source-cell
lineage; and align the quality-issue JSON schema with the already-frozen domain model.
This task does not persist artifacts, infer unresolved eligibility, group fund families,
create cross-source links, execute queries, rank products, or serve answers.

## 1. Goal and selected architecture

Task 2 established the fail-closed verified-reader boundary. Task 3 established the
pure `SourceRow -> NormalizationResult[T]` architecture with strict frozen Pydantic
records, `NormalizedValue[T]`, deterministic issues, complete cell locators, and no
normalizer I/O or clock access. Task 4 extends that architecture without weakening it.

The legacy Phase 1 plan predates Task 3 and is superseded in four places:

1. overseas products use a dedicated `OverseasListedProduct`, not the domestic-only
   `ListedProduct` and not a dynamic metric mapping;
2. overseas primary IDs use an exact-nonblank source-identity rule, not the domestic
   twelve-character identifier parser;
3. no overseas or public-fund eligibility is derived under A-003;
4. the complete `normalize_public_funds` boundary preserves malformed-row issues and
   all contributing item locators instead of passing only successful rows to collapse.

All public interfaces and cross-module records remain fully typed. Dynamic field maps,
plain DTOs that lose raw values, and caller-constructed locators are rejected.

Rejected alternatives are stretching the domestic product with nullable overseas
fields, retaining only one representative fund row, grouping by encounter order, and
using padded raw attribute text alone as the logical key. Those choices respectively
erase product-specific meaning, lose repeated evidence, contradict the worksheet's
non-contiguous order, or fail to protect normalized-key collisions. The selected
design preserves raw and normalized identities and checks both key spaces.

## 2. Frozen boundaries

- Inputs are immutable `SourceRow` values from the Task 2 verified reader or complete
  synthetic fixtures with equivalent lineage.
- Normalizers and collapse functions perform no filesystem, database, network,
  environment, logging, or clock I/O.
- Raw text is immutable. A normalized value never overwrites its raw value.
- Financial numerics use exact finite `Decimal`; `float` is prohibited.
- Financial dates use `date`. The overseas NAV source timestamp uses a timezone-naive
  `datetime` because the workbook supplies no timezone.
- A nearby update or basis date is never copied into another source cell's
  `source_applicable_date`; official cells currently have `None` there.
- Missing optional values and date sentinels do not quarantine a product. Invalid
  mandatory identity, product type, or fund attribute key does.
- `NormalizationResult.record is None` if and only if a quarantined issue exists.
- Product names, strategy text, descriptions, and identifiers are untrusted data.
- Official inputs and `tests/contracts/expected_source_audit.json` remain read-only.

## 3. Shared contracts and A-011 boundary

Task 4 reuses, unchanged, `SourceCellLocator`, `NormalizedValue[T]`,
`DerivedValue[T]`, `QualityStatus`, `DataQualityIssue`, and
`NormalizationResult[T]` from Task 3. New Pydantic records are frozen, strict, and
forbid extra fields.

### 3.1 Canonical quality-issue JSON

The current `schemas/quality_issue.schema.json` is older than the implemented domain
contract and cannot validate it. Task 4 resolves only this quality-issue part of A-011.
The canonical serialized issue is exactly `DataQualityIssue.model_dump(mode="json")`.
It requires:

```text
issue_id                 # lowercase SHA-256
rule_id
rule_version
severity                 # info | warning | high | blocker
quality_status           # closed QualityStatus enum
source                   # complete SourceCellLocator serialization
reason
quarantined
raw_payload_sha256       # lowercase SHA-256 of NUL-separated raw row
first_detected_at        # null or timezone-aware UTC date-time
```

The nested source requires table, safe manifest-relative file, sheet, Excel row,
exact column name/number/letter, source checksum, source snapshot date, and optional
source applicable date. Additional properties are forbidden at every object level.

Pure normalization emits `first_detected_at=None`. The first artifact persistence in
Task 5 supplies an injected timezone-aware UTC value. Operational timestamps never
enter logical reproducibility hashes. A proposed D-021 records this contract and marks
only the quality-issue portion of A-011 resolved. The evidence-record, golden-case,
metric-loader, and later evidence-version gaps remain open until their first consumers;
Task 4 does not edit `schemas/evidence_record.schema.json`.

JSON-mode UTC timestamps serialize canonically with a `Z` suffix. The schema combines
`format: date-time` with a terminal-`Z` pattern, so naive timestamps and even valid
nonzero-offset date-times are rejected. The domain model remains the authority for UTC
validation before serialization.

JSON Schema `format` is not self-enforcing. Contract tests and every runtime/artifact
consumer must construct
`Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())`, call
`Draft202012Validator.check_schema(schema)`, and then inspect or raise on all instance
errors. Using `jsonschema.validate` without an explicit `FormatChecker`, a pattern-only
timestamp check, or treating `format` as an annotation is prohibited. Tests prove that
canonical `...Z` UTC values validate while naive, malformed, and valid date-times with
nonzero offsets fail.

### 3.2 Issue ordering and safety

Issues use the existing deterministic ID and payload hash. Reasons are fixed messages
without raw payloads, absolute paths, or stack traces. No wall-clock value affects a
pure result. Section 6.3 freezes one total ordering for every issue returned by
`normalize_public_funds`, including rows whose item ID cannot be normalized.

### 3.3 Listed type

ETF and ETN are one shared exact source vocabulary. Task 4 may move
`ListedProductType` to a focused shared domain module and re-export it from the
domestic module, but only with regression tests proving Task 3 imports, serialization,
and behavior are unchanged. Values other than exact `ETF` and `ETN` quarantine.

## 4. Overseas ETF/ETN contract

Public interface:

```python
normalize_overseas_listed(
    row: SourceRow,
) -> NormalizationResult[OverseasListedProduct]
```

`as_of` is intentionally absent. Task 4 has no authorized overseas eligibility
predicate, so accepting an inert date would imply behavior that A-003 defers.

The function raises `NormalizationContractError` for a non-`PREF02N001` row.
Malformed product identity or product type returns a quarantined result.

### 4.1 Identity

`pd_itm_no` is an overseas source identifier, not a domestic security-number shape.
It is valid when the raw value is nonempty, contains at least one non-whitespace
character, and equals its Unicode-trimmed form. Its normalized value is the exact raw
string. No regex for current dot/ticker patterns is frozen: case, punctuation, length,
exchange suffix, or ISIN semantics are not silently rewritten. This accepts the
verified snapshot's unique IDs such as `BND.O`, `XW`, and `EES` without overfitting the
observed distribution. Blank, whitespace-only, or surrounding-whitespace identities
are `malformed_source_row` blockers.

`pd_itm_no_ma`, ticker, ISIN, Lipper ID, name, and other identifiers are separate
source-backed fields. Current equality between product and market IDs, or duplicate
ticker/ISIN/name values, never creates a merge.

### 4.2 Domain model and mappings

`OverseasListedProduct` has native grain `listed_product` and explicit wrappers for
all 49 source columns. Core query-facing mappings are named directly; remaining
source columns are retained with faithful descriptive names rather than a dynamic raw
map:

```text
product_id                  <- pd_itm_no
market_identifier           <- pd_itm_no_ma
ticker                      <- pd_abrv_nm
isin                        <- pd_isin_cd
name                        <- pd_nm
product_type                <- pd_grp_no
trading_currency            <- pd_trd_ccy
listing_date                <- pd_lstg_dt
sale_flag_raw               <- pd_sale_yn
suspension_flag_raw         <- pd_tr_yn
total_fee                   <- cu_charge_rt
aum                         <- du_last_aum
base_index                  <- cu_base_index
manager                     <- cu_fund_mgmt_co
strategy                    <- cu_strtegy
replication_method          <- cu_index_repl_mthd
asset_type                  <- wu_inv_ast_type
region                      <- wu_inv_rgn
return_1d                   <- du_er_1d
close_price                 <- du_clpr
close_price_base_date       <- du_clpr_base_dt
custom_update_date          <- cu_upt_dt
nav_base_at                 <- du_nav_base_dt
daily_update_date           <- du_upt_dt
weekly_update_date          <- wu_upt_dt

etn_flag_raw                <- cu_etn_yn
index_tracking_flag_raw     <- cu_index_tracking_yn
inverse_short_flag_raw      <- cu_inverse_short_yn
leverage_factor             <- cu_lev_fector
daily_base_date_match_raw   <- du_base_dt_match_yn
daily_open_price            <- du_opr
daily_high_price            <- du_hpr
daily_low_price             <- du_lpr
daily_bid_price             <- du_bpr
daily_close_source          <- du_clpr_src
difference_rate_raw_metric  <- du_diff_rt
last_nav                    <- du_last_nav
daily_value                 <- du_val_1d
daily_volume                <- du_vol_1d
source_currency_raw         <- pd_curr_cd
exchange_market_code        <- pd_exg_mkt_cd
market_code                 <- pd_mkt_id
lipper_id                   <- pd_lipper_id
listing_price               <- pd_lst_price
listed_share_count          <- pd_lst_stk_cnt
us_cik                      <- pd_us_cik
realtime_market_price       <- ru_mkt_price
realtime_market_volume      <- ru_mkt_volume
core_flag_raw               <- wu_core_yn
```

The 49 wrappers account for every official column exactly once. Source Fidelity does
not imply that every field becomes a registered query metric: unregistered fields such
as `du_diff_rt`, prices, and volumes remain typed source data only.

### 4.3 Parsing and quality

- `pd_grp_no` is the sole product-type discriminator. `cu_etn_yn` does not override it.
- `pd_trd_ccy` is parsed from the field as an exact uppercase three-letter ASCII
  currency. Current all-USD data is not hardcoded. `pd_curr_cd` remains a distinct raw
  source field and never overrides trading currency.
- `pd_lstg_dt` accepts the shared strict `YYYYMMDD` parser; the eight `00000000`
  values are `sentinel_zero`, not quarantines. Every overseas date call sets
  `allow_max_sentinel=False`; `99991231` is therefore parsed as an ordinary valid date,
  not a maximum-date sentinel.
- `cu_upt_dt`, `du_clpr_base_dt`, `du_upt_dt`, and `wu_upt_dt` are independent strict
  `YYYYMMDD` dates. `du_nav_base_dt` is the source's exact naive timestamp.
- Fee zero is `recorded_zero_unverified`. AUM, return, prices, counts, values, volumes,
  and other numeric zeroes are `recorded_zero`.
- `0E-8` is an exact valid Decimal zero and retains that exact raw spelling.
- Optional invalid numeric/date/currency values produce deterministic warnings without
  quarantining an otherwise valid identity.
- All 5,646 leverage-factor cells are missing; no leverage is inferred.
- Strategy/index placeholder prose remains literal untrusted text.

The model has no `is_active_at_as_of`, `is_eligible_at_as_of`, or other derived state.
Sale/trade flag blanks remain `missing_blank`; no truthiness or domestic polarity is
applied. Staleness thresholds are not frozen, so source dates remain visible without a
row-level `stale` inference.

### 4.4 Row-level versus dataset-level quality

An available `du_er_1d=0` wrapper is `recorded_zero`. The assertion that all 5,388
available values in this snapshot are zero is a dataset-distribution fact owned by the
artifact/metric-policy stage. It later produces a constant-metric warning and joint
tie behavior without rewriting each source cell. The same separation applies to all
distribution claims.

## 5. Public-fund source-row contract

Public interface:

```python
normalize_fund_attribute(
    row: SourceRow,
) -> NormalizationResult[FundAttributeRow]
```

The function raises `NormalizationContractError` for a non-`PRFD01N001` row. It
validates mandatory keys before interpreting the remaining payload. The known shifted
row at Excel 84,563 therefore produces one blocker at `itm_no` and no misleading
issues parsed from shifted cells.

### 5.1 Keys

`itm_no` uses the existing exact twelve-character uppercase ASCII alphanumeric parser.
The raw `"` value is a `malformed_source_row` blocker.

`prfd_attr_cd` is raw-preserving Unicode-trimmed text:

- blank or whitespace-only is a `malformed_source_row` blocker because it is part of
  the declared source primary key;
- valid padding is removed only in `normalized_value`; raw padding and exact locator
  remain unchanged;
- the 17 observed padded country codes (1,670 rows) therefore normalize, for example,
  raw `"USA "` to `"USA"` with `quality_status=valid`;
- no enum, country semantics, case conversion, or identifier regex is inferred.

Collision safety is mandatory. The complete `normalize_public_funds`/collapse boundary
proves uniqueness of both raw
`(itm_no, raw attribute)` and normalized `(itm_no, normalized attribute)` pairs.
Official data has 95,619 unique raw pairs, 228 raw and 228 trimmed attribute codes,
and zero trim collisions. Any normalized collision is a high quarantined group
failure; it is never silently deduplicated. `FundItemAttribute` retains the wrapper,
so the raw padded value survives even though stable ordering and logical identity use
the normalized code.

### 5.2 `FundAttributeRow`

`FundAttributeRow` is a strict frozen internal normalized row containing:

```text
source_row: SourceRow
fund_item_id: NormalizedValue[str]
attribute_code: NormalizedValue[str]
```

and explicit wrappers for all 43 other non-key source columns. It contains no dynamic
payload dictionary. The complete mapping is:

```text
benchmark_english_name       <- bmrk_eng_nm
benchmark_name               <- bmrk_nm
currency                     <- curr_cd
exchange_traded_flag_raw     <- exchdg_yn
establishment_country_code   <- fd_estb_ctry_cd
region_description           <- fd_ivst_rgn_desc
return_18m                   <- fd_mm18_ern_r
return_1m                    <- fd_mm1_ern_r
return_3m                    <- fd_mm3_ern_r
return_6m                    <- fd_mm6_ern_r
net_assets                   <- fd_nast_suma
establishment_type_code      <- fd_set_pcd
return_1w                    <- fd_wk1_ern_r
return_1y                    <- fd_yr1_ern_r
return_2y                    <- fd_yr2_ern_r
return_3y                    <- fd_yr3_ern_r
return_5y                    <- fd_yr5_ern_r
foreign_base_price_flag_raw  <- frc_bpr_itm_yn
fss_item_id                  <- fss_itm_no
hedge_fund_flag_raw          <- hdge_fd_yn
interest_dividend_description <- int_dvd_desc
short_name                   <- itm_abrv_nm
english_short_name           <- itm_eabrv_nm
english_name                 <- itm_eng_nm
name                         <- itm_nm
kofia_classification_code    <- kofia_fd_ccd
ksd_id                       <- ksd_itm_no
manager_item_id              <- mtco_itm_no
offshore_fund_flag_raw       <- ofsfd_yn
fund_type_raw                <- or_attr_desc
manager_external_code        <- or_co_xtn_itt_cd
overseas_fund_description    <- ovrs_fd_desc
investor_type_description    <- pers_corp_desc
professional_sale_control_code <- pfiv_sale_cntl_tcd
private_fund_description     <- prvo_fd_desc
offering_type_description    <- prvo_pbff_desc
family_candidate_key         <- rptt_ksd_itm_no
sale_status_raw              <- sale_yn
standard_item_id             <- std_itm_no
mirae_sale_flag_raw          <- thco_sale_yn
trustee_external_code        <- trusc_xtn_itt_cd
risk_code                    <- zrin_fd_ivst_risk_gcd
risk_name                    <- zrin_fd_ivst_risk_grd_nm
```

Together with `itm_no` and `prfd_attr_cd`, all 45 official columns are represented.
The normalizer preserves the exact input object by identity:
`normalize_fund_attribute(row).record.source_row is row`. The Python model boundary is
separate and enforceable: it accepts any value for which `type(value) is SourceRow`,
and rejects dictionaries, other mappings, and `SourceRow` subclasses. Python cannot
distinguish an exact `SourceRow` reconstructed by a caller from one emitted by the
reader, so this contract makes no such claim; the after validator instead proves that
all wrappers match whichever exact `SourceRow` was supplied.

JSON validation has no Python-object identity guarantee. Before ordinary `SourceRow`
validation, it requires the canonical serialized shape. The exact `SourceRow` key set
is `source_table`, `source_file`, `source_sheet`, `source_row_number`,
`source_checksum`, `source_snapshot_date`, `raw_payload`, and `cells`; the exact
`SourceCell` key set is `column_name`, `excel_column_number`,
`excel_column_letter`, `raw_value`, and `applicable_date`. It further requires
`cells` as a JSON array of exactly 45 JSON objects in catalog order, every cell with
that exact key set, and `raw_payload` as a JSON array of strings equal in order and
value to the cells' raw values. Scalar types are checked before Pydantic can coerce:
table/file/sheet/checksum/column names/letters/raw values are strings; row and column
numbers satisfy `type(value) is int` (so booleans and numeric strings fail); snapshot
and applicable dates are `YYYY-MM-DD` strings whose `date.fromisoformat` round trip is
identical, with `null` additionally allowed only for applicable date. No boolean field
exists in `SourceRow`/`SourceCell`; any future canonical boolean must analogously
require `type(value) is bool`. `source_file` is additionally nonempty, relative, free
of `..`, and already canonical:
`PurePosixPath(value).as_posix() == value`; redundant separators or dot segments such
as `data//file.xlsx` and `data/./file.xlsx` fail before Pydantic normalization. The
unchanged `SourceRow` and record after
validators then enforce types, safe path, dates, table, raw values, and locators. This
permits deterministic `model_validate_json(record.model_dump_json())` only as a
structural round trip; serialized JSON is not a trusted ingestion boundary.

An after validator checks every wrapper against the nested row using the frozen
field-to-column map: exact raw value equality and exact
`SourceCellLocator.from_row(source_row, column)` equality are required. It also checks
the exact table and that the source row contains the 45 expected columns in canonical
order. A wrapper copied from another row or column therefore fails even when its typed
value happens to match.

Contract tests require deterministic `model_dump(mode="json")` and
`model_dump_json()`, reject Python `model_validate`/constructor calls containing a
mapping or subclass instead of an exact-type instance, accept a separately constructed
exact `SourceRow` when every wrapper agrees with it, and allow only the canonical-shape
`model_validate_json(record.model_dump_json())` round trip. The JSON round trip must
reproduce raw payload, safe path, dates, cells, wrappers, and locators exactly.

### 5.3 Field policies

- Currency accepts exact `KRW` and `USD`; it is never inferred from another flag.
- AUM and all nine returns use finite Decimal parsing. Blank is `missing_blank`; zero
  is `recorded_zero`.
- Only `fd_mm18_ern_r`, `fd_yr2_ern_r`, `fd_yr3_ern_r`, and `fd_yr5_ern_r` apply the
  registered below-minus-100 rule. The Decimal remains present with
  `out_of_domain`, and a warning is located at each affected cell. The official one
  item appears on five attribute rows with four affected fields per row: 20 issues.
- Exact uppercase `NULL` is a missing token only in the two declared risk fields. It
  becomes `None/missing_literal_null` in either field. In the official snapshot the
  code is `NULL` while its paired risk name is blank, so the name correctly remains
  `None/missing_blank`; Task 4 does not manufacture a literal-NULL state for a blank.
- Risk-name spacing variants remain distinct raw/normalized source text.
- `or_attr_desc="06"` retains normalized `"06"`, receives the configured
  `mixed_source_values` state and a nonquarantine warning, and is never guessed to a
  fund type.
- Sale status and Mirae flag remain raw-backed text. No saleable, Mirae-saleable, or
  broader eligibility boolean is derived in Task 4 under A-003. The existing simple
  equality rules are deferred to the state-policy layer together with exact query
  semantics.
- Optional IDs use raw-preserving trimmed text. Zeros, blanks, and padded placeholder
  values are not exact links or family authority.
- The 15 private-marked rows/items and eight blank public/private markers remain in
  the source product set. The table name does not authorize rewriting their fields.
- Names containing `ETF` or `상장지수` remain public-fund items; they are not
  reclassified as listed products.
- There is no official fund source/update date. Locators carry the dataset snapshot
  and `source_applicable_date=None`; no fee or freshness metric is invented.

## 6. Public-fund collapse contract

Public interfaces:

```python
collapse_fund_items(
    rows: Iterable[FundAttributeRow],
) -> FundCollapseResult

normalize_public_funds(
    rows: Iterable[SourceRow],
) -> FundCollapseResult
```

`normalize_public_funds` is the authoritative complete boundary. It normalizes every
source row, preserves issues from failed rows, collapses every successful row, combines
all issues in deterministic order, and never requires callers to reconstruct the
malformed-row quarantine.

### 6.1 Result and output records

```text
FundCollapseResult
- items: tuple[FundItem, ...]
- attributes: tuple[FundItemAttribute, ...]
- issues: tuple[DataQualityIssue, ...]
```

`FundCollapseResult` itself is a frozen, strict, forbid-extra Pydantic model. It may
contain quarantined issues alongside unaffected items; the row-level equivalence rule
of `NormalizationResult` does not apply to a multi-row collapse result.

`FundItemAttribute` has native grain `fund_attribute` and contains the original
`fund_item_id` and `attribute_code` wrappers. It is ordered by normalized item ID,
normalized attribute code, raw attribute value, then Excel row. Raw padding and exact
cell evidence remain present.

`FundItemValue[T]` preserves repeated equal values without multiplying products:

```text
representative: NormalizedValue[T]
equivalent_sources: tuple[SourceCellLocator, ...]
```

The tuple is nonempty, contains one locator for every agreeing source row, is sorted by
Excel row/column, contains the representative locator first, and names one exact source
column. The representative comes from the lowest Excel row only after equality is
proved. All locators are unique. Shared-lineage comparison matches the representative's
table, file, sheet, column name/number/letter, checksum, and snapshot while explicitly
excluding both `source_row_number` and `source_applicable_date`. Each locator is still
retained exactly with its own row number and applicable date. Direct construction that
omits, duplicates, reorders, or mismatches the shared lineage or representative/source
column is rejected.

Every concrete generic specialization must support deterministic JSON-mode dump and
strict JSON round-trip validation while preserving the representative raw value,
normalized type, quality enum, rule/version, and complete locators.

`FundItem` has native grain `fund_item`. It contains a `FundItemValue[T]` for every
non-attribute wrapper listed in section 5.2, including the item ID. The attribute code
is excluded because it is many-valued. It does not include a computed family,
listed-product type, or eligibility value.

`FundItem` also owns the contributing source rows exactly once:

```text
contributing_rows: tuple[SourceRow, ...]
```

The tuple is nonempty and the collapse builder preserves each sorted input identity
(`item.contributing_rows[i] is input_row`). Direct Python construction accepts only
elements for which `type(value) is SourceRow`; it rejects mappings and subclasses but
accepts a separately constructed exact `SourceRow` that satisfies all invariants. JSON
uses the same canonical-shape structural boundary as `FundAttributeRow.source_row`,
without claiming object identity. All rows must be `PRFD01N001`, share file, sheet,
checksum, and snapshot, use the canonical 45 cells, and have the same exact raw
`itm_no`. Row numbers are unique and strictly increasing; the first row is therefore
the deterministic representative row. Mapping coercion and a caller-supplied
reordering are rejected in Python mode.

The `FundItem` after validator iterates the frozen field-to-column map. For every
`FundItemValue`, it requires:

- `equivalent_sources` equals, without omission or extras, the tuple
  `SourceCellLocator.from_row(row, source_column)` for every contributing row in order;
- the representative locator is the first expected locator;
- the representative raw value exactly equals the lowest row's raw source cell;
- every non-attribute raw cell in later rows equals the first row's corresponding raw
  cell.

Thus complete repeated lineage is a model invariant rather than a builder convention.
The source rows are stored once per item, not copied into each of the 44 values;
`FundItemValue` stores only the field-specific locators needed for direct evidence.
`FundItem.model_dump_json()` and strict JSON round-trip validation must preserve both
the contributing rows and every cross-checked value/locator exactly.

Because attributes are a sibling relation in `FundCollapseResult`, its after validator
enforces their completeness. For each item it requires exactly one
`FundItemAttribute` per contributing row: the attribute's item-ID locator must equal
`SourceCellLocator.from_row(row, "itm_no")`, its attribute locator must equal
`SourceCellLocator.from_row(row, "prfd_attr_cd")`, and both raw values must match that
row. The set of attribute source-row identities must equal the contributing-row set;
missing, duplicate, or extra attributes and attributes without an emitted item are
rejected.

### 6.2 Agreement, uniqueness, and determinism

The workbook is neither item-contiguous nor attribute-sorted. Collapse must group
globally by normalized `itm_no`; streaming `itertools.groupby` on encounter order is
incorrect.

For each item, collapse:

1. sorts rows by Excel row and proves unique raw and normalized item/attribute keys;
2. compares every one of the 44 non-attribute raw source columns exactly, not merely
   the current query-facing subset and not only normalized values;
3. only after exact agreement, selects the lowest Excel row as representative;
4. builds item values with every equivalent source-cell locator;
5. emits attributes and item in stable key order.

A duplicate raw pair, normalized attribute collision, or any non-attribute disagreement
uses the exact failure contracts in section 6.3 and excludes the entire affected item
plus all its attributes. Collapse never silently deduplicates or selects a preferred
value. Official data has zero such groups.

The result is input-order invariant. Tests prove that property with a finite exact
order suite rather than factorial enumeration. Given fixture declaration order
`canonical`, the required orders are `canonical`, `canonical[::-1]`,
`canonical[0::2] + canonical[1::2]`,
`canonical[1::2] + canonical[0::2]`, a stable item/attribute-key grouped order,
stable malformed-first, stable malformed-last, and 32 shuffles produced by one
`random.Random(20260814)` instance by copying `canonical` and calling `shuffle` once
per sample. Every order must produce byte-equivalent JSON-mode item, attribute, and
issue dumps.

The authoritative `normalize_public_funds` path materializes and groups only
`SourceRow` references. Its first pass uses the same internal key validator as
`normalize_fund_attribute`, preserving malformed item/attribute issues without
building full normalized row records. It then visits normalized item keys in stable
order, normalizes only that one Excel-row-sorted group, collapses it through one shared
single-group helper (routing each row through `normalize_fund_attribute`), appends
immutable outputs/issues, and releases every
`FundAttributeRow` before advancing. It never constructs a dataset-wide normalized-row
tuple or list. The standalone `collapse_fund_items` boundary may group its caller's
already-normalized iterable, but the official path must not call it with all 95,618
records.

The official result remains large because 95,618 rows contribute direct cell evidence,
but source rows are stored only once per item and not once per value. A two-size
`tracemalloc` preflight compares transient `peak-current` allocation slope after source
fixtures are built and structurally verifies the authoritative source-row grouping
path. The official pytest records `perf_counter` wall time and
`resource.getrusage(RUSAGE_SELF).ru_maxrss` before/after normalization. Task 5 may
replace the grouping mechanism with bounded external sort/storage while preserving
this semantic contract.

### 6.3 Collapse failure issues and global issue order

All three collapse rules have `rule_version="1.0.0"`,
`quality_status=mixed_source_values`, `severity=high`, and `quarantined=true`. Each
issue is built with `DataQualityIssue.from_row` from the actual offending row and cell,
so its payload hash and source locator remain complete.

#### Raw duplicate key

For a raw `(itm_no, prfd_attr_cd)` key occurring `n > 1` times:

```text
rule_id = public_fund.attribute_key.raw_duplicate
reason = Public-fund raw item-attribute key is duplicated.
locator = each participating row's prfd_attr_cd cell
cardinality = n issues for that duplicate raw-key group
```

Every participating cell receives exactly one issue, including the lowest-row value;
no row is treated as authoritative. If an item contains several duplicate raw-key
groups, cardinalities add.

#### Normalized attribute collision

For one normalized `(itm_no, normalized prfd_attr_cd)` group containing more than one
distinct raw attribute value:

```text
rule_id = public_fund.attribute_key.normalized_collision
reason = Public-fund attribute values collide after normalization.
locator = each participating row's prfd_attr_cd cell
cardinality = n issues for the n rows in that normalized-collision group
```

This rule is specifically about distinct raw spellings such as a padded and unpadded
form. A plain raw duplicate alone does not also trigger it. If a participating raw form
is itself duplicated and another raw form collides after trimming, those rows correctly
receive one issue from each independently violated rule.

#### Non-attribute disagreement

For every one of the 44 non-attribute columns whose exact raw values are not identical
within an item group:

```text
rule_id = public_fund.item.non_attribute_disagreement
reason = Public-fund non-attribute source values disagree within one item.
locator = that exact column cell in every row of the affected item group
cardinality = item row count x number of disagreeing columns
```

Every value in a disagreeing column is evidence; majority selection is prohibited.
Columns that agree emit no issue. The item and all its attributes are excluded once,
regardless of how many issues describe the failure.

#### One total issue ordering

`normalize_public_funds` decorates every row and collapse issue with internal ordering
metadata, sorts once, verifies unique `issue_id` values, and then drops only the private
metadata. The exact ascending key is:

```text
(
  normalized_item_key_or_empty,
  quarantine_raw_item_key_or_empty,
  source_row_number,
  source_column_number,
  rule_id,
  issue_id,
)
```

String components use ordinary Unicode code-point ordering and numeric components use
integer ordering; locale and process environment never participate.

For a successfully normalized item, the first component is its normalized `itm_no`
and the second is empty. For a row without a normalized item ID, the first component is
empty and the second is the exact raw `itm_no`; this is sorting metadata only and is
never emitted in the issue reason or substituted for identity. Thus the malformed
`itm_no='"'` row has a stable position without pretending it has a normalized key.
The remaining locator/rule/hash components make the order total. Duplicate issue IDs
are a contract failure rather than silently repeated output.

Tests mix successful, malformed, warning-bearing, duplicate, collision, and
disagreement rows and apply the exact bounded order suite from section 6.2, asserting
byte-identical `FundCollapseResult.model_dump_json()` output including the entire issue
tuple.

### 6.4 Family boundary

`rptt_ksd_itm_no` is preserved only as a candidate field. Blank, zero-like, padded,
or shared values do not group products. In particular, placeholder-like keys currently
connect hundreds of unrelated items. No `fund_family_candidate` output is built by
Task 4; family behavior requires an explicit request and later versioned policy.

## 7. Official acceptance contract

The acceptance test consumes only manifest/catalog-verified descriptors and exhausts
both official iterators. Counts are frozen observations, not correction lists.

### 7.1 Overseas

```text
5,646 source rows -> 5,646 records, zero quarantines
5,646 unique product IDs
5,587 ETF / 59 ETN
5,646 trading currencies read as USD from pd_trd_ccy
363 fee zero wrappers as recorded_zero_unverified; 5,283 positive fees
5,388 nonblank one-day returns, all recorded_zero; 258 blank
5,459 nonblank AUM: 5,451 positive, 8 recorded zero; 187 blank
5,638 nonblank base index/manager/strategy/asset type/region
2,360 nonblank replication methods
8 sentinel-zero listing dates; 10 blank sale/trade flags retained as unknown
all 49 declared wrappers preserve exact raw values and complete locators
```

Ticker, name, ISIN, and Lipper duplicates do not alter the primary-key result. No
per-row `constant_metric`, eligibility, or staleness claim is introduced.

### 7.2 Public funds

```text
95,619 source rows
11,139 raw item IDs; 11,138 valid FundItem outputs
one malformed/quarantined row at Excel 84,563 with raw itm_no='"'
95,619 raw unique source pairs; zero raw duplicates
95,618 normal FundItemAttribute outputs
228 raw and 228 trimmed attribute codes; 1,670 padded rows; zero trim collisions
zero official normalized pair collisions
zero non-attribute disagreement items
maximum 16 attributes per item
11,067 KRW items / 71 USD items
18,416 literal-NULL risk-code rows / 2,573 items
5,436 fund-type-06 rows / 686 items
five affected source rows / one item / 20 below-minus-100 field cells
one malformed blocker survives in FundCollapseResult.issues
every item field preserves the representative and all contributing locators
no family collapse and no name-based ETF conversion
```

The official test also proves bounded order invariance on representative
multi-attribute groups: source-row-number canonical order, reverse, zero-based even
indices followed by odd indices, and zero-based odd indices followed by even indices.
Attribute fidelity is compared directly to the existing `SourceRow` cells and
locators; the acceptance test does not renormalize 95,618 attributes or construct a
second complete `FundAttributeRow` tuple. The official pytest records wall time and
process peak RSS with `perf_counter` and `resource.getrusage`, after the two-size
transient-allocation slope preflight. It does
not freeze every optional warning count; a justified warning refinement may change
issue counts without changing source identity, raw values, or the normative anomalies
above.

## 8. Error handling and security

- Wrong table IDs are typed programmer errors; bad rows within the expected table are
  deterministic results/issues.
- Identity validation happens before parsing a shifted payload.
- Issue reasons never echo raw text or local paths.
- Text fields never instruct parsing, planning, code, SQL, or tools.
- No external data enriches or overwrites official values in evaluation mode.
- Input iteration failures are not swallowed. Unexpected exceptions propagate to the
  caller and block the task until explained.
- A schema/quality conflict is recorded rather than silently reconciled.

## 9. Required TDD and review sequence

Every behavior is introduced under observed RED -> GREEN -> REFACTOR:

1. canonical quality-issue JSON schema, explicit Draft 2020-12 plus FormatChecker
   validation, UTC-negative cases, and partial A-011/D-021 decision;
2. complete synthetic source rows plus shared listed type, exact overseas identity,
   literal-null helper, and `FundItemValue` invariants;
3. overseas import/table/model scaffold RED -> minimum uncommitted scaffold GREEN,
   mapping/valid-path RED -> GREEN, field-policy RED -> GREEN, then mutation/invariant
   RED -> GREEN before one complete checkpoint commit;
4. fund-row model scaffold RED -> minimum uncommitted model GREEN, table/key/all-field
   valid-path RED -> GREEN, field-policy RED -> GREEN, then exact-type Python,
   canonical-JSON scalar/shape, and mutation RED -> GREEN before commit;
5. collapse output-model scaffold RED -> GREEN; then valid standalone/authoritative
   path plus authoritative memory slope/lifetime RED -> GREEN before that grouping
   implementation; result invariant RED -> GREEN; each failure producer including its
   complete issue fields RED -> GREEN; global issue/bounded-order RED -> GREEN; and a
   final memory rerun before one complete checkpoint commit;
6. full official 101,265-row acceptance for section 7;
7. mandatory repository gates, status evidence, independent whole-branch review, and
   clean-tree evidence.

Each checkpoint is independently committed and reviewed. The official acceptance may
pass on its first executable run only when all relevant production behavior was already
introduced RED-first; no synthetic failure is manufactured.

## 10. Hard stops

Stop rather than guess or weaken a test when:

- handoff checksums or the 145,393-row audit differ;
- overseas counts differ from 5,646 rows/IDs or an official group is not ETF/ETN;
- official public-fund acceptance counts differ from 95,619 rows, 11,139 raw IDs, 11,138 valid items,
  95,619 raw pairs, the single row 84,563 quarantine, zero duplicate/collision pairs,
  or zero non-attribute disagreement items;
- official acceptance data produces a normalized attribute collision despite the
  verified profile's zero-collision observation;
- implementation would require overseas/public-fund eligibility, generic truthiness,
  risk-system equivalence, family semantics, or inferred field applicable dates;
- the quality schema cannot validate the complete frozen domain issue;
- an unexplained regression appears in Task 2 or Task 3 behavior;
- a change would mutate official inputs, frozen audit values, artifacts, query/API
  behavior, or submission-frozen outputs.

The collision stop applies only to unexpected official-source evidence. Synthetic raw
duplicate and normalized-collision fixtures are required behavior tests: they must run
to the deterministic fail-closed issues/exclusion defined in section 6.3 and are never
a reason to halt implementation.

## 11. Out of scope and next task

Task 4 does not implement Parquet/DuckDB artifacts, persistence timestamps, dataset
quality-summary records, constant-metric materialization, exact domestic-fund links,
metric ranking/aggregation, field registries, entity resolution, query plans, evidence
records, answer rendering, API behavior, or HCX behavior.

The legacy file list's unowned `src/finproof/data/quarantine.py` is not created as an
empty utility bucket. A focused persistence adapter belongs to Task 5, when
`silver_quality_issue`, schema validation, and injected first-detection time have an
actual producer and testable consumer.

Task 4 completes only after its dedicated plan records RED/GREEN evidence, all official
acceptance invariants, independent reviews, mandatory gates, status evidence, and a
clean tree. The next incomplete item is Phase 1 Task 5: reproducible Parquet/DuckDB
artifacts and exact identifier links. Task 5 must inject quality persistence time and
preserve this design's logical reproducibility boundary.
