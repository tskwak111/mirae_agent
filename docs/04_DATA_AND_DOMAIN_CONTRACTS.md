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

`top_k_scope=global` is permitted only for one compatibility partition. `top_k_scope=per_product_type` applies the limit independently to each product type; currency or metric policy may split a type further. Clauses are distributed through the field/metric registry. A clause that maps to no selected type, or whose meaning is materially ambiguous, requires clarification or an unsupported result rather than a guessed union.

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
domestic_etf.pd_itm_no == public_fund.ksd_itm_no
```

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
artifacts/parquet/bronze_*.parquet
artifacts/parquet/silver_*.parquet
artifacts/parquet/silver_quality_issue.parquet
artifacts/finproof.duckdb
```

The database is read-only at API runtime. Artifact checksums and registry versions are included in `/version` and each execution trace.
