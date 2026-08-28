from __future__ import annotations

# mypy: disable-error-code="arg-type,attr-defined"
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import PurePosixPath

import pytest
from pydantic import ValidationError

_HASH = "a" * 64
_CUTOFF = date(2026, 8, 24)


def _value(
    raw_value: str,
    normalized_value: Decimal,
    *,
    column_name: str,
    column_number: int,
    unknown: bool = False,
) -> object:
    from finproof.domain.locators import SourceCellLocator
    from finproof.domain.quality import QualityStatus
    from finproof.domain.values import NormalizedValue

    return NormalizedValue[Decimal](
        raw_value=raw_value,
        normalized_value=normalized_value,
        quality_status=QualityStatus.OUT_OF_DOMAIN if unknown else QualityStatus.VALID,
        rule_id=f"external.holding.{column_name}",
        rule_version="1.0.0",
        source=SourceCellLocator(
            source_table="krx_etf_pdf",
            source_file=PurePosixPath("external/synthetic-generation.pdf"),
            source_sheet="holdings",
            source_row_number=1,
            source_column_name=column_name,
            source_column_number=column_number,
            source_column_letter=chr(64 + column_number),
            source_checksum=_HASH,
            source_snapshot_date=date(2026, 8, 22),
            source_applicable_date=date(2026, 8, 22),
        ),
    )


def _holding(
    constituent_identifier: str = "KR7005930003",
    *,
    owner_product_id: str = "KR7005930003",
    owner_source_identifier: str | None = None,
    quantity_unit: str = "shares",
    quality_state: str = "valid",
) -> object:
    from finproof.data.holdings import HoldingRecord
    from finproof.domain.locators import SourceCellLocator
    from finproof.domain.query_plan import ProductType

    return HoldingRecord(
        generation_id="synthetic-generation",
        owner_product_type=ProductType.DOMESTIC_ETF,
        owner_product_id=owner_product_id,
        owner_source_identifier=owner_source_identifier or owner_product_id,
        owner_identifier_type="krx_isu_cd",
        owner_link_method="exact_identifier",
        constituent_identifier=constituent_identifier,
        constituent_identifier_type="isin",
        raw_name="삼성전자",
        display_name="삼성전자",
        quantity=_value(
            "10.000",
            Decimal("10"),
            column_name="quantity",
            column_number=3,
            unknown=quality_state == "unknown_unit",
        ),
        quantity_unit=quantity_unit,
        market_value=_value(
            "1000.00", Decimal("1000"), column_name="market_value", column_number=4
        ),
        market_value_currency="KRW",
        weight=_value("12.500", Decimal("12.5"), column_name="weight", column_number=5),
        weight_unit="percent",
        source_owner="한국거래소",
        source_kind="krx_etf_pdf",
        direct_source_url="https://example.invalid/holdings.pdf",
        raw_file_sha256=_HASH,
        source_as_of_date=date(2026, 8, 22),
        publication_date=date(2026, 8, 23),
        source_row_ordinal=1,
        source_locator=SourceCellLocator(
            source_table="krx_etf_pdf",
            source_file=PurePosixPath("external/synthetic-generation.pdf"),
            source_sheet="holdings",
            source_row_number=1,
            source_column_name="constituent_identifier",
            source_column_number=1,
            source_column_letter="A",
            source_checksum=_HASH,
            source_snapshot_date=date(2026, 8, 22),
            source_applicable_date=date(2026, 8, 22),
        ),
    )


def _coverage(
    state: str = "partial_top_10",
    *,
    owner_product_id: str = "KR7005930003",
    owner_source_identifier: str | None = None,
    observed_holding_count: int = 1,
) -> object:
    from finproof.data.holdings import HoldingCoverageRecord, HoldingCoverageState
    from finproof.domain.query_plan import ProductType

    limitation = {
        "complete": "none",
        "partial_top_10": "partial_top_10_only",
    }[state]
    return HoldingCoverageRecord(
        owner_product_type=ProductType.DOMESTIC_ETF,
        owner_product_id=owner_product_id,
        coverage_state=HoldingCoverageState(state),
        source_generation_id="synthetic-generation",
        owner_source_identifier=owner_source_identifier or owner_product_id,
        owner_identifier_type="krx_isu_cd",
        owner_link_method="exact_identifier",
        source_owner="한국거래소",
        source_kind="krx_etf_pdf",
        direct_source_url="https://example.invalid/holdings.pdf",
        raw_file_sha256=_HASH,
        source_as_of_date=date(2026, 8, 22),
        publication_date=date(2026, 8, 23),
        observed_holding_count=observed_holding_count,
        limitation_code=limitation,
    )


def _admitted_generation(
    *,
    state: str = "partial_top_10",
    holdings: tuple[object, ...] | None = None,
    coverage: tuple[object, ...] | None = None,
    **updates: object,
) -> object:
    from finproof.data.holdings import (
        HoldingCoverageRecord,
        HoldingRecord,
        admit_holding_snapshot,
        holding_rows_sha256,
    )

    exact_holdings = tuple(holdings or (_holding(),))
    exact_coverage = tuple(coverage or (_coverage(state),))
    payload: dict[str, object] = {
        "generation_id": "synthetic-generation",
        "cutoff_date": _CUTOFF,
        "source_owner": "한국거래소",
        "source_kind": "krx_etf_pdf",
        "direct_source_url": "https://example.invalid/holdings.pdf",
        "source_as_of_date": date(2026, 8, 22),
        "publication_date": date(2026, 8, 23),
        "retrieved_at": datetime(2026, 8, 25, tzinfo=UTC),
        "raw_file_sha256": _HASH,
        "reuse_basis": "submission redisplay permission recorded",
        "schema_field_dictionary": (
            "constituent_identifier:ISIN",
            "raw_name:NAME",
            "quantity:QTY",
            "market_value:MARKET_VALUE",
            "weight:WEIGHT",
        ),
        "unit_dictionary": ("quantity:shares", "market_value:KRW", "weight:percent"),
        "holdings": exact_holdings,
        "coverage": exact_coverage,
        "declared_holding_count": len(exact_holdings),
        "declared_quarantine_count": 0,
        "quarantined_row_ordinals": (),
        "declared_holding_rows_sha256": holding_rows_sha256(
            tuple(
                HoldingRecord.model_validate(item.model_dump(mode="python"), strict=True)
                for item in exact_holdings
            )
        ),
    }
    payload.update(updates)
    raw_holdings = payload.pop("holdings")
    raw_coverage = payload.pop("coverage")
    payload["holdings"] = tuple(
        HoldingRecord.model_validate(item.model_dump(mode="python"), strict=True)
        for item in raw_holdings
    )
    payload["coverage"] = tuple(
        HoldingCoverageRecord.model_validate(item.model_dump(mode="python"), strict=True)
        for item in raw_coverage
    )
    return admit_holding_snapshot(**payload)


def test_partial_holding_coverage_allows_positive_match_but_not_negative_claim() -> None:
    generation = _admitted_generation()

    assert generation.can_support_positive("KR7005930003")
    assert not generation.can_support_absence("KR7006600007")


def test_complete_holding_coverage_can_support_exact_absence() -> None:
    generation = _admitted_generation(state="complete")

    assert generation.can_support_absence("KR7006600007")
    assert not generation.can_support_absence("KR7005930003")


def test_unknown_holding_unit_is_preserved_but_never_comparable() -> None:
    unknown = _holding(quantity_unit="unknown", quality_state="unknown_unit")
    generation = _admitted_generation(
        holdings=(unknown,),
        unit_dictionary=("quantity:unknown", "market_value:KRW", "weight:percent"),
    )

    assert generation.holdings[0].quantity.raw_value == "10.000"
    assert generation.holdings[0].quantity.normalized_value == Decimal("10")
    assert generation.holdings[0].quantity.rule_version == "1.0.0"
    assert generation.holdings[0].quantity.source.source_row_number == 1
    assert generation.holdings[0].quantity_unit == "unknown"
    assert not generation.holdings[0].quantity_is_comparable


def test_holding_record_preserves_raw_metric_values_and_complete_row_locator() -> None:
    row = _holding()

    assert (
        row.quantity.raw_value,
        row.market_value.raw_value,
        row.weight.raw_value,
    ) == ("10.000", "1000.00", "12.500")
    assert row.source_locator.source_file == PurePosixPath("external/synthetic-generation.pdf")
    assert row.source_locator.source_checksum == _HASH
    assert row.source_locator.source_row_number == row.source_row_ordinal


def test_holding_admission_requires_separate_complete_schema_field_dictionary() -> None:
    with pytest.raises(ValueError, match="schema field dictionary"):
        _admitted_generation(schema_field_dictionary=("quantity:QTY",))


def test_holding_records_are_strict_and_reject_nonexact_owner_links() -> None:
    from finproof.data.holdings import HoldingRecord

    payload = _holding().model_dump(mode="python")
    payload["owner_link_method"] = "normalized_name"
    with pytest.raises(ValidationError, match="owner_link_method"):
        HoldingRecord.model_validate(payload, strict=True)

    payload = _holding().model_dump(mode="python")
    payload["source_row_ordinal"] = "1"
    with pytest.raises(ValidationError, match="source_row_ordinal"):
        HoldingRecord.model_validate(payload, strict=True)

    payload = _holding().model_dump(mode="python")
    payload["unexpected"] = True
    with pytest.raises(ValidationError, match="unexpected"):
        HoldingRecord.model_validate(payload, strict=True)


@pytest.mark.parametrize("late_field", ["source_as_of_date", "publication_date"])
def test_holding_admission_rejects_cutoff_late_source_dates(late_field: str) -> None:
    with pytest.raises(ValidationError, match=late_field):
        _admitted_generation(**{late_field: date(2026, 8, 25)})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("direct_source_url", ""),
        ("raw_file_sha256", "not-a-hash"),
        ("reuse_basis", ""),
    ],
)
def test_holding_admission_rejects_missing_source_authority(field: str, value: str) -> None:
    with pytest.raises((ValidationError, ValueError), match=field):
        _admitted_generation(**{field: value})


def test_holding_admission_rejects_contradictory_or_falsely_known_units() -> None:
    with pytest.raises(ValueError, match="unit dictionary"):
        _admitted_generation(unit_dictionary=("quantity:units", "market_value:KRW"))

    with pytest.raises(ValidationError, match="unknown_unit"):
        _holding(quantity_unit="unknown", quality_state="valid")


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"declared_holding_count": 2}, "holding count"),
        ({"declared_holding_rows_sha256": "b" * 64}, "holding rows hash"),
        ({"declared_quarantine_count": 1}, "quarantine count"),
        (
            {"declared_quarantine_count": 1, "quarantined_row_ordinals": (1,)},
            "quarantined row",
        ),
    ],
)
def test_holding_admission_rejects_declared_count_hash_or_quarantine_drift(
    updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _admitted_generation(**updates)


def test_holding_relations_emit_unavailable_coverage_without_inventing_rows() -> None:
    from finproof.data.holdings import build_holding_relations
    from finproof.domain.query_plan import ProductType

    holdings, coverage = build_holding_relations(
        enabled_products=(
            (ProductType.DOMESTIC_ETF, "KR7005930003"),
            (ProductType.DOMESTIC_ETN, "KR7006600007"),
            (ProductType.OVERSEAS_ETF, "US78462F1030"),
            (ProductType.OVERSEAS_ETN, "US-ETN-001"),
            (ProductType.PUBLIC_FUND, "FUND-001"),
        ),
        generations=(),
        approved_owner_mappings=(),
    )

    assert holdings == ()
    assert tuple(row.owner_product_id for row in coverage) == (
        "KR7005930003",
        "KR7006600007",
        "US78462F1030",
        "US-ETN-001",
        "FUND-001",
    )
    assert all(row.coverage_state == "unavailable" for row in coverage)
    assert all(row.observed_holding_count == 0 for row in coverage)
    assert all(not row.can_support_absence for row in coverage)


def test_etn_holding_rows_are_never_admitted_from_etf_sources() -> None:
    from finproof.data.holdings import HoldingCoverageRecord, HoldingRecord
    from finproof.domain.query_plan import ProductType

    payload = _holding().model_dump(mode="python")
    payload["owner_product_type"] = ProductType.DOMESTIC_ETN
    with pytest.raises(ValidationError, match="owner_product_type"):
        HoldingRecord.model_validate(payload, strict=True)

    coverage_payload = _coverage().model_dump(mode="python")
    coverage_payload["owner_product_type"] = ProductType.DOMESTIC_ETN
    with pytest.raises(ValidationError, match="ETN coverage"):
        HoldingCoverageRecord.model_validate(coverage_payload, strict=True)


def test_holding_metric_locator_applicable_date_must_equal_source_as_of_date() -> None:
    from finproof.data.holdings import HoldingRecord
    from finproof.domain.values import NormalizedValue

    row = _holding()
    payload = row.model_dump(mode="python")
    quantity = row.quantity
    payload["quantity"] = NormalizedValue[Decimal](
        **{
            **quantity.model_dump(mode="python"),
            "source": quantity.source.model_copy(
                update={"source_applicable_date": date(2026, 8, 21)}
            ),
        }
    )
    with pytest.raises(ValidationError, match="raw lineage"):
        HoldingRecord.model_validate(payload, strict=True)


def test_holding_relations_reject_generation_for_unlisted_owner() -> None:
    from finproof.data.holdings import build_holding_relations
    from finproof.domain.query_plan import ProductType

    with pytest.raises(ValueError, match="official enabled product"):
        build_holding_relations(
            enabled_products=((ProductType.DOMESTIC_ETF, "OTHER"),),
            generations=(_admitted_generation(),),
            approved_owner_mappings=((ProductType.DOMESTIC_ETF, "KR7005930003", "KR7005930003"),),
        )


def test_holding_relation_boundary_rejects_malformed_product_specific_owner_id() -> None:
    from finproof.data.holdings import build_holding_relations
    from finproof.domain.query_plan import ProductType

    malformed_holding = _holding(owner_product_id="KRX-NAME-LINK")
    malformed_coverage = _coverage(owner_product_id="KRX-NAME-LINK")
    generation = _admitted_generation(holdings=(malformed_holding,), coverage=(malformed_coverage,))
    with pytest.raises(ValueError, match="domestic ETF owner identifier"):
        build_holding_relations(
            enabled_products=((ProductType.DOMESTIC_ETF, "KRX-NAME-LINK"),),
            generations=(generation,),
            approved_owner_mappings=((ProductType.DOMESTIC_ETF, "KRX-NAME-LINK", "KRX-NAME-LINK"),),
        )


def test_partial_top_10_holding_coverage_rejects_more_than_ten_rows() -> None:
    with pytest.raises(ValidationError, match="partial_top_10"):
        _coverage(observed_holding_count=11)


def test_holding_relation_requires_explicit_approved_exact_owner_mapping() -> None:
    from finproof.data.holdings import build_holding_relations
    from finproof.domain.query_plan import ProductType

    generation = _admitted_generation()
    with pytest.raises(ValueError, match="approved owner mapping"):
        build_holding_relations(
            enabled_products=((ProductType.DOMESTIC_ETF, "KR7005930003"),),
            generations=(generation,),
            approved_owner_mappings=(),
        )


def test_domestic_holding_mapping_rejects_source_identifier_different_from_owner() -> None:
    from finproof.data.holdings import build_holding_relations
    from finproof.domain.query_plan import ProductType

    holding = _holding(owner_source_identifier="KR7006600007")
    coverage = _coverage(owner_source_identifier="KR7006600007")
    generation = _admitted_generation(holdings=(holding,), coverage=(coverage,))
    with pytest.raises(ValueError, match="domestic ETF owner identifier"):
        build_holding_relations(
            enabled_products=((ProductType.DOMESTIC_ETF, "KR7005930003"),),
            generations=(generation,),
            approved_owner_mappings=((ProductType.DOMESTIC_ETF, "KR7006600007", "KR7005930003"),),
        )


def test_public_fund_owner_mapping_rejects_names_but_allows_exact_published_crosswalk() -> None:
    from finproof.data.holdings import (
        HoldingCoverageRecord,
        HoldingRecord,
        build_holding_relations,
    )
    from finproof.domain.query_plan import ProductType

    def generation(source_identifier: str) -> object:
        holding_payload = _holding(owner_product_id="FUND-001").model_dump(mode="python")
        holding_payload |= {
            "owner_product_type": ProductType.PUBLIC_FUND,
            "owner_source_identifier": source_identifier,
            "owner_identifier_type": "published_fund_identifier",
        }
        coverage_payload = _coverage(owner_product_id="FUND-001").model_dump(mode="python")
        coverage_payload |= {
            "owner_product_type": ProductType.PUBLIC_FUND,
            "owner_source_identifier": source_identifier,
            "owner_identifier_type": "published_fund_identifier",
        }
        return _admitted_generation(
            holdings=(HoldingRecord.model_validate(holding_payload, strict=True),),
            coverage=(HoldingCoverageRecord.model_validate(coverage_payload, strict=True),),
        )

    name = " 미래에셋 글로벌 펀드 "
    with pytest.raises(ValueError, match="published fund identifier"):
        build_holding_relations(
            enabled_products=((ProductType.PUBLIC_FUND, "FUND-001"),),
            generations=(generation(name),),
            approved_owner_mappings=((ProductType.PUBLIC_FUND, name, "FUND-001"),),
        )

    identifier = "KR7000000001"
    holdings, coverage = build_holding_relations(
        enabled_products=((ProductType.PUBLIC_FUND, "FUND-001"),),
        generations=(generation(identifier),),
        approved_owner_mappings=((ProductType.PUBLIC_FUND, identifier, "FUND-001"),),
    )
    assert holdings[0].owner_source_identifier == identifier
    assert coverage[0].owner_product_id == "FUND-001"
