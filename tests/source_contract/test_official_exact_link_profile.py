"""Independent exact-untrimmed official ETF/fund intersection profile."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.source_contract


def test_official_exact_untrimmed_pair_scan_is_217_etf_only_and_one_to_one() -> None:
    from finproof.data.source_manifest import SourceFileManifest
    from finproof.data.xlsx_stream import iter_xlsx_rows

    repository_root = Path(__file__).resolve().parents[2]
    source_root = repository_root / "source_material"
    verified = SourceFileManifest.load(
        source_root / "input_manifest.json",
        source_root / "schema_catalog.json",
    ).verify(source_root)
    domestic_ids: dict[str, set[str]] = {}
    for row in iter_xlsx_rows(verified.data_file("PREF01N001")):
        domestic_ids.setdefault(row.cell("pd_itm_no").raw_value, set()).add(
            row.cell("pd_grp_no").raw_value
        )
    fund_ids: dict[str, set[str]] = {}
    for row in iter_xlsx_rows(verified.data_file("PRFD01N001")):
        identifier = row.cell("ksd_itm_no").raw_value
        if identifier != "":
            fund_ids.setdefault(identifier, set()).add(row.cell("itm_no").raw_value)
    pairs = {
        (identifier, next(iter(fund_ids[identifier])))
        for identifier, product_types in domestic_ids.items()
        if product_types == {"ETF"} and identifier in fund_ids
    }

    assert len(pairs) == 217
    assert all(domestic_ids[left] == {"ETF"} for left, _right in pairs)
    assert not any("ETN" in domestic_ids[left] for left, _right in pairs)
    assert all(len(fund_ids[left]) == 1 for left, _right in pairs)
    assert len({left for left, _right in pairs}) == len(pairs)
    assert len({right for _left, right in pairs}) == len(pairs)
