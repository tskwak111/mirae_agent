"""Bounded transient-allocation tests for authoritative public-fund collapse."""

import gc
import tracemalloc
import weakref
from collections.abc import Callable

import pytest

import finproof.data.normalization.public_funds as public_funds
from finproof.domain.normalization import NormalizationResult
from finproof.domain.public_funds import FundAttributeRow
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
            {"itm_no": f"KR{index:010d}", "prfd_attr_cd": "A001"},
            excel_row=index + 2,
        )
        for index in range(size)
    )


def _transient_bytes(size: int) -> int:
    rows = _unique_item_rows(size)
    gc.collect()
    tracemalloc.start()
    try:
        result = public_funds.normalize_public_funds(iter(rows))
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        assert (len(result.items), len(result.attributes)) == (size, size)
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


def test_authoritative_path_releases_each_normalized_group(
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Normalized row records must die before the next single-row group advances."""
    original = public_funds.normalize_fund_attribute
    live = peak_live = 0

    def tracked(row: SourceRow) -> NormalizationResult[FundAttributeRow]:
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

    monkeypatch.setattr(public_funds, "normalize_fund_attribute", tracked)
    result = public_funds.normalize_public_funds(iter(_unique_item_rows(512)))
    gc.collect()
    record_property("peak_live_fund_attribute_rows", peak_live)
    assert (len(result.items), len(result.attributes)) == (512, 512)
    assert 1 <= peak_live <= 4
    assert live == 0
