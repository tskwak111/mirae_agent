# Data and Domain Contracts

## 1. Source contract

Every workbook is identified by manifest entry, SHA-256 checksum, expected sheet, header, row count, and table ID. Source files are never modified in place.

Every ingested row receives:

```text
source_table
source_file
source_sheet
source_row_number        # Excel row number, header is row 1
source_checksum
source_snapshot_date
raw_payload
```

Quality processing emits issues; it does not erase raw evidence.

## 2. Shared value states

Do not collapse these states:

```text
missing_blank
missing_literal_null
sentinel_zero
sentinel_max_date
recorded_zero
recorded_zero_unverified
valid
invalid_format
out_of_domain
constant_metric
stale
mixed_source_values
malformed_source_row
```

A normalized value may be null while its raw value and quality state remain available.

## 3. Shared identity, grain, and cross-product contract

Native grains are fixed:

```text
domestic_bond                          -> instrument
domestic_etf / domestic_etn            -> listed_product
overseas_etf / overseas_etn            -> listed_product
public_fund default                     -> fund_item
public_fund attribute question          -> fund_attribute
explicit fund-class consolidation       -> fund_family_candidate
heterogeneous cross-product response    -> product
```

`product` is a response envelope, not a normalized physical product table and not permission to union incomparable columns. A validated multi-product request becomes an `ExecutionBundle` with one native `ExecutionSegment` per product type. Each segment retains product type, native grain, typed clauses, top-k, compatibility partition, and evidence requirements.

`top_k_scope=global` is permitted only for one final compatibility partition. `top_k_scope=per_product_type` applies the limit independently to each final compatibility partition within each product type; currency or metric policy may split a type further and every split is traced. The fixed order is entity resolution and literal filtering, product-specific state and metric eligibility, compatibility partitioning, aggregate or rank/tie calculation, then `top_k`. Clauses are distributed through the field/metric registry. A clause that maps to no selected type, or whose meaning is materially ambiguous, requires clarification or an unsupported result rather than a guessed union.

An aggregate request contains one `AggregationSpec`. `count` counts the native result grain and has no target field. `min`, `max`, `sum`, and `avg` require one field whose registry entry authorizes that operation. At most two canonical fields may form the group key. Aggregate output preserves typed group keys, the typed aggregate value, included/excluded counts, policy IDs, and bounded evidence-summary identity.

## 4. Domestic bond contract

### Identity and fields

```text
product_id                  <- PD_NO
name                        <- PD_NM
short_name                  <- trimmed PD_ABRV_NM
currency                    <- CURR_CD
bond_kind_raw               <- BD_KND
issue_date                  <- ISU_DT when valid
maturity_date               <- MAT_DT when valid and not sentinel
coupon_rate                 <- SRFC_IRT
buy_yield                   <- BUY_YIELD
buyable_quantity            <- BUYABLE_QUANTITY
source_remaining_days       <- REMAINING_DAYS
source_update_date          <- PD_STD_INFO_UPDATE
credit_rating_normalized    <- CRD_GRD through rating registry
credit_rating_agencies_raw  <- PD_EVCO_CRD_GRD
duration                    <- DUR
evaluation_price            <- EVAL_PRICE
```

### Derived fields

```text
remaining_days_at_as_of = maturity_date - as_of_date
is_matured_at_as_of
has_positive_buyable_quantity
is_buyable_validated_at_as_of
rating_status
```

### Rules

- blank, `0`, `99991231`, invalid date, and valid date are distinct.
- trim padded names/kinds for normalized fields while retaining raw text.
- `CRD_GRD` is the normalized filtering field when present.
- do not infer AAA or another rating for government bonds.
- preserve agency text; differing ratings receive `mixed_rating`.
- source buyability means positive recorded quantity.
- validated buyability additionally requires a valid non-matured date at the query as-of.
- answer wording distinguishes source quantity from actual real-time order availability.

## 5. Domestic ETF/ETN contract

### Identity/state

```text
product_id        <- pd_itm_no
market_identifier <- pd_itm_no_ma
product_group     <- pd_grp_no
name              <- pd_nm
short_name        <- pd_abrv_nm
currency          <- pd_curr_cd
listing_date      <- pd_lstg_dt
listing_end_date  <- pd_lste_dt
sale_flag         <- pd_sale_yn
suspension_flag   <- pd_tr_yn
```

### Frozen state at `as_of`

```text
pd_sale_yn = "1"
pd_tr_yn = "0"             # not suspended under supplied schema
valid listing date is not after as_of
valid end date is not before as_of
99991231 means no known end date
```

A plain ETF query adds `pd_grp_no = "ETF"`.

### Metrics

```text
aum_primary       <- pd_net_tamt
aum_secondary     <- du_last_aum
total_fee         <- cu_charge_rt
tracking_error     <- du_chas_errt
difference_rate   <- du_diff_rt
return_1d         <- du_er_1d
return_1m         <- du_er_1m
return_3m         <- du_er_3m
return_6m         <- du_er_6m
return_1y         <- du_er_1y
return_ytd        <- du_er_ytd
risk_code/name    <- pd_risk_cd / pd_risk_nm
base_index        <- cu_base_index
manager           <- cu_fund_mgmt_co
asset_type        <- wu_inv_ast_type
region            <- wu_inv_rgn
```

Constant tracking/difference metrics are queryable as recorded values but cannot produce a unique primary ranking. Exact `-100` returns remain raw values; active/sale state and metric quality determine rank eligibility.

## 6. Overseas ETF/ETN contract

### Identity

```text
product_id        <- pd_itm_no
market_identifier <- pd_itm_no_ma
ticker            <- pd_abrv_nm
isin              <- pd_isin_cd
name              <- pd_nm
product_group     <- pd_grp_no
```

### Fields

```text
currency          <- pd_trd_ccy
listing_date      <- pd_lstg_dt
sale_flag         <- pd_sale_yn
suspension_flag   <- pd_tr_yn
total_fee         <- cu_charge_rt
aum               <- du_last_aum
base_index        <- cu_base_index
manager           <- cu_fund_mgmt_co
strategy           <- cu_strtegy
replication       <- cu_index_repl_mthd
asset_type        <- wu_inv_ast_type
region            <- wu_inv_rgn
return_1d         <- du_er_1d
close_price/date  <- du_clpr / du_clpr_base_dt
```

All rows use USD trading currency in this snapshot, but the implementation must still read the field rather than hardcode USD.

Recorded zero fee uses `recorded_zero_unverified`. One-day return is constant zero among available rows and follows tie policy.

## 7. Public-fund contract

### Source attribute table

```text
PK = (itm_no, prfd_attr_cd)
```

There are 95,619 unique source attribute rows.

### Fund item table

```text
PK = itm_no
```

There are 11,139 source item IDs and 11,138 valid-format items after one malformed row is quarantined. All non-attribute fields are identical within each valid `itm_no` in this snapshot; item construction selects a deterministic representative while retaining every evidence locator.

### Core fields

```text
fund_item_id         <- itm_no
name                 <- itm_nm
short_name           <- itm_abrv_nm
currency             <- curr_cd
net_assets           <- fd_nast_suma
fund_type_raw         <- or_attr_desc
region_description   <- fd_ivst_rgn_desc
risk_code             <- zrin_fd_ivst_risk_gcd
risk_name             <- zrin_fd_ivst_risk_grd_nm
sale_status           <- sale_yn
mirae_sale_flag       <- thco_sale_yn
ksd_id                <- ksd_itm_no
standard_item_id      <- std_itm_no
family_candidate_key  <- rptt_ksd_itm_no
returns               <- fd_wk1_ern_r, fd_mm1_ern_r, fd_mm3_ern_r,
                         fd_mm6_ern_r, fd_mm18_ern_r, fd_yr1_ern_r,
                         fd_yr2_ern_r, fd_yr3_ern_r, fd_yr5_ern_r
```

### Rules

- literal string `NULL` in risk fields normalizes to missing with its own quality state.
- `or_attr_desc = "06"` is an unmapped code, not a guessed fund type.
- default search/rank grain is `fund_item`.
- the source attribute list remains available for attribute questions.
- family candidate grouping is never an automatic default.
- AUM rankings separate KRW and USD unless a fixed FX policy is explicitly selected.
- the malformed source row remains in Bronze and quality reports but not normal product results.

## 8. Cross-source links

Initial automatic link rule:

```text
domestic_etf.pd_itm_no raw value == public_fund.ksd_itm_no representative raw value
```

The rule is version `1.0.0`, applies only to source-declared domestic ETFs, and emits
one link at the public-fund `itm_no` grain. It never trims an identifier to create a
match. Each link preserves the left `pd_itm_no` locator and every agreeing public-fund
`ksd_itm_no` locator. Repeated attribute rows add evidence, not links; a one-to-many
identifier conflict blocks artifact publication.

Link metadata:

```text
left_table
left_product_id
right_table
right_product_id
link_type = exact_identifier
confidence = 1.0
rule_version
source evidence
```

All other matches are candidates requiring explicit review or clarification.

## 9. Quarantine contract

A quarantined record includes:

```text
issue_id
source locator
rule_id and version
severity
raw payload/hash
human-readable reason
first_detected_at
```

Quarantine is deterministic and testable. It is not a manual hidden deletion list.

## 10. Artifact contract

Phase 1 outputs:

```text
artifacts/manifest.json
artifacts/reports/source_audit.json
artifacts/reports/quality_summary.json
artifacts/parquet/bronze_source_column.parquet
artifacts/parquet/bronze_source_row.parquet
artifacts/parquet/bronze_source_cell.parquet
artifacts/parquet/silver_bond_instrument.parquet
artifacts/parquet/silver_domestic_listed_product.parquet
artifacts/parquet/silver_overseas_listed_product.parquet
artifacts/parquet/silver_fund_item.parquet
artifacts/parquet/silver_fund_item_attribute.parquet
artifacts/parquet/silver_quality_issue.parquet
artifacts/parquet/gold_exact_cross_source_link.parquet
artifacts/parquet/gold_exact_cross_source_link_evidence.parquet
artifacts/finproof.duckdb
```

Bronze preserves all 145,393 source rows, 6,401,851 source cells, and 207 catalog
columns, including quarantined rows. Wide Silver typed columns are the query projection;
the canonical strict-model `record_json` is the authoritative raw/normalized/rule/
quality/lineage serialization. Task 5 does not create metric, family, eligibility,
state, alias, fuzzy, search, or runtime-evidence tables.

The artifact manifest separates two identities:

- physical file and database SHA-256 values prove the integrity of one published
  generation;
- canonical table and manifest logical hashes prove data reproducibility after the one
  injected UTC persistence timestamp is replaced with null and artifact output path/
  size/compression/physical-hash fields are excluded.

The timestamp-free source-audit and quality-summary reports each have a closed semantic
report ID and canonical logical hash included in overall identity; physical report
paths are excluded. Verification recomputes
Parquet schema/count/order/uniqueness/logical hashes, both report hashes, and the overall
logical hash, then proves each self-contained DuckDB table is exactly equal to its
verified Parquet relation. Evaluation additionally compares the result with the
separately tracked and packaged `config/expected_phase1_artifacts.json`; matching only
physical hashes or row counts is insufficient.

The database is self-contained and read-only at API runtime. A build is staged and
fully verified before guarded offline publication; `--clean` may replace only an
already verified FinProof artifact root with the exact recursive physical inventory;
any extra/link/special entry makes clean refuse without changing target bytes. A failed
promotion rolls back. Runtime
files under `artifacts/` are generated and untracked. The repository tracks a
timestamp-free expected logical contract at
`config/expected_phase1_artifacts.json` instead. Artifact checksums and registry
versions are included in `/version` and each execution trace.

Only a repository-only, non-packaged candidate builder may bootstrap the initially
absent expected contract: it fully verifies a temporary, unpublished artifact set,
cannot write the baseline, and refuses once the expected file/resource exists. After a
new target commits, old-generation cleanup first atomically renames the verified backup
to an exact marked tombstone; partial recursive cleanup never rolls back the new target.

The exact implementation contract, table schemas, sort keys, hashing rules, and stop
conditions are frozen in
`docs/superpowers/specs/2026-08-14-phase1-task5-artifact-build-design.md`.
