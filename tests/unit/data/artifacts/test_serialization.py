# mypy: disable-error-code="arg-type,misc,no-untyped-call,no-untyped-def,union-attr"
"""Strict artifact table serialization contracts."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel

from finproof.data.normalization.bonds import normalize_bond
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.data.normalization.public_funds import collapse_fund_items, normalize_fund_attribute
from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import FundItem
from finproof.registry.rating import RatingRegistry
from tests.helpers.source_rows import source_row

ROOT = Path(__file__).resolve().parents[4]
AS_OF = date(2026, 7, 11)


def _bond_record() -> BondInstrument:
    registry = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")
    result = normalize_bond(
        source_row(
            "PRBD01N001",
            {
                "ISU_DT": "20200101",
                "MAT_DT": "20270711",
                "SRFC_IRT": "1.2300",
                "REMAINING_DAYS": "365",
            },
        ),
        AS_OF,
        registry,
    )
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


def _fund_record() -> FundItem:
    normalized = []
    for excel_row, code in ((2, "C101"), (3, "C102")):
        result = normalize_fund_attribute(
            source_row("PRFD01N001", {"prfd_attr_cd": code}, excel_row=excel_row)
        )
        assert result.record is not None
        normalized.append(result.record)
    collapsed = collapse_fund_items(normalized)
    assert len(collapsed.items) == 1
    return collapsed.items[0]


def test_serialization_module_skeleton_rejects_valid_bond() -> None:
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    spec = TABLE_SPEC_BY_NAME["silver_bond_instrument"]
    assert tuple(serialize_table_row(spec, _bond_record())) == spec.logical_projection


def test_bond_record_json_round_trip_and_projection() -> None:
    from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.values import DerivedValue, NormalizedValue

    record = _bond_record()
    payload = canonical_record_json(record)
    round_tripped = BondInstrument.model_validate_json(payload, strict=True)
    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_bond_instrument"], record)

    assert round_tripped == record
    assert row["record_json"] == payload
    assert row["grain"] == "instrument"
    for name in BondInstrument.model_fields:
        if name == "grain":
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


def test_fund_item_record_json_round_trip_representative_and_lineage() -> None:
    from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    record = _fund_record()
    payload = canonical_record_json(record)
    round_tripped = FundItem.model_validate_json(payload)
    row = serialize_table_row(TABLE_SPEC_BY_NAME["silver_fund_item"], record)

    assert round_tripped == record
    assert row["record_json"] == payload
    for name in FundItem.model_fields:
        if name in {"grain", "contributing_rows"}:
            continue
        wrapped = getattr(record, name)
        assert row[name] == wrapped.representative.normalized_value
        assert row[f"{name}__quality_status"] == wrapped.representative.quality_status.value
    assert row["ksd_id"] == record.ksd_id.representative.normalized_value
    assert row["ksd_id__quality_status"] == record.ksd_id.representative.quality_status.value
    assert "equivalent_sources" not in row
    parsed = FundItem.model_validate_json(row["record_json"])
    assert parsed.contributing_rows == record.contributing_rows
    assert parsed.ksd_id.equivalent_sources == record.ksd_id.equivalent_sources


@pytest.mark.parametrize(
    "case",
    ["bronze_column", "bronze_cell", "fund_attribute", "quality", "gold_link", "gold_evidence"],
)
def test_explicit_table_serializers_cover_bronze_attribute_quality_and_gold(case: str) -> None:
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
    attribute_result = normalize_fund_attribute(source_row("PRFD01N001"))
    assert attribute_result.record is not None
    attribute = collapse_fund_items([attribute_result.record]).attributes[0]
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
        "fund_attribute": ("silver_fund_item_attribute", attribute),
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


@pytest.mark.parametrize(
    "field",
    [
        "grain",
        "fund_item_id",
        "fund_item_id__quality_status",
        "attribute_code",
        "attribute_code__quality_status",
        "attribute_code_raw",
        "source_row_number",
        "record_json",
    ],
)
def test_fund_attribute_logical_projection_compares_every_physical_column_to_canonical_record_json(
    field: str,
) -> None:
    import json

    from finproof.data.artifacts.serialization import logical_table_row, serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    normalized = normalize_fund_attribute(source_row("PRFD01N001"))
    assert normalized.record is not None
    attribute = collapse_fund_items([normalized.record]).attributes[0]
    spec = TABLE_SPEC_BY_NAME["silver_fund_item_attribute"]
    row = dict(serialize_table_row(spec, attribute))
    original = row[field]
    if field == "record_json":
        payload = json.loads(original)
        payload["attribute_code"]["raw_value"] = "FORGED"
        changed: object = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    elif type(original) is int:
        changed = original + 1
    else:
        changed = f"{original}x"

    with pytest.raises(ValueError, match="attribute typed/JSON"):
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
    assert domestic.daily_update_at.normalized_value is None or (
        type(domestic.daily_update_at.normalized_value) is datetime
        and domestic.daily_update_at.normalized_value.tzinfo is None
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
                    update={"normalized_value": datetime(2026, 7, 11)}
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


@pytest.mark.parametrize(
    "case",
    ["source-local-aware", "bronze-naive", "bronze-nonzero-offset"],
)
def test_serialization_rejects_aware_source_local_and_nonexact_utc_timestamps(
    case: str,
) -> None:
    from datetime import UTC, datetime, timedelta, timezone

    from finproof.data.artifacts.serialization import (
        serialize_bronze_source_row,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME

    if case == "source-local-aware":
        value = _domestic_record()
        forged = value.model_copy(
            update={
                "daily_update_at": value.daily_update_at.model_copy(
                    update={"normalized_value": datetime(2026, 7, 10, tzinfo=UTC)}
                )
            }
        )
        call = lambda: serialize_table_row(  # noqa: E731
            TABLE_SPEC_BY_NAME["silver_domestic_listed_product"], forged
        )
    elif case.startswith("bronze"):
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
    [
        "decimal-string",
        "string-subclass",
        "fund-value-subclass",
        "normalized-value-subclass",
    ],
)
def test_fund_wide_revalidation_rejects_json_coercible_forged_decimal_string_and_nested_model_leaves(  # noqa: E501
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from decimal import Decimal

    from finproof.data.artifacts import serialization
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.public_funds import FundItemValue
    from finproof.domain.values import NormalizedValue

    value = _fund_record().model_copy(deep=True)
    if case == "decimal-string":
        object.__setattr__(value.return_1m.representative, "normalized_value", "1.25")
    elif case == "string-subclass":

        class ForgedText(str):
            pass

        object.__setattr__(
            value.name.representative,
            "normalized_value",
            ForgedText(value.name.representative.normalized_value or "fund"),
        )
    elif case == "fund-value-subclass":

        class ForgedFundItemValue(FundItemValue[Decimal]):
            pass

        wrapped = value.return_1m
        object.__setattr__(
            value,
            "return_1m",
            ForgedFundItemValue.model_construct(
                representative=wrapped.representative,
                equivalent_sources=wrapped.equivalent_sources,
            ),
        )
    else:

        class ForgedNormalizedValue(NormalizedValue[Decimal]):
            pass

        representative = value.return_1m.representative
        object.__setattr__(
            value.return_1m,
            "representative",
            ForgedNormalizedValue.model_construct(
                raw_value=representative.raw_value,
                normalized_value=representative.normalized_value,
                quality_status=representative.quality_status,
                rule_id=representative.rule_id,
                rule_version=representative.rule_version,
                source=representative.source,
            ),
        )

    canonical_calls = 0
    original_canonical = serialization.canonical_record_json

    def tracked_canonical(model: BaseModel):
        nonlocal canonical_calls
        canonical_calls += 1
        return original_canonical(model)

    monkeypatch.setattr(serialization, "canonical_record_json", tracked_canonical)
    with pytest.raises(ValueError, match="physical model values"):
        serialization.serialize_table_row(
            TABLE_SPEC_BY_NAME["silver_fund_item"],
            value,
        )
    assert canonical_calls == 0


@pytest.mark.parametrize(
    "case",
    [
        "grain-str-subclass",
        "locator-str-subclass",
        "locator-path-subclass",
        "locator-int-subclass",
        "locator-bool",
        "locator-datetime",
        "locator-date-subclass",
        "locator-applicable-datetime",
        "equivalent-locator-int-subclass",
        "row-str-subclass",
        "row-path-subclass",
        "row-int-subclass",
        "raw-payload-str-subclass",
        "cells-list",
        "cell-subclass",
        "cell-str-subclass",
        "cell-int-subclass",
    ],
)
def test_fund_python_graph_recursively_rejects_exact_model_children_with_forged_scalar_subclasses(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from datetime import datetime
    from pathlib import PurePosixPath

    from finproof.data.artifacts import serialization
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.source import SourceCell

    class ForgedText(str):
        pass

    class ForgedInt(int):
        pass

    class ForgedDate(date):
        pass

    class ForgedPath(PurePosixPath):
        pass

    class ForgedSourceCell(SourceCell):
        pass

    value = _fund_record().model_copy(deep=True)
    representative = value.fund_item_id.representative
    locator = representative.source
    equivalent_locator = value.fund_item_id.equivalent_sources[1]
    row = value.contributing_rows[0]
    cell = row.cells[0]

    if case == "grain-str-subclass":
        object.__setattr__(value, "grain", ForgedText(value.grain))
    elif case == "locator-str-subclass":
        object.__setattr__(locator, "source_table", ForgedText(locator.source_table))
    elif case == "locator-path-subclass":
        object.__setattr__(locator, "source_file", ForgedPath(locator.source_file))
    elif case == "locator-int-subclass":
        object.__setattr__(
            locator,
            "source_row_number",
            ForgedInt(locator.source_row_number),
        )
    elif case == "locator-bool":
        object.__setattr__(locator, "source_row_number", True)
    elif case == "locator-datetime":
        object.__setattr__(
            locator,
            "source_snapshot_date",
            datetime(2026, 7, 11),
        )
    elif case == "locator-date-subclass":
        object.__setattr__(locator, "source_snapshot_date", ForgedDate(2026, 7, 11))
    elif case == "locator-applicable-datetime":
        object.__setattr__(
            locator,
            "source_applicable_date",
            datetime(2026, 7, 11),
        )
    elif case == "equivalent-locator-int-subclass":
        object.__setattr__(
            equivalent_locator,
            "source_column_number",
            ForgedInt(equivalent_locator.source_column_number),
        )
    elif case == "row-str-subclass":
        object.__setattr__(row, "source_table", ForgedText(row.source_table))
    elif case == "row-path-subclass":
        object.__setattr__(row, "source_file", ForgedPath(row.source_file))
    elif case == "row-int-subclass":
        object.__setattr__(row, "source_row_number", ForgedInt(row.source_row_number))
    elif case == "raw-payload-str-subclass":
        object.__setattr__(
            row,
            "raw_payload",
            (ForgedText(row.raw_payload[0]), *row.raw_payload[1:]),
        )
    elif case == "cells-list":
        object.__setattr__(row, "cells", list(row.cells))
    elif case == "cell-subclass":
        object.__setattr__(
            row,
            "cells",
            (
                ForgedSourceCell.model_construct(**cell.model_dump(mode="python")),
                *row.cells[1:],
            ),
        )
    elif case == "cell-str-subclass":
        object.__setattr__(cell, "raw_value", ForgedText(cell.raw_value))
    else:
        object.__setattr__(
            cell,
            "excel_column_number",
            ForgedInt(cell.excel_column_number),
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
