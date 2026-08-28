# mypy: disable-error-code="arg-type,misc,no-untyped-call,no-untyped-def,union-attr"
"""Strict artifact table serialization contracts."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel

from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.data.normalization.public_funds import normalize_public_fund_item
from finproof.domain.bonds import BondInstrument, BondSaleLot
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import PublicFundItem
from finproof.registry.rating import RatingRegistry
from tests.helpers.source_rows import source_row

ROOT = Path(__file__).resolve().parents[4]
AS_OF = date(2026, 8, 24)


def _bond_lot_record() -> BondSaleLot:
    registry = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")
    result = normalize_bond_lot(
        source_row(
            "PRBD01N001",
            {
                "pd_no": "KR0000000001",
                "pd_exg_mkt": "장외",
                "info_base_dt": "20260822",
                "info_seq": "1",
                "isu_dt": "20200101",
                "mat_dt": "20270711",
                "srfc_irt": "1.2300",
                "remaining_days": "365",
            },
        ),
        registry,
    )
    assert result.record is not None
    return result.record


def _bond_record() -> BondInstrument:
    result = project_bond_instrument((_bond_lot_record(),), as_of=AS_OF)
    assert result.record is not None
    return result.record


def _domestic_record() -> ListedProduct:
    result = normalize_domestic_listed(
        source_row("PREF01N001", {"du_upt_dt": "2026-07-10 09:30:00"}), AS_OF
    )
    assert result.record is not None
    return result.record


def _overseas_record() -> OverseasListedProduct:
    result = normalize_overseas_listed(source_row("PREF02N001"))
    assert result.record is not None
    return result.record


def _fund_record() -> PublicFundItem:
    result = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {"prfd_attr_cds": "C101,C102,C101", "prfd_attr_cnt": "3"},
        )
    )
    assert result.record is not None
    return result.record


def test_refreshed_bond_lot_record_json_round_trip_preserves_every_field_and_lineage() -> None:
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    record = _bond_lot_record()
    spec = TABLE_SPEC_BY_NAME["silver_bond_sale_lot"]
    row = serialize_table_row(spec, record)
    parsed = BondSaleLot.model_validate_json(row["record_json"])

    assert parsed == record
    assert parsed.source_row == record.source_row
    assert parsed.source_key == record.source_key
    assert row["source_row_number"] == record.source_row.source_row_number
    assert tuple(row) == spec.logical_projection


def test_bond_record_json_round_trip_and_projection() -> None:
    from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.values import DerivedValue, NormalizedValue

    projected = project_bond_instrument((_bond_lot_record(),), as_of=AS_OF)
    assert projected.record is not None
    record = projected.record
    payload = canonical_record_json(record)
    round_tripped = BondInstrument.model_validate_json(payload)
    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_bond_instrument"], record)

    assert round_tripped == record
    assert row["record_json"] == payload
    assert row["grain"] == "instrument"
    for name in BondInstrument.model_fields:
        if name in {"grain", "selected_lot_key", "field_sources", "buy_yield_range"}:
            continue
        wrapped = getattr(record, name)
        if isinstance(wrapped, NormalizedValue):
            assert row[name] == wrapped.normalized_value
            assert row[f"{name}__quality_status"] == wrapped.quality_status.value
        elif isinstance(wrapped, DerivedValue):
            assert row[name] == wrapped.value
            assert row[f"{name}__quality_status"] == wrapped.quality_status.value
            assert row[f"{name}__as_of_date"] == wrapped.as_of_date
        else:  # pragma: no cover - closed model declaration
            raise AssertionError(f"unexpected bond wrapper: {name}")
    assert tuple(row) == TABLE_SPEC_BY_NAME["silver_bond_instrument"].logical_projection


def test_domestic_record_json_round_trip_and_projection() -> None:
    from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.values import DerivedValue, NormalizedValue

    record = _domestic_record()
    payload = canonical_record_json(record)
    round_tripped = ListedProduct.model_validate_json(payload, strict=True)
    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_domestic_listed_product"], record)

    assert round_tripped == record
    assert row["record_json"] == payload
    for name in ListedProduct.model_fields:
        if name == "grain":
            continue
        wrapped = getattr(record, name)
        if isinstance(wrapped, NormalizedValue):
            assert row[name] == (
                wrapped.normalized_value.value
                if hasattr(wrapped.normalized_value, "value")
                else wrapped.normalized_value
            )
            assert row[f"{name}__quality_status"] == wrapped.quality_status.value
        elif isinstance(wrapped, DerivedValue):
            assert row[name] == wrapped.value
            assert row[f"{name}__quality_status"] == wrapped.quality_status.value
            assert row[f"{name}__as_of_date"] == wrapped.as_of_date
    assert tuple(row) == TABLE_SPEC_BY_NAME["silver_domestic_listed_product"].logical_projection


def test_overseas_record_json_round_trip_and_projection() -> None:
    from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    record = _overseas_record()
    payload = canonical_record_json(record)
    round_tripped = OverseasListedProduct.model_validate_json(payload, strict=True)
    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_overseas_listed_product"], record)

    assert round_tripped == record
    assert row["record_json"] == payload
    for name in OverseasListedProduct.model_fields:
        if name == "grain":
            continue
        wrapped = getattr(record, name)
        assert row[name] == (
            wrapped.normalized_value.value
            if hasattr(wrapped.normalized_value, "value")
            else wrapped.normalized_value
        )
        assert row[f"{name}__quality_status"] == wrapped.quality_status.value
    assert tuple(row) == TABLE_SPEC_BY_NAME["silver_overseas_listed_product"].logical_projection


def test_refreshed_fund_item_record_json_round_trip_preserves_every_field_and_lineage() -> None:
    from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    record = _fund_record()
    payload = canonical_record_json(record)
    round_tripped = PublicFundItem.model_validate_json(payload)
    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_fund_item"], record)

    assert round_tripped == record
    assert row["record_json"] == payload
    for name in PublicFundItem.model_fields:
        if name in {"grain", "source_row", "attribute_codes"}:
            continue
        wrapped = getattr(record, name)
        assert row[name] == wrapped.normalized_value
        assert row[f"{name}__quality_status"] == wrapped.quality_status.value
    assert round_tripped.source_row == record.source_row
    assert round_tripped.attribute_codes == ("C101", "C102", "C101")


@pytest.mark.parametrize(
    "case",
    ["bronze_column", "bronze_cell", "quality", "gold_link", "gold_evidence"],
)
def test_explicit_table_serializers_cover_bronze_quality_and_gold(case: str) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal
    from pathlib import PurePosixPath

    from finproof.data.artifacts.serialization import (
        BronzeSourceCellRecord,
        BronzeSourceColumnRecord,
        ExactCrossSourceLinkEvidenceRecord,
        ExactCrossSourceLinkRecord,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus

    column = BronzeSourceColumnRecord(
        catalog_version="1.0.0",
        source_snapshot_date=AS_OF,
        source_table_order=0,
        source_table="PRBD01N001",
        source_column_number=1,
        source_column_letter="A",
        source_column_name="PD_NO",
        source_declared_type="VARCHAR",
        source_example="KR0000000001",
        source_key_marker="PK",
        source_name_ko="상품번호",
        schema_file="schema.xlsx",
        schema_excel_row=2,
    )
    cell = BronzeSourceCellRecord(
        source_table_order=0,
        source_table="PRBD01N001",
        source_file=PurePosixPath("data/a.xlsx"),
        source_sheet="Sheet1",
        source_row_number=2,
        source_column_name="PD_NO",
        source_column_number=1,
        source_column_letter="A",
        source_checksum="a" * 64,
        source_snapshot_date=AS_OF,
        source_applicable_date=None,
        raw_value="KR0000000001",
    )
    link = ExactCrossSourceLinkRecord(
        link_id="b" * 64,
        left_table="silver_domestic_listed_product",
        left_product_id="KR7000000001",
        left_identifier_field="pd_itm_no",
        right_table="silver_fund_item",
        right_product_id="KR7000000001",
        right_identifier_field="ksd_itm_no",
        matched_raw_identifier="KR7000000001",
        link_type="exact_identifier",
        confidence=Decimal("1.0"),
        rule_id="cross_source.domestic_etf_public_fund.exact_raw_identifier",
        rule_version="1.0.0",
    )
    evidence = ExactCrossSourceLinkEvidenceRecord(
        link_id=link.link_id,
        evidence_role="left_identifier",
        evidence_role_order=0,
        evidence_ordinal=0,
        raw_identifier=link.matched_raw_identifier,
        source_table=cell.source_table,
        source_file=cell.source_file,
        source_sheet=cell.source_sheet,
        source_row_number=cell.source_row_number,
        source_column_name=cell.source_column_name,
        source_column_number=cell.source_column_number,
        source_column_letter=cell.source_column_letter,
        source_checksum=cell.source_checksum,
        source_snapshot_date=cell.source_snapshot_date,
        source_applicable_date=None,
    )
    pure = DataQualityIssue.from_row(
        source_row("PREF01N001"),
        "pd_itm_no",
        rule_id="test.rule",
        rule_version="1.0.0",
        severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.INVALID_FORMAT,
        reason="test",
        quarantined=True,
    )
    quality = DataQualityIssue.model_validate(
        {**pure.model_dump(mode="python"), "first_detected_at": datetime(2026, 8, 15, tzinfo=UTC)},
        strict=True,
    )
    cases = {
        "bronze_column": ("bronze_source_column", column),
        "bronze_cell": ("bronze_source_cell", cell),
        "quality": ("silver_quality_issue", quality),
        "gold_link": ("gold_exact_cross_source_link", link),
        "gold_evidence": ("gold_exact_cross_source_link_evidence", evidence),
    }
    table_name, value = cases[case]
    row = serialize_table_row(TABLE_SPEC_BY_NAME[table_name], value)

    assert tuple(row) == TABLE_SPEC_BY_NAME[table_name].logical_projection
    if "record_json" in row:
        assert isinstance(row["record_json"], str)


def test_bronze_source_row_alone_accepts_and_injects_persistence_timestamp() -> None:
    import json
    from datetime import UTC, datetime

    from finproof.data.artifacts.serialization import logical_table_row, serialize_bronze_source_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    value = source_row("PRBD01N001")
    timestamp = datetime(2026, 8, 15, 1, 2, 3, 456789, tzinfo=UTC)
    spec = TABLE_SPEC_BY_NAME["bronze_source_row"]
    row = serialize_bronze_source_row(spec, value, persistence_timestamp=timestamp)

    assert row["loaded_at"] is timestamp
    assert row["raw_payload_json"] == json.dumps(
        value.raw_payload, ensure_ascii=False, separators=(",", ":")
    )
    logical = logical_table_row(spec, row)
    assert logical["loaded_at"] is None
    assert tuple(logical) == spec.logical_projection


def test_persisted_quality_requires_typed_json_timestamp_agreement() -> None:
    import json
    from datetime import UTC, datetime

    from finproof.data.artifacts.serialization import logical_table_row, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus

    pure = DataQualityIssue.from_row(
        source_row("PREF01N001"),
        "pd_itm_no",
        rule_id="test.rule",
        rule_version="1.0.0",
        severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.INVALID_FORMAT,
        reason="test",
        quarantined=True,
    )
    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    persisted = DataQualityIssue.model_validate(
        {**pure.model_dump(mode="python"), "first_detected_at": timestamp}, strict=True
    )
    spec = TABLE_SPEC_BY_NAME["silver_quality_issue"]
    row = serialize_table_row(spec, persisted)

    assert row["first_detected_at"] is timestamp
    assert json.loads(row["record_json"])["first_detected_at"] == "2026-08-15T00:00:00Z"
    logical = logical_table_row(spec, row)
    assert logical["first_detected_at"] is None
    assert json.loads(logical["record_json"])["first_detected_at"] is None
    with pytest.raises(ValueError, match="timestamp agreement"):
        logical_table_row(
            spec,
            {**row, "first_detected_at": datetime(2026, 8, 15, 0, 0, 1, tzinfo=UTC)},
        )
    with pytest.raises(ValueError, match="persisted"):
        serialize_table_row(spec, pure)


@pytest.mark.parametrize(
    "field",
    [
        "issue_id",
        "rule_id",
        "rule_version",
        "severity",
        "quality_status",
        "source_table",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_column_name",
        "source_column_number",
        "source_column_letter",
        "source_checksum",
        "source_snapshot_date",
        "source_applicable_date",
        "reason",
        "quarantined",
        "raw_payload_sha256",
    ],
)
def test_quality_logical_projection_compares_each_uncovered_scalar_to_canonical_record_json(
    field: str,
) -> None:
    from datetime import UTC, datetime, timedelta

    from finproof.data.artifacts.serialization import logical_table_row, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.quality import DataQualityIssue, IssueSeverity, QualityStatus

    pure = DataQualityIssue.from_row(
        source_row("PREF01N001"),
        "pd_itm_no",
        rule_id="test.rule",
        rule_version="1.0.0",
        severity=IssueSeverity.WARNING,
        quality_status=QualityStatus.INVALID_FORMAT,
        reason="test",
        quarantined=True,
    )
    persisted = DataQualityIssue.model_validate(
        {
            **pure.model_dump(mode="python"),
            "first_detected_at": datetime(2026, 8, 15, tzinfo=UTC),
        },
        strict=True,
    )
    spec = TABLE_SPEC_BY_NAME["silver_quality_issue"]
    row = dict(serialize_table_row(spec, persisted))
    original = row[field]
    if type(original) is bool:
        changed: object = not original
    elif type(original) is int:
        changed = original + 1
    elif type(original) is date:
        changed = original + timedelta(days=1)
    elif original is None:
        changed = AS_OF
    else:
        changed = f"{original}x"

    with pytest.raises(ValueError, match="typed/JSON"):
        logical_table_row(spec, {**row, field: changed})


def test_non_bronze_serializers_expose_no_persistence_timestamp_parameter() -> None:
    from datetime import UTC, datetime
    from inspect import signature

    from finproof.data.artifacts.serialization import (
        serialize_bronze_source_row,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    assert tuple(signature(serialize_table_row).parameters) == ("spec", "value")
    assert tuple(signature(serialize_bronze_source_row).parameters) == (
        "spec",
        "value",
        "persistence_timestamp",
    )
    assert (
        signature(serialize_bronze_source_row).parameters["persistence_timestamp"].kind.name
        == "KEYWORD_ONLY"
    )
    with pytest.raises(TypeError, match="unexpected keyword"):
        serialize_table_row(
            TABLE_SPEC_BY_NAME["silver_bond_instrument"],
            _bond_record(),
            persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("case", ["string", "int64", "date", "bool", "enum"])
def test_decimal_date_local_datetime_enum_null_and_utc_encoding(case: str) -> None:
    import json
    from datetime import datetime
    from decimal import Decimal

    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    bond = _bond_record()
    domestic = _domestic_record()
    assert type(bond.coupon_rate.normalized_value) is Decimal
    assert type(bond.issue_date.normalized_value) is date
    assert (
        domestic.daily_update_date.normalized_value is None
        or type(domestic.daily_update_date.normalized_value) is date
    )
    assert domestic.tracking_error.normalized_value is None
    domestic_json = json.loads(
        serialize_table_row(TABLE_SPEC_BY_NAME["silver_domestic_listed_product"], domestic)[
            "record_json"
        ]
    )
    assert domestic_json["product_type"]["normalized_value"] == "ETF"

    if case == "string":
        forged = bond.model_copy(
            update={"name": bond.name.model_copy(update={"normalized_value": 1})}
        )
    elif case == "int64":
        forged = bond.model_copy(
            update={
                "source_remaining_days": bond.source_remaining_days.model_copy(
                    update={"normalized_value": True}
                )
            }
        )
    elif case == "date":
        forged = bond.model_copy(
            update={
                "issue_date": bond.issue_date.model_copy(
                    update={"normalized_value": datetime(2026, 8, 24)}
                )
            }
        )
    elif case == "bool":
        forged = bond.model_copy(
            update={"is_matured_at_as_of": bond.is_matured_at_as_of.model_copy(update={"value": 1})}
        )
    else:
        forged_domestic = domestic.model_copy(
            update={
                "product_type": domestic.product_type.model_copy(update={"normalized_value": "ETF"})
            }
        )
        with pytest.raises(ValueError, match="physical"):
            serialize_table_row(
                TABLE_SPEC_BY_NAME["silver_domestic_listed_product"], forged_domestic
            )
        return

    with pytest.raises(ValueError, match="physical"):
        serialize_table_row(TABLE_SPEC_BY_NAME["silver_bond_instrument"], forged)


@pytest.mark.parametrize("case", ["bronze-naive", "bronze-nonzero-offset"])
def test_serialization_rejects_nonexact_utc_timestamps(
    case: str,
) -> None:
    from datetime import datetime, timedelta, timezone

    from finproof.data.artifacts.serialization import serialize_bronze_source_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    timestamp = (
        datetime(2026, 8, 15)
        if case == "bronze-naive"
        else datetime(2026, 8, 15, tzinfo=timezone(timedelta(hours=9)))
    )
    call = lambda: serialize_bronze_source_row(  # noqa: E731
        TABLE_SPEC_BY_NAME["bronze_source_row"],
        source_row("PRBD01N001"),
        persistence_timestamp=timestamp,
    )
    with pytest.raises(ValueError, match="timestamp"):
        call()


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("1e20", id="scientific-integer-overflow"),
        pytest.param("123456789012345678901", id="twenty-one-integer-digits"),
        pytest.param("1e-19", id="scientific-scale-overflow"),
        pytest.param("0.1234567890123456789", id="nineteen-fractional-digits"),
    ],
)
def test_explicit_gold_decimal_rejects_decimal_38_18_integer_and_fractional_overflow(
    value: str,
) -> None:
    from decimal import Decimal

    from finproof.data.artifacts.serialization import (
        ExactCrossSourceLinkRecord,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    link = ExactCrossSourceLinkRecord(
        link_id="b" * 64,
        left_table="silver_domestic_listed_product",
        left_product_id="KR7000000001",
        left_identifier_field="pd_itm_no",
        right_table="silver_fund_item",
        right_product_id="KR7000000001",
        right_identifier_field="ksd_itm_no",
        matched_raw_identifier="KR7000000001",
        link_type="exact_identifier",
        confidence=Decimal("1.0"),
        rule_id="cross_source.domestic_etf_public_fund.exact_raw_identifier",
        rule_version="1.0.0",
    )
    forged = link.model_copy(update={"confidence": Decimal(value)})

    with pytest.raises(ValueError, match=r"Decimal\(38,18\)"):
        serialize_table_row(TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"], forged)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("NaN", id="not-a-number"),
        pytest.param("Infinity", id="positive-infinity"),
        pytest.param("1e20", id="integer-overflow"),
        pytest.param("1e-19", id="scale-loss"),
    ],
)
def test_serialization_rejects_nonfinite_overflow_and_scale_loss(value: str) -> None:
    from decimal import Decimal

    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    bond = _bond_record()
    forged = bond.model_copy(
        update={
            "coupon_rate": bond.coupon_rate.model_copy(update={"normalized_value": Decimal(value)})
        }
    )

    with pytest.raises(ValueError, match=r"Decimal\(38,18\)"):
        serialize_table_row(TABLE_SPEC_BY_NAME["silver_bond_instrument"], forged)


@pytest.mark.parametrize(
    "case", ["spacing", "key-order", "typed-leaf", "omitted-leaf", "extra-leaf"]
)
def test_logical_projection_rejects_noncanonical_record_json(case: str) -> None:
    import json

    from finproof.data.artifacts.serialization import logical_table_row, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    row = dict(serialize_table_row(spec, _bond_record()))
    parsed = json.loads(row["record_json"])
    if case == "spacing":
        changed = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
    elif case == "key-order":
        changed = json.dumps(
            dict(reversed(tuple(parsed.items()))),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    elif case == "typed-leaf":
        parsed["product_id"]["normalized_value"] = "FORGED"
        changed = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    elif case == "omitted-leaf":
        del parsed["product_id"]
        changed = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        parsed["extra"] = "forged"
        changed = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ValueError, match="record_json"):
        logical_table_row(spec, {**row, "record_json": changed})


@pytest.mark.parametrize("case", ["equal-looking-copy", "model-subclass", "wrong-pair"])
def test_serialization_revalidates_exact_registered_spec_and_model_pair(case: str) -> None:
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    value: BondInstrument = _bond_record()
    if case == "equal-looking-copy":
        spec = spec.model_copy()
    elif case == "model-subclass":

        class ForgedBond(BondInstrument):
            pass

        value = ForgedBond.model_validate(value.model_dump(mode="python"), strict=True)
    else:
        spec = TABLE_SPEC_BY_NAME["silver_domestic_listed_product"]

    with pytest.raises(ValueError, match="registered"):
        serialize_table_row(spec, value)


@pytest.mark.parametrize(
    "case",
    ["decimal-string", "string-subclass", "normalized-value-subclass"],
)
def test_direct_fund_item_revalidation_rejects_forged_normalized_leaves(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.data.artifacts import serialization
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.values import NormalizedValue

    value = _fund_record().model_copy(deep=True)
    if case == "decimal-string":
        object.__setattr__(value.return_1m, "normalized_value", "1.25")
    elif case == "string-subclass":

        class ForgedText(str):
            pass

        object.__setattr__(
            value.name,
            "normalized_value",
            ForgedText(value.name.normalized_value or "fund"),
        )
    else:

        class ForgedNormalizedValue(NormalizedValue[str]):
            pass

        original = value.name
        object.__setattr__(
            value,
            "name",
            ForgedNormalizedValue.model_construct(
                raw_value=original.raw_value,
                normalized_value=original.normalized_value,
                quality_status=original.quality_status,
                rule_id=original.rule_id,
                rule_version=original.rule_version,
                source=original.source,
            ),
        )

    canonical_calls = 0
    original_canonical = serialization.canonical_record_json

    def tracked_canonical(model: BaseModel):
        nonlocal canonical_calls
        canonical_calls += 1
        return original_canonical(model)

    monkeypatch.setattr(serialization, "canonical_record_json", tracked_canonical)
    with pytest.raises(ValueError, match=r"physical|Decimal"):
        serialization.serialize_table_row(
            TABLE_SPEC_BY_NAME["silver_fund_item"],
            value,
        )
    assert canonical_calls == 0


@pytest.mark.parametrize(
    "case",
    [
        "locator-str-subclass",
        "locator-date-subclass",
        "row-str-subclass",
        "cells-list",
        "cell-subclass",
    ],
)
def test_direct_fund_item_graph_rejects_forged_source_lineage(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.data.artifacts import serialization
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.source import SourceCell

    class ForgedText(str):
        pass

    class ForgedDate(date):
        pass

    class ForgedSourceCell(SourceCell):
        pass

    value = _fund_record().model_copy(deep=True)
    locator = value.fund_item_id.source
    row = value.source_row
    cell = row.cells[0]

    if case == "locator-str-subclass":
        object.__setattr__(locator, "source_table", ForgedText(locator.source_table))
    elif case == "locator-date-subclass":
        object.__setattr__(locator, "source_snapshot_date", ForgedDate(2026, 8, 24))
    elif case == "row-str-subclass":
        object.__setattr__(row, "source_table", ForgedText(row.source_table))
    elif case == "cells-list":
        object.__setattr__(row, "cells", list(row.cells))
    else:
        object.__setattr__(
            row,
            "cells",
            (
                ForgedSourceCell.model_construct(**cell.model_dump(mode="python")),
                *row.cells[1:],
            ),
        )
    canonical_calls = 0

    def fail_canonical(_model: BaseModel) -> str:
        nonlocal canonical_calls
        canonical_calls += 1
        raise AssertionError("canonical serialization must not be reached")

    monkeypatch.setattr(serialization, "canonical_record_json", fail_canonical)
    with pytest.raises(ValueError, match="physical model values"):
        serialization.serialize_table_row(
            TABLE_SPEC_BY_NAME["silver_fund_item"],
            value,
        )
    assert canonical_calls == 0


@pytest.mark.parametrize("case", ["table-grain", "nested-column-arrow-type"])
def test_serialization_rejects_mutated_registered_spec_fingerprint(case: str) -> None:
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    target = spec if case == "table-grain" else spec.columns[0]
    attribute = "grain" if case == "table-grain" else "arrow_type"
    original = getattr(target, attribute)
    try:
        object.__setattr__(target, attribute, "forged")
        with pytest.raises(ValueError, match="fingerprint"):
            serialize_table_row(spec, _bond_record())
    finally:
        object.__setattr__(target, attribute, original)
