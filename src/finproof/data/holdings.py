"""Strict admission and coverage semantics for sealed holdings snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import QualityStatus
from finproof.domain.query_plan import ProductType
from finproof.domain.values import NormalizedValue

NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
AdmittedHoldingOwnerType = Literal[
    ProductType.DOMESTIC_ETF,
    ProductType.OVERSEAS_ETF,
    ProductType.PUBLIC_FUND,
]
HoldingOwnerType = Literal[
    ProductType.DOMESTIC_ETF,
    ProductType.DOMESTIC_ETN,
    ProductType.OVERSEAS_ETF,
    ProductType.OVERSEAS_ETN,
    ProductType.PUBLIC_FUND,
]

_OWNER_IDENTIFIER_TYPES = {
    ProductType.DOMESTIC_ETF: "krx_isu_cd",
    ProductType.OVERSEAS_ETF: "sec_cik_series_class",
    ProductType.PUBLIC_FUND: "published_fund_identifier",
}
_COVERAGE_OWNER_TYPES = {
    ProductType.DOMESTIC_ETF,
    ProductType.DOMESTIC_ETN,
    ProductType.OVERSEAS_ETF,
    ProductType.OVERSEAS_ETN,
    ProductType.PUBLIC_FUND,
}


class HoldingCoverageState(StrEnum):
    """Closed evidence completeness states for one official owner product."""

    COMPLETE = "complete"
    PARTIAL_TOP_10 = "partial_top_10"
    UNAVAILABLE = "unavailable"


def _require_direct_https_url(value: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("direct_source_url must be a direct credential-free HTTPS URL")


def _require_finite(value: Decimal | None, field_name: str) -> None:
    if value is not None and not value.is_finite():
        raise ValueError(f"{field_name} must be finite when available")


class HoldingRecord(BaseModel):
    """One exact external holding row with immutable source lineage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )

    generation_id: NonEmptyText
    owner_product_type: AdmittedHoldingOwnerType
    owner_product_id: NonEmptyText
    owner_source_identifier: NonEmptyText
    owner_identifier_type: NonEmptyText
    owner_link_method: Literal["exact_identifier"]
    constituent_identifier: NonEmptyText
    constituent_identifier_type: NonEmptyText
    raw_name: str
    display_name: NonEmptyText
    quantity: NormalizedValue[Decimal]
    quantity_unit: str | None
    market_value: NormalizedValue[Decimal]
    market_value_currency: str | None
    weight: NormalizedValue[Decimal]
    weight_unit: str | None
    source_owner: NonEmptyText
    source_kind: NonEmptyText
    direct_source_url: NonEmptyText
    raw_file_sha256: Sha256
    source_as_of_date: date
    publication_date: date
    source_row_ordinal: int = Field(gt=0)
    source_locator: SourceCellLocator

    @model_validator(mode="after")
    def require_exact_lineage_and_units(self) -> Self:
        _require_direct_https_url(self.direct_source_url)
        expected_identifier_type = _OWNER_IDENTIFIER_TYPES[self.owner_product_type]
        if self.owner_identifier_type != expected_identifier_type:
            raise ValueError("owner_identifier_type is not the approved exact mapping")
        if (self.quantity.normalized_value is None) != (self.quantity_unit is None):
            raise ValueError("quantity and quantity_unit availability must agree")
        if (self.market_value.normalized_value is None) != (self.market_value_currency is None):
            raise ValueError("market_value and market_value_currency availability must agree")
        if (self.weight.normalized_value is None) != (self.weight_unit is None):
            raise ValueError("weight and weight_unit availability must agree")
        _require_finite(self.quantity.normalized_value, "quantity")
        _require_finite(self.market_value.normalized_value, "market_value")
        _require_finite(self.weight.normalized_value, "weight")
        metric_units = (
            (self.quantity_unit, self.quantity),
            (self.market_value_currency, self.market_value),
            (self.weight_unit, self.weight),
        )
        if any(
            (unit == "unknown") != (wrapped.quality_status is QualityStatus.OUT_OF_DOMAIN)
            for unit, wrapped in metric_units
        ):
            raise ValueError("unknown_unit quality must exactly track an unknown unit")
        expected_lineage = (
            self.source_kind,
            self.source_locator.source_file,
            self.source_locator.source_sheet,
            self.source_row_ordinal,
            self.raw_file_sha256,
            self.source_as_of_date,
            self.source_as_of_date,
        )
        for locator in (
            self.source_locator,
            self.quantity.source,
            self.market_value.source,
            self.weight.source,
        ):
            if (
                locator.source_table,
                locator.source_file,
                locator.source_sheet,
                locator.source_row_number,
                locator.source_checksum,
                locator.source_snapshot_date,
                locator.source_applicable_date,
            ) != expected_lineage:
                raise ValueError("holding raw lineage differs within one source row")
        return self

    @property
    def quantity_is_comparable(self) -> bool:
        """Unknown-unit quantities are never eligible for numeric comparison."""
        return self.quantity.normalized_value is not None and self.quantity_unit != "unknown"

    @property
    def market_value_is_comparable(self) -> bool:
        """Unknown-currency market values are never eligible for comparison."""
        return (
            self.market_value.normalized_value is not None
            and self.market_value_currency != "unknown"
        )

    @property
    def weight_is_comparable(self) -> bool:
        """Unknown-unit weights are never eligible for comparison."""
        return self.weight.normalized_value is not None and self.weight_unit != "unknown"


class HoldingCoverageRecord(BaseModel):
    """One explicit coverage row, including unavailable source generations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )

    owner_product_type: HoldingOwnerType
    owner_product_id: NonEmptyText
    coverage_state: HoldingCoverageState
    source_generation_id: str | None
    owner_source_identifier: str | None
    owner_identifier_type: str | None
    owner_link_method: Literal["exact_identifier"] | None
    source_owner: str | None
    source_kind: str | None
    direct_source_url: str | None
    raw_file_sha256: str | None
    source_as_of_date: date | None
    publication_date: date | None
    observed_holding_count: int = Field(ge=0)
    limitation_code: Literal["none", "partial_top_10_only", "source_unavailable"]

    @model_validator(mode="after")
    def require_state_shape(self) -> Self:
        source_fields = (
            self.source_generation_id,
            self.owner_source_identifier,
            self.owner_identifier_type,
            self.owner_link_method,
            self.source_owner,
            self.source_kind,
            self.direct_source_url,
            self.raw_file_sha256,
            self.source_as_of_date,
            self.publication_date,
        )
        if self.coverage_state is HoldingCoverageState.UNAVAILABLE:
            if (
                any(value is not None for value in source_fields)
                or self.observed_holding_count != 0
                or self.limitation_code != "source_unavailable"
            ):
                raise ValueError("unavailable coverage cannot claim source evidence")
            return self
        if any(value is None for value in source_fields):
            raise ValueError("admitted coverage requires complete source evidence")
        if self.owner_product_type in {
            ProductType.DOMESTIC_ETN,
            ProductType.OVERSEAS_ETN,
        }:
            raise ValueError("ETN coverage can only be unavailable")
        assert self.direct_source_url is not None
        assert self.raw_file_sha256 is not None
        assert self.owner_identifier_type is not None
        _require_direct_https_url(self.direct_source_url)
        if len(self.raw_file_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.raw_file_sha256
        ):
            raise ValueError("raw_file_sha256 must be lowercase SHA-256")
        if self.owner_identifier_type != _OWNER_IDENTIFIER_TYPES[self.owner_product_type]:
            raise ValueError("owner_identifier_type is not the approved exact mapping")
        expected_limitation = (
            "none"
            if self.coverage_state is HoldingCoverageState.COMPLETE
            else "partial_top_10_only"
        )
        if self.limitation_code != expected_limitation:
            raise ValueError("coverage limitation does not match its state")
        if (
            self.coverage_state is HoldingCoverageState.PARTIAL_TOP_10
            and self.observed_holding_count > 10
        ):
            raise ValueError("partial_top_10 coverage cannot declare more than ten rows")
        return self

    @property
    def can_support_absence(self) -> bool:
        """Only complete coverage can establish absence for this owner."""
        return self.coverage_state is HoldingCoverageState.COMPLETE

    @classmethod
    def unavailable(
        cls,
        *,
        owner_product_type: HoldingOwnerType,
        owner_product_id: str,
    ) -> HoldingCoverageRecord:
        """Create the sole valid source-free coverage shape."""
        return cls(
            owner_product_type=owner_product_type,
            owner_product_id=owner_product_id,
            coverage_state=HoldingCoverageState.UNAVAILABLE,
            source_generation_id=None,
            owner_source_identifier=None,
            owner_identifier_type=None,
            owner_link_method=None,
            source_owner=None,
            source_kind=None,
            direct_source_url=None,
            raw_file_sha256=None,
            source_as_of_date=None,
            publication_date=None,
            observed_holding_count=0,
            limitation_code="source_unavailable",
        )


def holding_rows_sha256(holdings: tuple[HoldingRecord, ...]) -> str:
    """Hash exact canonical holding rows in their declared source order."""
    if type(holdings) is not tuple or any(type(row) is not HoldingRecord for row in holdings):
        raise TypeError("holdings must be an exact HoldingRecord tuple")
    digest = hashlib.sha256()
    for row in holdings:
        validated = HoldingRecord.model_validate(row.model_dump(mode="python"), strict=True)
        digest.update(
            json.dumps(
                validated.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


class HoldingGeneration(BaseModel):
    """One admitted immutable external source generation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )

    generation_id: NonEmptyText
    cutoff_date: date
    source_owner: NonEmptyText
    source_kind: NonEmptyText
    direct_source_url: NonEmptyText
    source_as_of_date: date
    publication_date: date
    retrieved_at: datetime
    raw_file_sha256: Sha256
    reuse_basis: NonEmptyText
    schema_field_dictionary: tuple[NonEmptyText, ...]
    unit_dictionary: tuple[NonEmptyText, ...]
    holdings: tuple[HoldingRecord, ...]
    coverage: tuple[HoldingCoverageRecord, ...]
    declared_holding_count: int = Field(ge=0)
    declared_quarantine_count: int = Field(ge=0)
    quarantined_row_ordinals: tuple[int, ...]
    declared_holding_rows_sha256: Sha256

    @model_validator(mode="after")
    def require_admitted_generation(self) -> Self:
        _require_direct_https_url(self.direct_source_url)
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() != timedelta(0):
            raise ValueError("retrieved_at must be timezone-aware UTC")
        if self.source_as_of_date > self.cutoff_date:
            raise ValueError("source_as_of_date must not exceed cutoff_date")
        if self.publication_date > self.cutoff_date:
            raise ValueError("publication_date must not exceed cutoff_date")
        required_schema_fields = {
            "constituent_identifier",
            "raw_name",
            "quantity",
            "market_value",
            "weight",
        }
        parsed_schema_fields: list[str] = []
        for declaration in self.schema_field_dictionary:
            canonical, separator, source_field = declaration.partition(":")
            if not separator or not canonical or not source_field:
                raise ValueError("schema field dictionary entries must map canonical fields")
            parsed_schema_fields.append(canonical)
        if set(parsed_schema_fields) != required_schema_fields or len(parsed_schema_fields) != len(
            required_schema_fields
        ):
            raise ValueError("schema field dictionary must cover the exact holding fields")
        if not self.unit_dictionary or (
            tuple(sorted(set(self.unit_dictionary))) != tuple(sorted(self.unit_dictionary))
        ):
            raise ValueError("unit dictionary must contain unique declarations")
        if self.declared_holding_count != len(self.holdings):
            raise ValueError("declared holding count differs from admitted rows")
        if self.declared_holding_rows_sha256 != holding_rows_sha256(self.holdings):
            raise ValueError("declared holding rows hash differs from admitted rows")
        if self.declared_quarantine_count != len(self.quarantined_row_ordinals):
            raise ValueError("declared quarantine count differs from row ordinals")
        if (
            any(type(value) is not int or value <= 0 for value in self.quarantined_row_ordinals)
            or tuple(sorted(set(self.quarantined_row_ordinals))) != self.quarantined_row_ordinals
        ):
            raise ValueError("quarantined row ordinals must be unique positive source order")
        holding_ordinals = tuple(row.source_row_ordinal for row in self.holdings)
        if tuple(sorted(set(holding_ordinals))) != holding_ordinals:
            raise ValueError("holding source rows must be unique and ordered")
        if set(holding_ordinals) & set(self.quarantined_row_ordinals):
            raise ValueError("quarantined row cannot also be an admitted holding")

        coverage_by_owner: dict[tuple[ProductType, str], HoldingCoverageRecord] = {}
        for coverage_row in self.coverage:
            key = (coverage_row.owner_product_type, coverage_row.owner_product_id)
            if key in coverage_by_owner:
                raise ValueError("coverage owner must be unique within a generation")
            coverage_by_owner[key] = coverage_row
            if (
                coverage_row.coverage_state is HoldingCoverageState.UNAVAILABLE
                or coverage_row.source_generation_id != self.generation_id
                or coverage_row.source_owner != self.source_owner
                or coverage_row.source_kind != self.source_kind
                or coverage_row.direct_source_url != self.direct_source_url
                or coverage_row.raw_file_sha256 != self.raw_file_sha256
                or coverage_row.source_as_of_date != self.source_as_of_date
                or coverage_row.publication_date != self.publication_date
            ):
                raise ValueError("coverage source lineage differs from its generation")

        observed: dict[tuple[ProductType, str], int] = dict.fromkeys(coverage_by_owner, 0)
        for holding_row in self.holdings:
            key = (holding_row.owner_product_type, holding_row.owner_product_id)
            coverage = coverage_by_owner.get(key)
            if coverage is None:
                raise ValueError("holding owner lacks an admitted coverage row")
            if (
                holding_row.generation_id != self.generation_id
                or holding_row.owner_source_identifier != coverage.owner_source_identifier
                or holding_row.owner_identifier_type != coverage.owner_identifier_type
                or holding_row.source_owner != self.source_owner
                or holding_row.source_kind != self.source_kind
                or holding_row.direct_source_url != self.direct_source_url
                or holding_row.raw_file_sha256 != self.raw_file_sha256
                or holding_row.source_as_of_date != self.source_as_of_date
                or holding_row.publication_date != self.publication_date
            ):
                raise ValueError("holding source lineage differs from its generation")
            declared_units = (
                (
                    f"quantity:{holding_row.quantity_unit}"
                    if holding_row.quantity_unit is not None
                    else None
                ),
                (
                    f"market_value:{holding_row.market_value_currency}"
                    if holding_row.market_value_currency is not None
                    else None
                ),
                (
                    f"weight:{holding_row.weight_unit}"
                    if holding_row.weight_unit is not None
                    else None
                ),
            )
            if any(
                declaration is not None and declaration not in self.unit_dictionary
                for declaration in declared_units
            ):
                raise ValueError("holding unit contradicts the generation unit dictionary")
            observed[key] += 1
        if any(
            row.observed_holding_count != observed[(row.owner_product_type, row.owner_product_id)]
            for row in self.coverage
        ):
            raise ValueError("coverage observed holding count differs from admitted rows")
        return self

    def can_support_positive(self, constituent_identifier: str) -> bool:
        """Return true only for an exact admitted positive holding row."""
        if type(constituent_identifier) is not str or not constituent_identifier:
            raise TypeError("constituent_identifier must be a nonempty exact string")
        return any(row.constituent_identifier == constituent_identifier for row in self.holdings)

    def can_support_absence(self, constituent_identifier: str) -> bool:
        """Require complete coverage for every owner before proving absence."""
        if type(constituent_identifier) is not str or not constituent_identifier:
            raise TypeError("constituent_identifier must be a nonempty exact string")
        return (
            bool(self.coverage)
            and all(row.can_support_absence for row in self.coverage)
            and not self.can_support_positive(constituent_identifier)
        )


def admit_holding_snapshot(
    *,
    generation_id: str,
    cutoff_date: date,
    source_owner: str,
    source_kind: str,
    direct_source_url: str,
    source_as_of_date: date,
    publication_date: date,
    retrieved_at: datetime,
    raw_file_sha256: str,
    reuse_basis: str,
    schema_field_dictionary: tuple[str, ...],
    unit_dictionary: tuple[str, ...],
    holdings: tuple[HoldingRecord, ...],
    coverage: tuple[HoldingCoverageRecord, ...],
    declared_holding_count: int,
    declared_quarantine_count: int,
    quarantined_row_ordinals: tuple[int, ...],
    declared_holding_rows_sha256: str,
) -> HoldingGeneration:
    """Admit one snapshot only after reconstructing its complete strict contract."""
    return HoldingGeneration.model_validate(
        {
            "generation_id": generation_id,
            "cutoff_date": cutoff_date,
            "source_owner": source_owner,
            "source_kind": source_kind,
            "direct_source_url": direct_source_url,
            "source_as_of_date": source_as_of_date,
            "publication_date": publication_date,
            "retrieved_at": retrieved_at,
            "raw_file_sha256": raw_file_sha256,
            "reuse_basis": reuse_basis,
            "schema_field_dictionary": schema_field_dictionary,
            "unit_dictionary": unit_dictionary,
            "holdings": holdings,
            "coverage": coverage,
            "declared_holding_count": declared_holding_count,
            "declared_quarantine_count": declared_quarantine_count,
            "quarantined_row_ordinals": quarantined_row_ordinals,
            "declared_holding_rows_sha256": declared_holding_rows_sha256,
        },
        strict=True,
    )


def build_holding_relations(
    *,
    enabled_products: tuple[tuple[HoldingOwnerType, str], ...],
    generations: tuple[HoldingGeneration, ...],
    approved_owner_mappings: tuple[tuple[HoldingOwnerType, str, str], ...],
) -> tuple[tuple[HoldingRecord, ...], tuple[HoldingCoverageRecord, ...]]:
    """Flatten admitted rows and fill every uncovered official owner explicitly."""
    if (
        type(enabled_products) is not tuple
        or type(generations) is not tuple
        or type(approved_owner_mappings) is not tuple
    ):
        raise TypeError("holding relation inputs must be exact tuples")
    owner_order: dict[tuple[ProductType, str], int] = {}
    for index, raw_entry in enumerate(cast(tuple[object, ...], enabled_products)):
        if (
            type(raw_entry) is not tuple
            or len(raw_entry) != 2
            or type(raw_entry[0]) is not ProductType
            or raw_entry[0] not in _COVERAGE_OWNER_TYPES
            or type(raw_entry[1]) is not str
            or not raw_entry[1]
        ):
            raise TypeError("enabled product identity is outside the holdings contract")
        entry = (cast(HoldingOwnerType, raw_entry[0]), raw_entry[1])
        if entry in owner_order:
            raise ValueError("enabled product identity must be unique")
        owner_order[entry] = index

    approved: set[tuple[ProductType, str, str]] = set()
    for raw_mapping in cast(tuple[object, ...], approved_owner_mappings):
        if (
            type(raw_mapping) is not tuple
            or len(raw_mapping) != 3
            or type(raw_mapping[0]) is not ProductType
            or raw_mapping[0] not in _OWNER_IDENTIFIER_TYPES
            or type(raw_mapping[1]) is not str
            or not raw_mapping[1]
            or type(raw_mapping[2]) is not str
            or not raw_mapping[2]
        ):
            raise TypeError("approved owner mapping is outside the exact contract")
        mapping = (
            cast(HoldingOwnerType, raw_mapping[0]),
            raw_mapping[1],
            raw_mapping[2],
        )
        if mapping in approved:
            raise ValueError("approved owner mapping must be unique")
        approved.add(mapping)

    holdings: list[HoldingRecord] = []
    coverage_by_owner: dict[tuple[ProductType, str], HoldingCoverageRecord] = {}
    for generation in generations:
        if type(generation) is not HoldingGeneration:
            raise TypeError("generation must be an exact admitted HoldingGeneration")
        validated = HoldingGeneration.model_validate(
            generation.model_dump(mode="python"), strict=True
        )
        for row in validated.coverage:
            key = (row.owner_product_type, row.owner_product_id)
            _require_product_specific_owner_mapping(row)
            assert row.owner_source_identifier is not None
            if (
                row.owner_product_type,
                row.owner_source_identifier,
                row.owner_product_id,
            ) not in approved:
                raise ValueError("generation lacks an explicit approved owner mapping")
            if key not in owner_order:
                raise ValueError("generation owner is not an official enabled product")
            if key in coverage_by_owner:
                raise ValueError("official enabled product has multiple generations")
            coverage_by_owner[key] = row
        holdings.extend(validated.holdings)

    ordered_coverage = tuple(
        coverage_by_owner.get(key)
        or HoldingCoverageRecord.unavailable(
            owner_product_type=key[0],
            owner_product_id=key[1],
        )
        for key in enabled_products
    )
    holdings.sort(
        key=lambda row: (
            owner_order[(row.owner_product_type, row.owner_product_id)],
            row.source_row_ordinal,
        )
    )
    return tuple(holdings), ordered_coverage


def _require_product_specific_owner_mapping(row: HoldingCoverageRecord) -> None:
    if row.coverage_state is HoldingCoverageState.UNAVAILABLE:
        return
    assert row.owner_source_identifier is not None
    if row.owner_product_type is ProductType.DOMESTIC_ETF:
        if (
            re.fullmatch(r"KR[A-Z0-9]{10}", row.owner_product_id) is None
            or row.owner_source_identifier != row.owner_product_id
        ):
            raise ValueError("domestic ETF owner identifier is not exact KRX identity")
    elif row.owner_product_type is ProductType.OVERSEAS_ETF:
        cik, separator_one, remainder = row.owner_source_identifier.partition("|")
        series_id, separator_two, class_id = remainder.partition("|")
        if (
            not separator_one
            or not separator_two
            or not cik.isdigit()
            or not series_id.startswith("S")
            or not class_id.startswith("C")
        ):
            raise ValueError("overseas ETF owner identifier lacks exact SEC triple")
    elif (
        row.owner_product_type is ProductType.PUBLIC_FUND
        and re.fullmatch(
            r"(?=.*[0-9])[A-Z0-9][A-Z0-9._:/-]{2,127}",
            row.owner_source_identifier,
        )
        is None
    ):
        raise ValueError("public-fund owner lacks an exact published fund identifier")
