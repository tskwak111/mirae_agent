#!/usr/bin/env python3
"""Independently audit the sealed August official source distribution."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from tools.xlsx_stream import iter_table_dicts
elif __package__:
    from .xlsx_stream import iter_table_dicts
else:
    from xlsx_stream import iter_table_dicts

DISTRIBUTION_DATE: Final = date(2026, 8, 24)
ROOT: Final = Path(__file__).resolve().parents[1]
SOURCE: Final = ROOT / "source_material"
EXPECTED: Final = ROOT / "tests" / "contracts" / "expected_source_audit.json"

DATA_FILES: Final = {
    "PRBD01N001": "prbd01n001_data.xlsx",
    "PREF01N001": "pref01n001_data.xlsx",
    "PREF02N001": "pref02n001_data.xlsx",
    "PRFD01N001": "prfd01n001_data.xlsx",
}
COVERAGE_BOUNDARIES: Final = {
    "PRBD01N001": "2026-08-22",
    "PREF01N001": "2026-08-22",
    "PREF02N001": "2026-08-23",
    "PRFD01N001": "2026-08-22",
}
QUALITY_FIELDS: Final = {
    "PRBD01N001": ("buy_yield", "buyable_quantity", "mat_dt"),
    "PREF01N001": ("du_chas_errt", "du_er_1y", "du_last_aum"),
    "PREF02N001": ("du_er_1d", "du_last_aum", "cu_charge_rt"),
    "PRFD01N001": ("fd_yr1_ern_r", "fd_nast_suma", "prfd_attr_cds"),
}
COVERAGE_FIELDS: Final = {
    "PRBD01N001": ("info_base_dt", "sale_yield_base_dt", "pd_std_info_update"),
    "PREF01N001": ("du_upt_dt", "wu_upt_dt", "ref_base_dt"),
    "PREF02N001": ("du_upt_dt", "wu_upt_dt", "du_clpr_base_dt"),
    "PRFD01N001": ("fd_daily_bas_dt", "fd_price_bas_dt"),
}
OFFICIAL_PROFILE: Final = {
    "total_source_rows": 53_375,
    "PRBD01N001": {
        "rows": 21_882,
        "unique_pd_no": 20_497,
        "duplicate_instruments": 1_078,
    },
    "PREF01N001": {"rows": 1_780, "group_ETF": 1_235, "group_ETN": 545},
    "PREF02N001": {"rows": 6_037, "group_ETF": 5_972, "group_ETN": 65},
    "PRFD01N001": {
        "rows": 23_676,
        "unique_itm_no": 23_676,
        "exact_domestic_etf_fund_links": 217,
    },
}


class AuditProfileError(ValueError):
    """Observed facts differ from the organizer-approved package profile."""


def _clean(value: str) -> str:
    return value.strip()


def _is_zero(value: str) -> bool:
    text = _clean(value)
    if not text:
        return False
    try:
        return Decimal(text) == 0
    except InvalidOperation:
        return False


def _quality_counts(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        field: {
            "blank": sum(not _clean(row[field]) for row in rows),
            "nonblank": sum(bool(_clean(row[field])) for row in rows),
            "numeric_zero": sum(_is_zero(row[field]) for row in rows),
        }
        for field in fields
    }


def _coverage_maxima(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict[str, str]:
    return {
        field: max((_clean(row[field]) for row in rows if _clean(row[field])), default="")
        for field in fields
    }


def _read(source_root: Path, table_id: str) -> list[dict[str, str]]:
    path = source_root / "data" / DATA_FILES[table_id]
    return [row for _, row in iter_table_dicts(path, "data")]


def calculate(*, source_root: Path = SOURCE) -> dict[str, Any]:
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    rows_by_table = {table_id: _read(source_root, table_id) for table_id in DATA_FILES}
    bond_rows = rows_by_table["PRBD01N001"]
    domestic_rows = rows_by_table["PREF01N001"]
    overseas_rows = rows_by_table["PREF02N001"]
    fund_rows = rows_by_table["PRFD01N001"]

    bond_ids = Counter(_clean(row["pd_no"]) for row in bond_rows)
    domestic_groups = Counter(_clean(row["pd_grp_no"]) for row in domestic_rows)
    overseas_groups = Counter(_clean(row["pd_grp_no"]) for row in overseas_rows)
    domestic_ids = {_clean(row["pd_itm_no"]) for row in domestic_rows if _clean(row["pd_itm_no"])}
    fund_ksd_ids = {_clean(row["ksd_itm_no"]) for row in fund_rows if _clean(row["ksd_itm_no"])}
    tables: dict[str, dict[str, Any]] = {
        "PRBD01N001": {
            "rows": len(bond_rows),
            "unique_pd_no": len(bond_ids),
            "duplicate_instruments": sum(count > 1 for count in bond_ids.values()),
        },
        "PREF01N001": {
            "rows": len(domestic_rows),
            "group_ETF": domestic_groups["ETF"],
            "group_ETN": domestic_groups["ETN"],
            "unique_product_ids": len({_clean(row["pd_itm_no"]) for row in domestic_rows}),
        },
        "PREF02N001": {
            "rows": len(overseas_rows),
            "group_ETF": overseas_groups["ETF"],
            "group_ETN": overseas_groups["ETN"],
            "unique_product_ids": len({_clean(row["pd_itm_no"]) for row in overseas_rows}),
        },
        "PRFD01N001": {
            "rows": len(fund_rows),
            "unique_itm_no": len({_clean(row["itm_no"]) for row in fund_rows}),
            "exact_domestic_etf_fund_links": len(domestic_ids & fund_ksd_ids),
        },
    }
    for table_id, rows in rows_by_table.items():
        tables[table_id]["quality_distribution"] = _quality_counts(rows, QUALITY_FIELDS[table_id])
        tables[table_id]["coverage_maxima"] = _coverage_maxima(rows, COVERAGE_FIELDS[table_id])
        tables[table_id]["coverage_boundary"] = COVERAGE_BOUNDARIES[table_id]

    return {
        "audit_version": "2.0.0",
        "distribution_date": DISTRIBUTION_DATE.isoformat(),
        "total_source_rows": sum(table["rows"] for table in tables.values()),
        **tables,
    }


def require_official_profile(actual: dict[str, Any]) -> None:
    failures: list[str] = []
    for key, expected in OFFICIAL_PROFILE.items():
        observed = actual.get(key)
        if isinstance(expected, dict) and isinstance(observed, dict):
            for field, value in expected.items():
                if observed.get(field) != value:
                    failures.append(
                        f"{key}.{field}: expected {value!r}, actual {observed.get(field)!r}"
                    )
        elif observed != expected:
            failures.append(f"{key}: expected {expected!r}, actual {observed!r}")
    if failures:
        raise AuditProfileError("; ".join(failures))


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
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--check", action="store_true", help="Compare with frozen expected audit")
    parser.add_argument("--write", type=Path, help="Write calculated JSON to this path")
    parser.add_argument(
        "--write-expected",
        type=Path,
        help="Write expected JSON only after the fixed official profile passes",
    )
    args = parser.parse_args(argv)
    source_root = args.source_root or SOURCE
    actual = calculate(source_root=source_root)
    rendered = json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write_expected is not None:
        try:
            require_official_profile(actual)
        except AuditProfileError as error:
            print(f"Official source profile FAILED: {error}", file=sys.stderr)
            return 1
        args.write_expected.parent.mkdir(parents=True, exist_ok=True)
        args.write_expected.write_text(rendered, encoding="utf-8")
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(rendered, encoding="utf-8")
    if not args.check and args.write is None and args.write_expected is None:
        print(rendered, end="")
    if args.check:
        expected_path = (
            EXPECTED
            if args.source_root is None
            else source_root.parent / "tests/contracts/expected_source_audit.json"
        )
        if not expected_path.is_file():
            print(f"Missing expected audit: {expected_path}", file=sys.stderr)
            return 2
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        delta = differences(expected, actual)
        if delta:
            print("Official source audit FAILED:", file=sys.stderr)
            for line in delta:
                print(f"- {line}", file=sys.stderr)
            return 1
        print(
            "Official source audit PASS: "
            f"{actual['total_source_rows']:,} rows; distribution {actual['distribution_date']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
