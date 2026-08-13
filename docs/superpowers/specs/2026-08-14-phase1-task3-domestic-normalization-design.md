# Phase 1 Task 3 Domestic Normalization Design

**Status:** Approved under the user's standing instruction to select the safest
recommended approach and continue without intermediate confirmation.

**Scope:** Normalize verified `PRBD01N001` domestic-bond rows and verified
`PREF01N001` domestic ETF/ETN rows into immutable typed domain records while
preserving exact raw value lineage. This task does not write artifacts, mutate
official inputs, normalize overseas products or public funds, or implement query/API
behavior.

## 1. Goal and selected approach

The Task 2 reader established a fail-closed `VerifiedSourceFile -> SourceRow`
boundary. Task 3 adds a pure, deterministic `SourceRow -> NormalizationResult[T]`
boundary.

Three representations were considered:

1. typed value wrappers embedded in product records;
2. plain typed DTOs plus an issue sidecar;
3. a dynamic normalized-field mapping.

The design selects option 1. Every transformed source field is a frozen
`NormalizedValue[T]` carrying the exact raw string, typed value, quality state,
versioned rule, and complete source-cell locator. Derived states use a separate
`DerivedValue[T]` carrying their explicit `as_of_date` and input locators. This is
more verbose than a plain DTO, but it is the only option that preserves the Source
Fidelity invariant at the value boundary without weakening static typing.

## 2. Frozen boundaries

- Inputs are only immutable `SourceRow` values produced by the verified Task 2
  reader or equivalent complete synthetic fixtures.
- Normalizers perform no filesystem, database, network, clock, or environment I/O.
- Raw values are never trimmed, replaced, or overwritten. Normalized text may be
  trimmed only in the typed value beside the raw string.
- `Decimal` is used for quantities, amounts, yields, fees, returns, duration, and
  prices. `float` is prohibited in normalization contracts.
- Financial dates use `date`; the domestic listed daily update timestamp uses a
  timezone-naive source `datetime` because the source contains no timezone.
- A field-level applicable date is not inferred from a nearby update column unless
  an explicit registry rule maps them. Task 3 preserves update columns separately
  and leaves the source cell's `applicable_date` unchanged.
- Missing optional metrics do not quarantine a product. Invalid mandatory identity
  or product-type fields do.
- `NormalizationResult.record is None` if and only if the row is quarantined.
- Official source files and `tests/contracts/expected_source_audit.json` remain
  immutable.

## 3. Shared domain contracts

### 3.1 Quality states

`QualityStatus(StrEnum)` contains the exact configured values:

```text
valid
missing_blank
missing_literal_null
sentinel_zero
sentinel_max_date
recorded_zero
recorded_zero_unverified
invalid_format
out_of_domain
constant_metric
stale
mixed_source_values
malformed_source_row
```

Task 3 uses only the states justified by its fields. `constant_metric` is not assigned
by a row normalizer; the later dataset-profile stage owns the assertion that every
nonblank value in a snapshot is constant.

`IssueSeverity(StrEnum)` contains `info`, `warning`, `high`, and `blocker`.

### 3.2 Complete locators

`SourceCellLocator` is a frozen strict Pydantic model containing:

```text
source_table
source_file                 # manifest-relative PurePosixPath
source_sheet
source_row_number           # Excel row
source_column_name
source_column_number        # Excel column
source_column_letter
source_checksum
source_snapshot_date
source_applicable_date      # copied exactly from SourceCell; normally None here
```

`SourceCellLocator.from_row(row, column_name)` performs an exact case-sensitive
lookup and combines row and cell lineage. It never accepts caller-invented path,
checksum, row, or column values.

### 3.3 Normalized and derived values

`NormalizedValue[T]` is frozen and contains:

```text
raw_value: str
normalized_value: T | None
quality_status: QualityStatus
rule_id: str
rule_version: str
source: SourceCellLocator
```

`DerivedValue[T]` is frozen and contains:

```text
value: T | None
quality_status: QualityStatus
rule_id: str
rule_version: str
as_of_date: date
inputs: tuple[SourceCellLocator, ...]
```

Neither wrapper invents an operational timestamp. Both reject empty rule IDs and
versions.

### 3.4 Quality issues and deterministic results

`DataQualityIssue` is frozen and contains:

```text
issue_id
rule_id
rule_version
severity
quality_status
source
reason
quarantined
raw_payload_sha256
first_detected_at           # None during pure normalization
```

`issue_id` is the lowercase SHA-256 of the versioned rule and exact safe locator.
`raw_payload_sha256` is the lowercase SHA-256 of the row's NUL-separated UTF-8 raw
payload. The raw payload and absolute paths never appear in issue messages.

The artifact-building phase will add a timezone-aware UTC `first_detected_at` when it
first persists an issue. Task 3 deliberately leaves it `None` so normalization stays
deterministic and clock-free. The repository JSON schema remains an artifact contract
and is resolved under A-011 before that artifact producer is implemented.

`NormalizationResult[T]` is a frozen generic Pydantic model:

```text
record: T | None
issues: tuple[DataQualityIssue, ...]
```

The model enforces that any `record=None` result contains at least one quarantined
issue and that a result with a record contains no quarantined issue.

## 4. Shared parsing behavior

All parsing helpers accept a `SourceRow` plus exact column name and return a
`NormalizedValue`.

### Text

- Raw text remains exact.
- Normalized text strips surrounding Unicode whitespace.
- Empty or whitespace-only text becomes `None` with `missing_blank`.
- Literal `NULL` is ordinary text unless the product-field contract explicitly
  declares it a missing token; neither domestic product contract does so.

### Identifiers

- Domestic bond `PD_NO` must be exactly 12 uppercase ASCII alphanumeric characters.
  Both `KR...` and the observed `XS...` identifier are allowed.
- Domestic listed `pd_itm_no` must be exactly 12 uppercase ASCII alphanumeric
  characters.
- Identifier normalization never trims or changes case. Any mismatch is
  `malformed_source_row`, severity `blocker`, and quarantines the row.

### Dates

The strict parser recognizes only eight ASCII digits in `YYYYMMDD` form:

- empty or whitespace-only -> `missing_blank`, typed `None`;
- `0` or `00000000` -> `sentinel_zero`, typed `None`;
- `99991231` when enabled for the field -> `sentinel_max_date`, typed `None`;
- impossible or non-eight-digit date -> `invalid_format`, typed `None`;
- calendar date -> `valid`, typed `date`.

`99991231` is enabled for bond maturity and domestic listing-end dates, not for
ordinary issue/listing/update dates.

The listed daily update column `du_upt_dt` is parsed only in exact
`YYYY-MM-DD HH:MM:SS` form. It is stored independently and is never silently reduced
to another field's applicable date.

### Decimals and integers

- Empty or whitespace-only -> `missing_blank`, typed `None`.
- Non-finite, malformed, or non-decimal text -> `invalid_format`, typed `None`.
- Exact zero -> the field's declared zero status.
- Other finite values -> `valid`.
- Integer fields accept decimal syntax only if the value is mathematically integral.

Per-field zero policy in this task:

```text
ordinary amount/yield/return/quantity/price/duration -> recorded_zero
domestic total fee                                  -> recorded_zero_unverified
domestic tracking error/difference rate             -> recorded_zero
```

Dataset-wide `constant_metric` is applied later, after distribution validation.

### Issues

Expected missing optional values and declared sentinels are represented in their
wrappers without emitting an issue. `invalid_format`, `out_of_domain`, and
`mixed_source_values` emit deterministic issues. Mandatory identity/type violations
emit blocker quarantine issues.

## 5. Rating registry

`RatingRegistry.from_yaml(path: Path)` strictly loads `config/rating_scale.yaml`.
It requires version `1.0.0`, immutable nonempty missing tokens, immutable canonical
ratings with positive integer ordinals, and aliases whose targets exist.

Smaller ordinals are stronger. `compare(left, right)` returns:

```text
-1  left is stronger
 0  equal ordinal
+1  left is weaker
```

Missing, unrated, or unmapped values raise `RatingNotComparableError`; they never
pass a minimum-grade filter. Aliases are applied exactly after surrounding whitespace
is removed. No unconfigured grade is inferred. In particular, official `C0` and
`CC0` remain `out_of_domain` because the frozen registry contains neither grade nor
alias.

For agency text, comma-separated tokens are trimmed and normalized independently.
`mixed_source_values` applies when comparable agency ordinals disagree with one
another or with the primary `CRD_GRD`. Same-ordinal configured forms such as `AA` and
`AA0` are not considered disagreement. Agency values never backfill a missing primary
grade.

## 6. Domestic bond normalization

Public interface:

```python
normalize_bond(
    row: SourceRow,
    as_of: date,
    rating_registry: RatingRegistry,
) -> NormalizationResult[BondInstrument]
```

The function rejects a non-`PRBD01N001` row as a programmer contract error. A
malformed `PD_NO` returns a quarantined result.

`BondInstrument` has native grain `instrument` and contains value wrappers for:

```text
product_id                  <- PD_NO
name                        <- PD_NM
short_name                  <- PD_ABRV_NM
currency                    <- CURR_CD
bond_kind_raw               <- BD_KND
issue_date                  <- ISU_DT
maturity_date               <- MAT_DT
source_update_date          <- PD_STD_INFO_UPDATE
coupon_rate                 <- SRFC_IRT
buy_yield                   <- BUY_YIELD
buyable_quantity            <- BUYABLE_QUANTITY
source_remaining_days       <- REMAINING_DAYS
credit_rating               <- CRD_GRD
credit_rating_agencies_raw  <- PD_EVCO_CRD_GRD
credit_rating_date          <- CRD_GRD_DT
duration                    <- DUR
evaluation_price            <- EVAL_PRICE
```

Bond currency accepts only an exact three-letter uppercase ASCII code. `000` and any
other shape are `out_of_domain`; the normalizer does not infer currency from country
or issuer.

Derived values:

```text
remaining_days_at_as_of
is_matured_at_as_of
has_positive_buyable_quantity
is_buyable_validated_at_as_of
```

Rules:

- `remaining_days_at_as_of = maturity_date - as_of` and may be negative. It is never
  copied from source `REMAINING_DAYS`.
- A bond is matured only when valid maturity is strictly before `as_of`; maturity on
  `as_of` has remaining days zero and is not yet classified as matured.
- `has_positive_buyable_quantity` is `None` if quantity is unavailable/invalid,
  otherwise the exact `> 0` predicate.
- Validated buyability is `True` only for positive quantity and valid maturity on or
  after `as_of`; explicit zero/negative quantity or an already matured bond is
  `False`; unresolved prerequisites produce `None`.
- A positive source quantity on a matured bond remains preserved and produces a
  warning rather than being overwritten.
- Answer-layer wording later distinguishes snapshot source quantity from real-time
  order availability.

## 7. Domestic ETF/ETN normalization

Public interface:

```python
normalize_domestic_listed(
    row: SourceRow,
    as_of: date,
) -> NormalizationResult[ListedProduct]
```

The function rejects a non-`PREF01N001` row as a programmer contract error. A
malformed `pd_itm_no` or a product group other than exact `ETF`/`ETN` quarantines the
row. `ListedProductType` preserves ETF and ETN as distinct values.

`ListedProduct` has native grain `listed_product` and contains wrappers for:

```text
product_id        <- pd_itm_no
market_identifier <- pd_itm_no_ma
product_type      <- pd_grp_no
name              <- pd_nm
short_name        <- pd_abrv_nm
currency          <- pd_curr_cd
listing_date      <- pd_lstg_dt
listing_end_date  <- pd_lste_dt
sale_flag         <- pd_sale_yn
suspension_flag   <- pd_tr_yn
aum_primary       <- pd_net_tamt
aum_secondary     <- du_last_aum
total_fee         <- cu_charge_rt
tracking_error    <- du_chas_errt
difference_rate   <- du_diff_rt
return_1d         <- du_er_1d
return_1m         <- du_er_1m
return_3m         <- du_er_3m
return_6m         <- du_er_6m
return_1y         <- du_er_1y
return_ytd        <- du_er_ytd
risk_code         <- pd_risk_cd
risk_name         <- pd_risk_nm
base_index        <- cu_base_index
manager           <- cu_fund_mgmt_co
asset_type        <- wu_inv_ast_type
region            <- wu_inv_rgn
custom_update_date <- cu_upt_dt
daily_update_at   <- du_upt_dt
weekly_update_date <- wu_upt_dt
```

`pd_net_tamt` is always the primary AUM. `du_last_aum` remains diagnostic and never
replaces a missing primary value.

Domestic listed currency uses an explicit allowlist: `CURR_CD_KRW -> KRW`. Blank is
`missing_blank`; `CURR_CD_000` and every unregistered code are `out_of_domain`. The
normalizer never derives currency from the Korean name or assumes every domestic
listing is KRW.

State flags are exact strings:

```text
pd_sale_yn = "1" -> sale enabled
pd_sale_yn = "0" -> sale disabled
pd_tr_yn   = "0" -> not suspended
pd_tr_yn   = "1" -> suspended
```

Other or blank flag values are `out_of_domain`; they are not truthy/falsy guesses.

`is_eligible_at_as_of: DerivedValue[bool]` follows D-007 and the frozen state rule:

- sale enabled;
- not suspended;
- valid listing date not after `as_of`;
- listing end is `99991231`, blank, or a valid date not before `as_of`.

An explicit disqualifying state yields `False`. If there is no explicit disqualifier
but a required prerequisite is unknown/invalid, the derived value is `None`; unknown
is never silently treated as eligible.

## 8. Official snapshot observations used by acceptance tests

These observations are verified from the checksum-locked `2026-07-11` inputs and are
acceptance evidence, not hidden correction lists:

- `PRBD01N001`: 42,394 rows, 42,394 unique valid 12-character IDs; 42,393 begin `KR`
  and one begins `XS`.
- `PREF01N001`: 1,734 rows and unique raw IDs; 1,733 valid 12-character IDs and one
  malformed `KR` row at Excel row 1,155, which is quarantined.
- Domestic listed product groups are 1,202 ETF and 532 ETN source rows.
- Bond `MAT_DT` contains valid dates, blank, `0`, and `99991231`; all remain distinct.
- Domestic `du_chas_errt` nonblank values are recorded zero in this snapshot, but the
  row normalizer records zero rather than assigning the dataset-level
  `constant_metric` state.
- Bond primary grades `C0` and `CC0` are present but unregistered; they remain
  out-of-domain and non-comparable.

The official acceptance test exhausts both verified readers and proves:

```text
42,394 bond records, zero quarantined bond rows
1,733 domestic listed records, one quarantined domestic row
record identity uniqueness within each produced native grain
complete raw/locator preservation for every wrapped field
no unexpected exception across all 44,128 source rows
```

It does not freeze every quality-issue count; rule refinements may legitimately add a
warning without changing product identity or raw values.

## 9. Error handling and security

- Product text is untrusted data and is never executed or interpreted as an
  instruction.
- Public issue reasons use fixed safe messages and never contain raw payloads,
  absolute paths, or stack traces.
- A wrong source table is a programming contract violation and raises a typed
  `NormalizationContractError`; a bad row within the expected table is represented by
  a deterministic result/issue.
- Rating YAML failures become typed registry configuration errors without dumping the
  file content.
- Normalization performs no logging of full questions or product payloads.

## 10. Testing strategy

Every production behavior is introduced with observed RED -> GREEN evidence.

Test layers for this task:

1. shared wrapper/parser tests for exact raw retention, date states, finite Decimal,
   integral parsing, deterministic issues, and normalization-result invariants;
2. strict rating-registry tests for aliases, ordinal comparison, missing/unmapped
   behavior, immutability, malformed YAML, and version rejection;
3. bond tests for raw-vs-derived remaining days, all date states, rating disagreement,
   missing/unmapped ratings, matured positive quantity, currency, and quarantine;
4. domestic listed tests for ETF/ETN identity, exact flags, listing boundaries,
   tri-state eligibility, primary/secondary AUM, zero policies, currency, and
   quarantine;
5. official full-source acceptance for the counts and invariants in section 8;
6. Ruff, mypy, complete pytest, source audit, handoff, schema catalog, and pre-commit
   gates.

Tests construct complete `SourceRow` fixtures and exercise real normalizers. No test
directly instantiates an incomplete source locator or mocks parsing behavior.

## 11. Delivery boundary and next task

Task 3 completes when the two official domestic datasets normalize under the contracts
above, the task is independently reviewed, `docs/implementation/STATUS.md` records
the observed evidence, and the branch passes all mandatory gates.

The next incomplete Phase 1 item is Task 4: overseas-listed and public-fund
normalization with the fund item/attribute split and quarantine-schema resolution.
Task 3 does not start that work.
