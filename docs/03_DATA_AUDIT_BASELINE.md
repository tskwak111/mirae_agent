# Official Source Data Audit Baseline

## 1. Purpose

These are immutable acceptance baselines for the supplied workbooks. They are not claims that every source value is economically valid. They prove that ingestion sees the same source and that known data semantics are handled intentionally.

Reproduce with:

```bash
python tools/audit_source_data.py --check
```

Canonical machine-readable values live in `tests/contracts/expected_source_audit.json`.

## 2. Files and official total

| Table | File | Source rows |
|---|---|---:|
| PRBD01N001 | domestic bonds | 42,394 |
| PREF01N001 | domestic ETF/ETN | 1,734 |
| PREF02N001 | overseas ETF/ETN | 5,646 |
| PRFD01N001 | public funds | 95,619 |
| **Total** |  | **145,393** |

Snapshot: `2026-07-11`.

## 3. Domestic bonds — PRBD01N001

| Audit | Expected |
|---|---:|
| rows | 42,394 |
| unique `PD_NO` | 42,394 |
| nonblank `BUY_YIELD` | 881 |
| nonblank `BUYABLE_QUANTITY` | 881 |
| positive `BUYABLE_QUANTITY` | 325 |
| positive quantity with maturity before snapshot | 71 |
| positive quantity not matured at snapshot | 254 |
| nonblank `REMAINING_DAYS` | 31,749 |
| `MAT_DT = 0` | 316 |
| `MAT_DT = 99991231` | 4 |
| blank `MAT_DT` | 3 |
| raw distinct `BD_KND` | 52 |
| trimmed distinct `BD_KND` | 40 |
| positive-quantity rows missing both rating fields | 223 |
| rows with differing multi-agency ratings | 286 |
| rows where `MAT_DT - REMAINING_DAYS` infers 2026-02-24 | 20,127 |
| rows with `PD_STD_INFO_UPDATE = 20260224` | 20,160 |

The inferred date is an arithmetic observation, not an official field definition. Store it as an audit finding, not as authoritative metadata.

## 4. Domestic ETF/ETN — PREF01N001

| Audit | Expected |
|---|---:|
| rows | 1,734 |
| `pd_grp_no = ETF` | 1,202 |
| `pd_grp_no = ETN` | 532 |
| ETF active under frozen snapshot rule | 1,139 |
| ETN active under frozen snapshot rule | 381 |
| nonblank base index | 58 |
| nonblank total fee | 217 |
| positive total fee | 67 |
| zero total fee | 150 |
| nonblank tracking error | 1,551 |
| tracking error values equal zero | 1,551 |
| nonblank difference rate | 1,517 |
| difference-rate values equal zero | 1,517 |
| positive `pd_net_tamt` | 1,551 |
| positive `du_last_aum` | 1,042 |
| exact -100% one-month return | 20 |
| exact -100% three-month return | 37 |
| exact -100% six-month return | 53 |
| exact -100% one-year return | 98 |
| exact -100% YTD return | 44 |

Frozen active-state rule:

```text
pd_sale_yn = 1
pd_tr_yn = 0
listing start is not after as-of
listing end is not before as-of, with 99991231 treated as open-ended
```

## 5. Overseas ETF/ETN — PREF02N001

| Audit | Expected |
|---|---:|
| rows | 5,646 |
| ETF | 5,587 |
| ETN | 59 |
| nonblank base index | 5,638 |
| nonblank manager | 5,638 |
| nonblank strategy | 5,638 |
| nonblank asset type | 5,638 |
| nonblank region | 5,638 |
| positive total fee | 5,283 |
| zero total fee | 363 |
| nonblank one-day return | 5,388 |
| one-day returns equal zero | 5,388 |
| nonblank AUM | 5,459 |
| positive AUM | 5,451 |
| nonblank replication method | 2,360 |
| nonblank leverage factor | 0 |
| rows with trading currency USD | 5,646 |

A recorded fee of zero remains raw evidence but receives `recorded_zero_unverified`; operation policy determines comparison behavior.

## 6. Public funds — PRFD01N001

| Audit | Expected |
|---|---:|
| source attribute rows | 95,619 |
| unique `itm_no` | 11,139 |
| normal-format `itm_no` | 11,138 |
| malformed `itm_no` | 1 |
| unique `(itm_no, prfd_attr_cd)` | 95,619 |
| duplicate `(itm_no, prfd_attr_cd)` | 0 |
| maximum attributes for one item | 16 |
| items with non-attribute field disagreement | 0 |
| literal `"NULL"` risk rows | 18,416 |
| items with literal `"NULL"` risk | 2,573 |
| `or_attr_desc = 06` rows | 5,436 |
| items with `or_attr_desc = 06` | 686 |
| rows whose name contains `ETF` | 1,260 |
| items whose name contains `ETF` | 113 |
| rows whose name contains `상장지수` | 423 |
| items whose name contains `상장지수` | 62 |
| union of ETF/상장지수 named items | 175 |
| below -100 return source rows for affected metric | 5 |
| distinct affected item | 1 |
| KRW source rows | 95,046 |
| USD source rows | 572 |
| blank/malformed currency rows | 1 |
| KRW items | 11,067 |
| USD items | 71 |
| blank/malformed currency items | 1 |
| `sale_yn = 판매중` source rows | 76,318 |
| `sale_yn = 판매완료` source rows | 19,300 |
| `thco_sale_yn = Y` source rows | 91,594 |

Known malformed source row is Excel row `84563` with a one-character `itm_no` and shifted/invalid fields. Preserve it in Bronze, quarantine it from normal item views, and test its exclusion.

## 7. Exact cross-source link

Exactly 47 products satisfy:

```text
PREF01N001.pd_itm_no = PRFD01N001.ksd_itm_no
```

Only these exact identifier matches may be automatically linked by the initial evaluation implementation. Name/AUM similarity produces candidates only.

## 8. Sample `axis_*` warning

Schema sample sheets contain derived `axis_*` fields, but they are not declared as mandatory official truth. At least one sample mapping is semantically questionable. Treat them as vocabulary/design hints, not training labels or filtering ground truth.
