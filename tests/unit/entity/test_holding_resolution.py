"""Focused constituent-resolution contracts."""

from finproof.entity import HoldingResolver


def _resolver(*rows: tuple[str, str, str]) -> HoldingResolver:
    return HoldingResolver._from_rows(rows)


def test_exact_identifier_requires_one_distinct_identifier_type_pair() -> None:
    resolver = _resolver(
        ("KR7005930003", "ISIN", "삼성전자"),
        ("KR7005930003", "ISIN", "삼성전자"),
    )

    result = resolver.resolve("KR7005930003")

    assert result.selected is result.candidates[0]
    assert len(result.candidates) == 1
    assert result.selected.constituent_identifier_type == "ISIN"


def test_same_identifier_under_different_types_is_bounded_ambiguity() -> None:
    result = _resolver(
        ("005930", "KRX_CODE", "삼성전자"),
        ("005930", "TICKER", "Samsung Electronics"),
    ).resolve("005930")

    assert result.selected is None
    assert tuple(candidate.constituent_identifier_type for candidate in result.candidates) == (
        "KRX_CODE",
        "TICKER",
    )


def test_normalized_exact_name_selects_only_one_distinct_pair() -> None:
    result = _resolver(("KR7005930003", "ISIN", "  삼성전자  ")).resolve("삼성전자")

    assert result.selected is result.candidates[0]
    assert result.selected.constituent_identifier == "KR7005930003"


def test_multi_pair_name_ambiguity_is_deterministic_and_bounded_to_five() -> None:
    rows = tuple((f"ID-{index}", "LOCAL", "동명이인") for index in range(9, -1, -1))

    result = _resolver(*rows).resolve("동명이인")

    assert result.selected is None
    assert tuple(candidate.constituent_identifier for candidate in result.candidates) == (
        "ID-0",
        "ID-1",
        "ID-2",
        "ID-3",
        "ID-4",
    )


def test_fuzzy_and_official_zero_row_relation_never_select() -> None:
    fuzzy = _resolver(("KR7005930003", "ISIN", "삼성전자")).resolve("삼성전")
    empty = _resolver().resolve("삼성전자")

    assert fuzzy.selected is None
    assert fuzzy.candidates == ()
    assert empty.selected is None
    assert empty.candidates == ()
