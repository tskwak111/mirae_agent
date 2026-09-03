"""Bounded transient-allocation tests for authoritative public-fund collapse."""

import gc
import tracemalloc
import weakref
from collections.abc import Callable

import pytest

import finproof.data.normalization.public_funds as public_funds
from finproof.domain.normalization import NormalizationResult
from finproof.domain.public_funds import PublicFundItem
from finproof.domain.source import SourceRow
from tests.helpers.source_rows import source_row

pytestmark = [
    pytest.mark.performance,
    pytest.mark.filterwarnings(
        "ignore:record_property is incompatible with junit_family 'xunit2':pytest.PytestWarning"
    ),
]


def _unique_item_rows(size: int) -> tuple[SourceRow, ...]:
    return tuple(
        source_row(
            "PRFD01N001",
            {
                "itm_no": f"KR{index:010d}",
                "prfd_attr_cds": "A001",
                "prfd_attr_cnt": "1",
            },
            excel_row=index + 2,
        )
        for index in range(size)
    )


def _transient_bytes(size: int) -> int:
    rows = _unique_item_rows(size)
    gc.collect()
    tracemalloc.start()
    try:
        item_count = 0
        for row in rows:
            result: NormalizationResult[PublicFundItem] = public_funds.normalize_public_fund_item(
                row
            )
            assert result.record is not None
            item_count += 1
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        assert item_count == size
        return peak_bytes - current_bytes
    finally:
        tracemalloc.stop()


def test_authoritative_path_transient_slope_is_bounded(
    record_property: Callable[[str, object], None],
) -> None:
    """A second dataset-wide normalized-row collection would exceed the slope bound."""
    small_bytes = _transient_bytes(256)
    large_bytes = _transient_bytes(512)
    record_property("transient_256_bytes", small_bytes)
    record_property("transient_512_bytes", large_bytes)
    limit = int(small_bytes * 1.5) + 2 * 1024 * 1024
    assert large_bytes <= limit, (small_bytes, large_bytes, limit)


def test_authoritative_path_releases_each_normalized_item(
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Normalized row records must die before the next single-row group advances."""
    original = public_funds.normalize_public_fund_item
    live = peak_live = 0

    def tracked(row: SourceRow) -> NormalizationResult[PublicFundItem]:
        nonlocal live, peak_live
        result = original(row)
        if result.record is not None:
            live += 1
            peak_live = max(peak_live, live)

            def released() -> None:
                nonlocal live
                live -= 1

            weakref.finalize(result.record, released)
        return result

    monkeypatch.setattr(public_funds, "normalize_public_fund_item", tracked)
    for row in _unique_item_rows(512):
        result = public_funds.normalize_public_fund_item(row)
        assert result.record is not None
    del result
    gc.collect()
    record_property("peak_live_fund_attribute_rows", peak_live)
    assert 1 <= peak_live <= 4
    assert live == 0
