#!/usr/bin/env python3
"""Reproduce the frozen FinProof official-source audit without production code."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from tools.xlsx_stream import iter_table_dicts
elif __package__:
    from .xlsx_stream import iter_table_dicts
else:
    from xlsx_stream import iter_table_dicts

SNAPSHOT: Final = date(2026, 7, 11)
ROOT: Final = Path(__file__).resolve().parents[1]
DATA: Final = ROOT / "source_material" / "data"
EXPECTED: Final = ROOT / "tests" / "contracts" / "expected_source_audit.json"


def clean(value: str) -> str:
    return value.strip()


def nonblank(value: str) -> bool:
    return clean(value) != ""


def decimal_or_none(value: str) -> Decimal | None:
    text = clean(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_yyyymmdd(value: str) -> date | None:
    text = clean(value)
    if text in {"", "0", "00000000", "99991231"}:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def audit_bonds() -> tuple[dict[str, Any], set[str]]:
    path = DATA / "PRBD01N001_domestic_bonds_20260711_datarows.xlsx"
    rows = 0
    ids: set[str] = set()
    buy_yield_nonblank = 0
    quantity_nonblank = 0
    quantity_positive = 0
    positive_matured_before_snapshot = 0
    positive_not_matured_at_snapshot = 0
    remaining_nonblank = 0
    maturity_zero = 0
    maturity_max = 0
    maturity_blank = 0
    bond_kind_raw: set[str] = set()
    bond_kind_trimmed: set[str] = set()
    positive_missing_both_ratings = 0
    mixed_multi_agency_ratings = 0
    inferred_base_20260224 = 0
    update_20260224 = 0

    for _, row in iter_table_dicts(path):
        rows += 1
        ids.add(clean(row["PD_NO"]))
        if nonblank(row["BUY_YIELD"]):
            buy_yield_nonblank += 1
        if nonblank(row["BUYABLE_QUANTITY"]):
            quantity_nonblank += 1
        quantity = decimal_or_none(row["BUYABLE_QUANTITY"])
        maturity = parse_yyyymmdd(row["MAT_DT"])
        if quantity is not None and quantity > 0:
            quantity_positive += 1
            if maturity is not None and maturity < SNAPSHOT:
                positive_matured_before_snapshot += 1
            if maturity is not None and maturity >= SNAPSHOT:
                positive_not_matured_at_snapshot += 1
            if not nonblank(row["CRD_GRD"]) and not nonblank(row["PD_EVCO_CRD_GRD"]):
                positive_missing_both_ratings += 1
        if nonblank(row["REMAINING_DAYS"]):
            remaining_nonblank += 1
        mat_raw = clean(row["MAT_DT"])
        maturity_zero += int(mat_raw == "0")
        maturity_max += int(mat_raw == "99991231")
        maturity_blank += int(mat_raw == "")
        bond_kind_raw.add(row["BD_KND"])
        bond_kind_trimmed.add(clean(row["BD_KND"]))

        agency_tokens = [
            token.strip() for token in row["PD_EVCO_CRD_GRD"].split(",") if token.strip()
        ]
        if len(set(agency_tokens)) > 1:
            mixed_multi_agency_ratings += 1

        remaining = decimal_or_none(row["REMAINING_DAYS"])
        if (
            maturity is not None
            and remaining is not None
            and remaining == remaining.to_integral_value()
            and maturity - timedelta(days=int(remaining)) == date(2026, 2, 24)
        ):
            inferred_base_20260224 += 1
        if clean(row["PD_STD_INFO_UPDATE"]) == "20260224":
            update_20260224 += 1

    return (
        {
            "rows": rows,
            "unique_pd_no": len(ids),
            "buy_yield_nonblank": buy_yield_nonblank,
            "buyable_quantity_nonblank": quantity_nonblank,
            "buyable_quantity_positive": quantity_positive,
            "positive_quantity_matured_before_snapshot": positive_matured_before_snapshot,
            "positive_quantity_not_matured_at_snapshot": positive_not_matured_at_snapshot,
            "remaining_days_nonblank": remaining_nonblank,
            "maturity_date_zero": maturity_zero,
            "maturity_date_99991231": maturity_max,
            "maturity_date_blank": maturity_blank,
            "bond_kind_distinct_raw": len(bond_kind_raw),
            "bond_kind_distinct_trimmed": len(bond_kind_trimmed),
            "positive_quantity_missing_both_ratings": positive_missing_both_ratings,
            "mixed_multi_agency_rating_rows": mixed_multi_agency_ratings,
            "remaining_days_infers_20260224": inferred_base_20260224,
            "pd_std_info_update_20260224": update_20260224,
        },
        ids,
    )


def listed_active(row: dict[str, str]) -> bool:
    if clean(row["pd_sale_yn"]) != "1" or clean(row["pd_tr_yn"]) != "0":
        return False
    listing = parse_yyyymmdd(row["pd_lstg_dt"])
    end_raw = clean(row["pd_lste_dt"])
    end = parse_yyyymmdd(end_raw)
    if listing is not None and listing > SNAPSHOT:
        return False
    return end_raw in {"", "99991231"} or end is None or end >= SNAPSHOT


def audit_domestic_listed() -> tuple[dict[str, Any], set[str]]:
    path = DATA / "PREF01N001_domestic_etf_20260711_datarows.xlsx"
    counters: Counter[str] = Counter()
    ids: set[str] = set()
    tracking_values: list[Decimal] = []
    difference_values: list[Decimal] = []

    for _, row in iter_table_dicts(path):
        counters["rows"] += 1
        product_id = clean(row["pd_itm_no"])
        ids.add(product_id)
        group = clean(row["pd_grp_no"])
        counters[f"group_{group}"] += 1
        if listed_active(row):
            counters[f"active_{group}"] += 1
        if nonblank(row["cu_base_index"]):
            counters["base_index_nonblank"] += 1
        fee = decimal_or_none(row["cu_charge_rt"])
        if fee is not None:
            counters["fee_nonblank"] += 1
            counters["fee_positive"] += int(fee > 0)
            counters["fee_zero"] += int(fee == 0)
        tracking = decimal_or_none(row["du_chas_errt"])
        if tracking is not None:
            counters["tracking_nonblank"] += 1
            tracking_values.append(tracking)
        difference = decimal_or_none(row["du_diff_rt"])
        if difference is not None:
            counters["difference_nonblank"] += 1
            difference_values.append(difference)
        for field, name in (
            ("pd_net_tamt", "pd_net_tamt_positive"),
            ("du_last_aum", "du_last_aum_positive"),
        ):
            value = decimal_or_none(row[field])
            counters[name] += int(value is not None and value > 0)
        for field, name in (
            ("du_er_1m", "return_1m_exact_minus_100"),
            ("du_er_3m", "return_3m_exact_minus_100"),
            ("du_er_6m", "return_6m_exact_minus_100"),
            ("du_er_1y", "return_1y_exact_minus_100"),
            ("du_er_ytd", "return_ytd_exact_minus_100"),
        ):
            counters[name] += int(decimal_or_none(row[field]) == Decimal("-100"))

    result: dict[str, Any] = dict(counters)
    result["tracking_values_equal_zero"] = sum(value == 0 for value in tracking_values)
    result["difference_values_equal_zero"] = sum(value == 0 for value in difference_values)
    result["unique_product_ids"] = len(ids)
    return result, ids


def audit_overseas_listed() -> tuple[dict[str, Any], set[str]]:
    path = DATA / "PREF02N001_overseas_etf_20260711_datarows.xlsx"
    counters: Counter[str] = Counter()
    ids: set[str] = set()
    return_values: list[Decimal] = []

    for _, row in iter_table_dicts(path):
        counters["rows"] += 1
        ids.add(clean(row["pd_itm_no"]))
        group = clean(row["pd_grp_no"])
        counters[f"group_{group}"] += 1
        for field, name in (
            ("cu_base_index", "base_index_nonblank"),
            ("cu_fund_mgmt_co", "manager_nonblank"),
            ("cu_strtegy", "strategy_nonblank"),
            ("wu_inv_ast_type", "asset_type_nonblank"),
            ("wu_inv_rgn", "region_nonblank"),
            ("cu_index_repl_mthd", "replication_nonblank"),
            ("cu_lev_fector", "leverage_factor_nonblank"),
        ):
            counters[name] += int(nonblank(row[field]))
        fee = decimal_or_none(row["cu_charge_rt"])
        if fee is not None:
            counters["fee_positive"] += int(fee > 0)
            counters["fee_zero"] += int(fee == 0)
        one_day = decimal_or_none(row["du_er_1d"])
        if one_day is not None:
            counters["return_1d_nonblank"] += 1
            return_values.append(one_day)
        aum = decimal_or_none(row["du_last_aum"])
        if aum is not None:
            counters["aum_nonblank"] += 1
            counters["aum_positive"] += int(aum > 0)
        counters["currency_usd"] += int(clean(row["pd_trd_ccy"]) == "USD")

    result: dict[str, Any] = dict(counters)
    result["return_1d_values_equal_zero"] = sum(value == 0 for value in return_values)
    result["unique_product_ids"] = len(ids)
    return result, ids


def audit_public_funds(domestic_ids: set[str]) -> tuple[dict[str, Any], set[str]]:
    path = DATA / "PRFD01N001_public_funds_20260711_datarows.xlsx"
    rows = 0
    items: set[str] = set()
    valid_items: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    attributes_per_item: Counter[str] = Counter()
    first_non_attribute: dict[str, tuple[str, ...]] = {}
    non_attribute_disagreements: set[str] = set()
    literal_null_risk_rows = 0
    literal_null_risk_items: set[str] = set()
    type_06_rows = 0
    type_06_items: set[str] = set()
    etf_name_rows = 0
    etf_name_items: set[str] = set()
    index_name_rows = 0
    index_name_items: set[str] = set()
    below_minus_100_rows = 0
    below_minus_100_items: set[str] = set()
    currency_rows: Counter[str] = Counter()
    currency_by_item: dict[str, str] = {}
    sale_rows: Counter[str] = Counter()
    own_sale_rows: Counter[str] = Counter()
    malformed_excel_rows: list[int] = []
    fund_ksd_ids: set[str] = set()

    return_fields = ("fd_mm18_ern_r", "fd_yr2_ern_r", "fd_yr3_ern_r", "fd_yr5_ern_r")
    valid_pattern = re.compile(r"^[A-Z0-9]{12}$")

    for excel_row, row in iter_table_dicts(path):
        rows += 1
        item = clean(row["itm_no"])
        attribute = clean(row["prfd_attr_cd"])
        items.add(item)
        pairs.add((item, attribute))
        attributes_per_item[item] += 1
        if valid_pattern.fullmatch(item):
            valid_items.add(item)
        else:
            malformed_excel_rows.append(excel_row)

        non_attribute_tuple = tuple(row[column] for column in row if column != "prfd_attr_cd")
        previous = first_non_attribute.setdefault(item, non_attribute_tuple)
        if previous != non_attribute_tuple:
            non_attribute_disagreements.add(item)

        risk = clean(row["zrin_fd_ivst_risk_gcd"])
        if risk == "NULL":
            literal_null_risk_rows += 1
            literal_null_risk_items.add(item)
        if clean(row["or_attr_desc"]) == "06":
            type_06_rows += 1
            type_06_items.add(item)
        name = row["itm_nm"]
        if "ETF" in name.upper():
            etf_name_rows += 1
            etf_name_items.add(item)
        if "상장지수" in name:
            index_name_rows += 1
            index_name_items.add(item)
        if any(
            (value := decimal_or_none(row[field])) is not None and value < -100
            for field in return_fields
        ):
            below_minus_100_rows += 1
            below_minus_100_items.add(item)

        currency = clean(row["curr_cd"])
        currency_rows[currency] += 1
        currency_by_item.setdefault(item, currency)
        sale_rows[clean(row["sale_yn"])] += 1
        own_sale_rows[clean(row["thco_sale_yn"])] += 1
        ksd = clean(row["ksd_itm_no"])
        if ksd:
            fund_ksd_ids.add(ksd)

    currency_items = Counter(currency_by_item.values())
    result: dict[str, Any] = {
        "rows": rows,
        "unique_itm_no": len(items),
        "valid_format_itm_no": len(valid_items),
        "malformed_itm_no": len(items - valid_items),
        "unique_itm_no_attribute_pairs": len(pairs),
        "duplicate_itm_no_attribute_pairs": rows - len(pairs),
        "max_attributes_per_item": max(attributes_per_item.values()),
        "non_attribute_disagreement_items": len(non_attribute_disagreements),
        "literal_null_risk_rows": literal_null_risk_rows,
        "literal_null_risk_items": len(literal_null_risk_items),
        "fund_type_06_rows": type_06_rows,
        "fund_type_06_items": len(type_06_items),
        "name_contains_etf_rows": etf_name_rows,
        "name_contains_etf_items": len(etf_name_items),
        "name_contains_listed_index_rows": index_name_rows,
        "name_contains_listed_index_items": len(index_name_items),
        "name_etf_or_listed_index_items": len(etf_name_items | index_name_items),
        "return_below_minus_100_rows": below_minus_100_rows,
        "return_below_minus_100_items": len(below_minus_100_items),
        "currency_rows_krw": currency_rows["KRW"],
        "currency_rows_usd": currency_rows["USD"],
        "currency_rows_blank_or_other": rows - currency_rows["KRW"] - currency_rows["USD"],
        "currency_items_krw": currency_items["KRW"],
        "currency_items_usd": currency_items["USD"],
        "currency_items_blank_or_other": len(items) - currency_items["KRW"] - currency_items["USD"],
        "sale_rows_active": sale_rows["판매중"],
        "sale_rows_complete": sale_rows["판매완료"],
        "sale_rows_blank_or_other": rows - sale_rows["판매중"] - sale_rows["판매완료"],
        "mirae_sale_rows_y": own_sale_rows["Y"],
        "mirae_sale_rows_blank": own_sale_rows[""],
        "mirae_sale_rows_other": rows - own_sale_rows["Y"] - own_sale_rows[""],
        "malformed_excel_rows": malformed_excel_rows,
        "exact_domestic_etf_fund_links": len(domestic_ids & fund_ksd_ids),
    }
    return result, items


def calculate() -> dict[str, Any]:
    bonds, _ = audit_bonds()
    domestic, domestic_ids = audit_domestic_listed()
    overseas, _ = audit_overseas_listed()
    funds, _ = audit_public_funds(domestic_ids)
    return {
        "audit_version": "1.0.0",
        "snapshot_date": SNAPSHOT.isoformat(),
        "total_source_rows": bonds["rows"] + domestic["rows"] + overseas["rows"] + funds["rows"],
        "PRBD01N001": bonds,
        "PREF01N001": domestic,
        "PREF02N001": overseas,
        "PRFD01N001": funds,
    }


def differences(expected: Any, actual: Any, prefix: str = "") -> list[str]:
    output: list[str] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in expected:
                output.append(f"{path}: unexpected actual value {actual[key]!r}")
            elif key not in actual:
                output.append(f"{path}: missing actual value; expected {expected[key]!r}")
            else:
                output.extend(differences(expected[key], actual[key], path))
    elif expected != actual:
        output.append(f"{prefix}: expected {expected!r}, actual {actual!r}")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Compare with frozen expected audit")
    parser.add_argument("--write", type=Path, help="Write calculated JSON to this path")
    args = parser.parse_args(argv)

    actual = calculate()
    rendered = json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(rendered, encoding="utf-8")
    if not args.check and args.write is None:
        print(rendered, end="")

    if args.check:
        if not EXPECTED.is_file():
            print(f"Missing expected audit: {EXPECTED}", file=sys.stderr)
            return 2
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        delta = differences(expected, actual)
        if delta:
            print("Official source audit FAILED:", file=sys.stderr)
            for line in delta:
                print(f"- {line}", file=sys.stderr)
            return 1
        print(
            "Official source audit PASS: "
            f"{actual['total_source_rows']:,} rows; snapshot {actual['snapshot_date']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
